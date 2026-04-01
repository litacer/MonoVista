"""
Flask API 路由 — 含模型选择支持
"""
import uuid
import io
import threading
import base64
from datetime import datetime, timedelta
import numpy as np
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func
from loguru import logger
from werkzeug.security import generate_password_hash, check_password_hash

from backend.models.depth_estimator import (
    get_estimator,
    list_models,
    activate_model,
    configure_runtime,
    get_runtime_state,
    inference_guard,
)
from backend.dibr.synthesizer import get_synthesizer
from backend.utils.image_utils import (
    numpy_to_base64, bytes_to_numpy, resize_keep_aspect
)
from backend.models.user import db, User, AuditLog, ConversionHistory, ModelRegistry, Announcement, ShareLink
from backend.utils.auth_utils import create_token, jwt_required, admin_required
from backend.utils.oss_utils import upload_file_to_oss, delete_file_from_oss
from backend.utils.audit_utils import audit_action
from backend.utils.captcha_utils import generate_captcha, verify_captcha
from backend.utils.cache_utils import (
    ACTIVE_MODELS_CACHE_KEY,
    get_json_cache,
    set_json_cache,
    delete_cache,
)

ALLOWED_IMG = {"image/jpeg", "image/png", "image/gif", "image/webp"}

api_bp = Blueprint("api", __name__, url_prefix="/api")

_cache: dict = {}


# ── XSS 安全过滤 ──────────────────────────────────────────────────
# 富文本内容在存入数据库前必须经过此函数过滤。
# 策略：使用白名单（allowlist）方式，只保留常见排版标签及其安全属性，
# 移除所有 <script>、on* 事件属性、javascript: 链接等恶意代码。
# 依赖：pip install bleach
def _sanitize_html(raw_html: str) -> str:
    """
    对富文本 HTML 进行 XSS 过滤。

    允许的标签（白名单）：
      - 文字排版：p, b, strong, i, em, u, s, br, hr
      - 标题：h1~h6
      - 列表：ul, ol, li
      - 链接：a（仅 href, target, rel）
      - 图像：img（仅 src, alt, width, height，禁止 onerror 等事件）
      - 其他：blockquote, pre, code, span, div

    过滤后保证：
      - 无内联 javascript: 协议
      - 无 on* 事件属性（onclick, onload 等）
      - 无 <script> / <style> 标签

    @param raw_html  - 前端富文本编辑器输出的原始 HTML
    @return          - 安全清洗后的 HTML 字符串
    """
    try:
        import bleach
        ALLOWED_TAGS = [
            "p", "b", "strong", "i", "em", "u", "s", "br", "hr",
            "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li", "blockquote", "pre", "code",
            "span", "div", "a", "img",
        ]
        ALLOWED_ATTRS = {
            "*":   ["style", "class"],           # 允许通用 style/class（颜色、对齐等排版）
            "a":   ["href", "target", "rel"],     # 链接属性
            "img": ["src", "alt", "width", "height"],  # 图片属性（不含事件）
        }
        # strip=True：移除不在白名单中的标签（而非转义），更彻底
        cleaned = bleach.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return cleaned
    except ImportError:
        # bleach 未安装时降级为简单转义（保守策略）
        logger.warning("[xss] bleach not installed, using basic escape fallback")
        import html
        return html.escape(raw_html)


def _store(image_np, depth_result) -> str:
    sid = str(uuid.uuid4())
    _cache[sid] = {
        "image":       image_np,
        "depth_raw":   depth_result["depth_raw"],
        "depth_norm":  depth_result["depth_norm"],
        "depth_color": depth_result["depth_color"],
        "model_key":   depth_result.get("model_key", "dav2-small"),
        "model_label": depth_result.get("model_label", ""),
    }
    if len(_cache) > 30:
        del _cache[next(iter(_cache))]
    return sid


def _get(sid: str) -> dict:
    return _cache.get(sid)


# ── 公告接口（用户端公开）──────────────────────────────────────────

@api_bp.get("/announcements")
def get_announcements():
    """
    获取当前激活的公告列表（用户端调用，无需登录）。

    返回规则：
      - 仅返回 is_active=True 的记录
      - 按 create_time 倒序，最多返回 20 条

    前端使用：
      - 滚动公告栏：只读 title 字段
      - 点击弹窗：渲染 content 字段（HTML，v-html 指令）

    安全说明：
      content 字段已在写入时经过 _sanitize_html() XSS 过滤，
      前端可安全使用 v-html 渲染。
    """
    records = (
        Announcement.query
        .filter_by(is_active=True)
        .order_by(Announcement.create_time.desc())
        .limit(20)
        .all()
    )
    return jsonify({"announcements": [r.to_dict() for r in records]})


# ── 公告管理接口（管理端，需 admin 权限）──────────────────────────

@api_bp.get("/admin/announcements")
@admin_required
def admin_get_announcements():
    """获取所有公告（含已禁用），按创建时间倒序。"""
    records = Announcement.query.order_by(Announcement.create_time.desc()).all()
    return jsonify({"announcements": [r.to_dict() for r in records]})


@api_bp.post("/admin/announcements")
@admin_required
def admin_create_announcement():
    """
    创建新公告。

    请求体（JSON）：
      title    - 公告标题（必填，最多 200 字）
      content  - 富文本 HTML 内容（必填，经 XSS 过滤后存储）
      type     - 类型：info / warning / success（默认 info）
      is_active - 是否立即激活（默认 True）

    XSS 防护：
      content 字段在写入前调用 _sanitize_html() 清洗，
      移除 <script> 标签、on* 事件属性、javascript: 链接等危险内容。
    """
    data = request.get_json(force=True)
    title   = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    ann_type = (data.get("type") or "info").strip().lower()
    is_active = bool(data.get("is_active", True))

    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if len(title) > 200:
        return jsonify({"error": "标题最多 200 字"}), 400
    if ann_type not in ("info", "warning", "success"):
        ann_type = "info"

    # 写入前必须过滤 XSS：富文本内容来自用户输入，不可信任
    safe_content = _sanitize_html(content)

    record = Announcement(
        title=title,
        content=safe_content,
        type=ann_type,
        is_active=is_active,
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"announcement": record.to_dict()}), 201


@api_bp.put("/admin/announcements/<int:ann_id>")
@admin_required
def admin_update_announcement(ann_id):
    """更新公告内容（title/content/type/is_active）。"""
    record = Announcement.query.filter_by(id=ann_id).first()
    if not record:
        return jsonify({"error": "公告不存在"}), 404

    data = request.get_json(force=True)

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "标题不能为空"}), 400
        record.title = title[:200]

    if "content" in data:
        # 同样需要 XSS 过滤，防止绕过创建接口直接 PUT 注入
        record.content = _sanitize_html((data["content"] or "").strip())

    if "type" in data:
        t = (data["type"] or "info").lower()
        record.type = t if t in ("info", "warning", "success") else "info"

    if "is_active" in data:
        record.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"announcement": record.to_dict()})


@api_bp.patch("/admin/announcements/<int:ann_id>/toggle")
@admin_required
def admin_toggle_announcement(ann_id):
    """一键切换公告激活/禁用状态。"""
    record = Announcement.query.filter_by(id=ann_id).first()
    if not record:
        return jsonify({"error": "公告不存在"}), 404
    record.is_active = not record.is_active
    db.session.commit()
    return jsonify({"announcement": record.to_dict()})


@api_bp.delete("/admin/announcements/<int:ann_id>")
@admin_required
def admin_delete_announcement(ann_id):
    """删除指定公告。"""
    record = Announcement.query.filter_by(id=ann_id).first()
    if not record:
        return jsonify({"error": "公告不存在"}), 404
    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "deleted"})  


def _build_active_models_payload():
    rows = (
        ModelRegistry.query
        .filter_by(is_visible=True)
        .order_by(ModelRegistry.updated_at.desc())
        .all()
    )
    return [{
        "key": m.model_key,
        "label": m.display_name or m.name,
        "description": m.description or "",
        "status": m.status,
    } for m in rows]


def _refresh_active_models_cache():
    payload = _build_active_models_payload()
    set_json_cache(ACTIVE_MODELS_CACHE_KEY, payload)
    return payload


@api_bp.get("/models/active")
def models_active():
    """用户端菜单接口：仅返回可见模型（is_visible=true）。"""
    cached = get_json_cache(ACTIVE_MODELS_CACHE_KEY)
    if cached is not None:
        return jsonify({"models": cached, "cached": True})
    payload = _refresh_active_models_cache()
    return jsonify({"models": payload, "cached": False})


@api_bp.get("/models")
def models():
    return jsonify({"models": list_models()})


@api_bp.post("/auth/register")
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None

    if len(username) < 3 or len(password) < 6:
        return jsonify({"error": "Username >=3 chars, password >=6 chars"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
    if email and User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        nickname=username,
        email=email,
        level="Lv1",
        role="user",
    )
    db.session.add(user)
    db.session.commit()
    token = create_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()})


@api_bp.get("/auth/captcha")
def get_captcha():
    """
    生成图形验证码接口。

    流程：
      1. 调用 generate_captcha() 生成 4 位随机字符
      2. 用 Pillow 绘制带干扰线/噪点的图片，转 Base64
      3. 以 UUID 为 Key、字符文本为 Value 写入 Redis（TTL 5 分钟）
      4. 返回 { uuid, image } 给前端

    前端使用方式：
      - 将 image 直接设为 <img src="..."> 的 src
      - 将 uuid 随登录表单一起提交
      - 点击图片时再次调用此接口刷新

    返回：
        { "uuid": "...", "image": "data:image/png;base64,..." }
    """
    try:
        captcha_uuid, image_b64 = generate_captcha()
        return jsonify({"uuid": captcha_uuid, "image": image_b64})
    except RuntimeError as e:
        logger.error(f"[captcha] Generate failed: {e}")
        return jsonify({"error": str(e)}), 503


@api_bp.post("/auth/login")
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    # ── 验证码校验 ────────────────────────────────────────────────
    # 从请求体中提取前端提交的 UUID 和用户输入的验证码
    captcha_uuid = (data.get("captcha_uuid") or "").strip()
    captcha_code = (data.get("captcha_code") or "").strip()

    if not captcha_uuid or not captcha_code:
        return jsonify({"error": "请填写验证码"}), 400

    # verify_captcha：从 Redis 取出存储值与用户输入比对（忽略大小写），
    # 验证通过后立即删除 Redis Key（防止重放攻击）
    if not verify_captcha(captcha_uuid, captcha_code):
        return jsonify({"error": "验证码错误或已过期，请刷新后重试"}), 400

    # ── 用户名/密码校验 ───────────────────────────────────────────
    if not username or len(password) < 6:
        return jsonify({"error": "Invalid username or password"}), 401

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()})


@api_bp.post("/auth/forgot-password")
def forgot_password():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify({"error": "New password >=6 chars"}), 400

    user = User.query.filter_by(username=username, email=email).first()
    if not user:
        return jsonify({"error": "Username and email do not match"}), 400

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Password reset success"})


@api_bp.get("/auth/profile")
@jwt_required
def get_profile():
    return jsonify({"user": g.current_user.to_dict()})


@api_bp.post("/auth/change-password")
@jwt_required
@audit_action(action="change_password", object_type="user", object_id_key="user_id")
def change_password():
    """
    修改密码（需登录）。

    请求 JSON：
      old_password  - 当前密码（明文）
      new_password  - 新密码（明文，6~64 位）

    安全策略：
      1. check_password_hash 校验旧密码，防止旁路攻击
      2. 新密码长度 6-64，拒绝过弱密码
      3. 新旧密码不允许相同
      4. 更新成功后客户端应清除 Token 并重新登录
         （Token 本身在 JWT_EXPIRE_HOURS 后失效；
          如需立即失效可在 Redis 维护黑名单，此处从简）
    """
    from werkzeug.security import check_password_hash, generate_password_hash
    data = request.get_json(force=True) or {}
    old_pwd = (data.get('old_password') or '').strip()
    new_pwd = (data.get('new_password') or '').strip()

    if not old_pwd or not new_pwd:
        return jsonify({'error': '原密码和新密码不能为空'}), 400
    if len(new_pwd) < 6 or len(new_pwd) > 64:
        return jsonify({'error': '新密码长度须为 6 ~ 64 位'}), 400

    user = g.current_user
    if not check_password_hash(user.password_hash, old_pwd):
        return jsonify({'error': '原密码错误'}), 400
    if check_password_hash(user.password_hash, new_pwd):
        return jsonify({'error': '新密码不能与原密码相同'}), 400

    user.password_hash = generate_password_hash(new_pwd)
    db.session.commit()
    logger.info(f"[change_password] uid={user.id} username={user.username}")
    return jsonify({'message': '密码已更新，请重新登录'})


@api_bp.put("/auth/profile")
@jwt_required
def update_profile():
    data = request.get_json(force=True)
    user = g.current_user

    nickname = data.get("nickname")
    email = data.get("email")
    signature = data.get("signature")

    if nickname is not None:
        user.nickname = (nickname or "").strip() or user.nickname

    if email is not None:
        email = (email or "").strip() or None
        if email:
            exists = User.query.filter(User.email == email, User.id != user.id).first()
            if exists:
                return jsonify({"error": "Email already used"}), 400
        user.email = email

    if signature is not None:
        sig = (signature or "").strip()
        # 签名长度校验：最多 100 字符（含中文）
        if len(sig) > 100:
            return jsonify({"error": "签名最多 100 个字符"}), 400
        user.signature = sig

    db.session.commit()
    return jsonify({"user": user.to_dict()})


@api_bp.get("/audit/logs")
@jwt_required
def get_audit_logs():
    """返回当前用户最近 50 条操作日志，用于个人中心「最近动态」。"""
    user = g.current_user
    limit = min(int(request.args.get("limit", 20)), 50)
    logs = (
        AuditLog.query
        .filter_by(user_id=user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({"logs": [l.to_dict() for l in logs]})


import random

_BIND_CODE_PREFIX = "auth:code:"
_BIND_CODE_TTL    = 300   # 5 分钟


@api_bp.post("/auth/bind/send-code")
@jwt_required
def bind_send_code():
    """
    发送账号绑定验证码。

    请求体：
      type   - 绑定类型：'email' 或 'phone'
      target - 目标邮箱或手机号

    Redis 存储逻辑：
      Key:   auth:code:{user_id}:{type}   （含类型，防止邮箱/手机码互串）
      Value: 6 位数字验证码（字符串）
      TTL:   300 秒（5 分钟）

    安全说明：
      - 服务端生成并存储，客户端不可伪造
      - TTL 到期自动失效，防止暴力枚举
      - 当前采用控制台打印模拟发送（生产环境替换为短信/邮件 SDK）
    """
    from backend.utils.captcha_utils import _get_redis
    data = request.get_json(force=True)
    bind_type = (data.get("type") or "").strip().lower()
    target    = (data.get("target") or "").strip()

    if bind_type not in ("email", "phone"):
        return jsonify({"error": "type 必须是 email 或 phone"}), 400
    if not target:
        return jsonify({"error": "目标不能为空"}), 400

    user = g.current_user

    # 校验目标是否已被他人绑定
    if bind_type == "email":
        exists = User.query.filter(User.email == target, User.id != user.id).first()
        if exists:
            return jsonify({"error": "该邮箱已被其他账号绑定"}), 409
    else:
        exists = User.query.filter(User.phone == target, User.id != user.id).first()
        if exists:
            return jsonify({"error": "该手机号已被其他账号绑定"}), 409

    # 生成 6 位随机数字验证码
    code = "{:06d}".format(random.randint(0, 999999))

    # 写入 Redis，Key 含用户 ID 与绑定类型，确保每个用户每种类型独立存储
    redis_key = f"{_BIND_CODE_PREFIX}{user.id}:{bind_type}"
    try:
        _get_redis().setex(redis_key, _BIND_CODE_TTL, code)
    except Exception as e:
        logger.error(f"[bind] Redis write failed: {e}")
        return jsonify({"error": "验证码服务暂时不可用，请稍后重试"}), 503

    # 控制台模拟发送（生产替换为 send_email / send_sms）
    logger.info(f"[bind] 模拟发送验证码 → 用户={user.username} 类型={bind_type} 目标={target} 验证码={code}")
    print(f"\n{'='*50}")
    print(f"  [模拟发送] 绑定验证码")
    print(f"  类型：{bind_type}  目标：{target}")
    print(f"  验证码：{code}  有效期：5 分钟")
    print(f"{'='*50}\n")

    return jsonify({"message": f"验证码已发送至 {target}，请在 5 分钟内完成验证"})


@api_bp.post("/auth/bind/confirm")
@jwt_required
def bind_confirm():
    """
    确认绑定：校验验证码并更新数据库中的邮箱或手机号。

    请求体：
      type   - 'email' 或 'phone'
      target - 目标值
      code   - 用户输入的 6 位验证码

    Redis 校验逻辑：
      1. 构造 Key = auth:code:{user_id}:{type} 从 Redis 读取
      2. Key 不存在 → 验证码已过期或未发送
      3. 值不匹配   → 验证码错误
      4. 校验通过后立即 DELETE Key（一次性，防重放）
      5. 更新数据库字段并提交
    """
    from backend.utils.captcha_utils import _get_redis
    data = request.get_json(force=True)
    bind_type = (data.get("type") or "").strip().lower()
    target    = (data.get("target") or "").strip()
    code      = (data.get("code") or "").strip()

    if bind_type not in ("email", "phone"):
        return jsonify({"error": "type 必须是 email 或 phone"}), 400
    if not target or not code:
        return jsonify({"error": "目标和验证码不能为空"}), 400

    user = g.current_user

    # Step 1：从 Redis 读取验证码
    redis_key = f"{_BIND_CODE_PREFIX}{user.id}:{bind_type}"
    try:
        stored = _get_redis().get(redis_key)
    except Exception as e:
        logger.error(f"[bind] Redis read failed: {e}")
        return jsonify({"error": "验证服务暂时不可用"}), 503

    # Step 2：Key 不存在（未发送或已过期）
    if not stored:
        return jsonify({"error": "验证码已过期或尚未发送，请重新获取"}), 400

    # Step 3：比对验证码
    if stored.strip() != code:
        return jsonify({"error": "验证码错误，请重新输入"}), 400

    # Step 4：校验通过 → 立即删除 Redis Key（防重放）
    try:
        _get_redis().delete(redis_key)
    except Exception as e:
        logger.warning(f"[bind] Redis delete failed (non-critical): {e}")

    # Step 5：再次校验目标是否已被他人绑定（并发场景防御）
    if bind_type == "email":
        exists = User.query.filter(User.email == target, User.id != user.id).first()
        if exists:
            return jsonify({"error": "该邮箱已被其他账号绑定"}), 409
        user.email = target
    else:
        exists = User.query.filter(User.phone == target, User.id != user.id).first()
        if exists:
            return jsonify({"error": "该手机号已被其他账号绑定"}), 409
        user.phone = target

    db.session.commit()
    logger.info(f"[bind] 绑定成功 用户={user.username} 类型={bind_type} 目标={target}")
    return jsonify({"message": "绑定成功", "user": user.to_dict()})


@api_bp.post("/history")
@jwt_required
def save_history():
    """
    保存一条转换历史记录。

    请求体（JSON）：
        original_url   - 原图 OSS URL（由前端 /upload 接口上传后获得）
        depth_url      - 深度图 OSS URL
        thumbnail_url  - 缩略图 URL（可选，默认复用 original_url）
        model_key      - 使用的深度估计模型标识
        model_label    - 模型人类可读名称
        image_width    - 图像宽度（像素）
        image_height   - 图像高度（像素）
        render_config  - 3D 渲染参数 JSON，如 {"intensity": 0.04}

    返回：
        新创建记录的完整 dict
    """
    data = request.get_json(force=True)
    user = g.current_user

    # 校验必填字段
    if not data.get("original_url") or not data.get("depth_url"):
        return jsonify({"error": "original_url and depth_url are required"}), 400

    record = ConversionHistory(
        user_id       = user.id,
        original_url  = data["original_url"],
        depth_url     = data["depth_url"],
        thumbnail_url = data.get("thumbnail_url"),
        model_key     = data.get("model_key", ""),
        model_label   = data.get("model_label", ""),
        image_width   = data.get("image_width"),
        image_height  = data.get("image_height"),
        # render_config 存储前端传入的 3D 参数快照，MySQL JSON 类型自动序列化
        render_config = data.get("render_config") or {},
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"record": record.to_dict()}), 201


@api_bp.get("/history")
@jwt_required
def get_history():
    """
    获取当前用户的转换历史列表。

    查询参数：
        limit  - 返回条数上限（默认 20，最大 50）

    返回：
        records 数组，按创建时间倒序排列
    """
    user  = g.current_user
    limit = min(int(request.args.get("limit", 20)), 50)
    records = (
        ConversionHistory.query
        .filter_by(user_id=user.id)
        .order_by(ConversionHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({"records": [r.to_dict() for r in records]})


@api_bp.delete("/history/<int:record_id>")
@jwt_required
def delete_history(record_id):
    """
    删除指定历史记录（仅限本人记录）。
    """
    user   = g.current_user
    record = ConversionHistory.query.filter_by(id=record_id, user_id=user.id).first()
    if not record:
        return jsonify({"error": "Record not found"}), 404
    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "deleted"})


# ============================================================
# Admin Portal APIs（RBAC：仅 role=admin）
# ============================================================


def _seed_model_registry_if_empty():
    """首次启动时自动初始化模型仓库记录。"""
    if ModelRegistry.query.count() > 0:
        # 兼容历史数据：补齐新字段默认值
        rows = ModelRegistry.query.all()
        touched = False
        for r in rows:
            if r.display_name is None:
                r.display_name = r.name
                touched = True
            if r.description is None:
                r.description = ""
                touched = True
            if r.is_visible is None:
                r.is_visible = True
                touched = True
        if touched:
            db.session.commit()
            _refresh_active_models_cache()
        return

    defaults = [
        {"name": "Depth Anything V2 Small", "display_name": "DAV2 Small", "description": "速度最快，适合极速预览", "model_key": "dav2-small", "framework": "PyTorch", "version": "v1.0.0", "status": "Active", "infer_latency_ms": 32.0, "vram_mb": 1450.0},
        {"name": "Depth Anything V2 Base", "display_name": "DAV2 Base", "description": "速度与精度均衡，适合通用场景", "model_key": "dav2-base", "framework": "PyTorch", "version": "v1.0.0", "status": "Inactive", "infer_latency_ms": 47.0, "vram_mb": 2160.0},
        {"name": "Depth Anything V2 Large", "display_name": "DAV2 Large", "description": "高精度，适合复杂细节恢复", "model_key": "dav2-large", "framework": "PyTorch", "version": "v1.0.0", "status": "Inactive", "infer_latency_ms": 69.0, "vram_mb": 3290.0},
        {"name": "Monodepth2", "display_name": "Monodepth2", "description": "适合复杂室外场景", "model_key": "mono2-stereo", "framework": "PyTorch", "version": "v1.0.0", "status": "Inactive", "infer_latency_ms": 28.0, "vram_mb": 980.0},
    ]
    for item in defaults:
        db.session.add(ModelRegistry(
            name=item["name"],
            display_name=item["display_name"],
            description=item["description"],
            is_visible=True,
            model_key=item["model_key"],
            framework=item["framework"],
            oss_weight_path=f"oss://models/{item['model_key']}/weights.bin",
            version=item["version"],
            status=item["status"],
            infer_latency_ms=item["infer_latency_ms"],
            vram_mb=item["vram_mb"],
        ))
    db.session.commit()
    _refresh_active_models_cache()


@api_bp.get("/admin/model-registry")
@admin_required
def admin_model_registry():
    _seed_model_registry_if_empty()
    runtime = get_runtime_state()
    models = ModelRegistry.query.order_by(ModelRegistry.updated_at.desc()).all()
    return jsonify({
        "models": [m.to_dict() for m in models],
        "runtime": runtime,
    })


@api_bp.put("/admin/model-registry/<int:model_id>/visibility")
@admin_required
def admin_update_model_visibility(model_id):
    """菜单式模型激活开关：更新 is_visible 并刷新 Redis 可用模型缓存。"""
    _seed_model_registry_if_empty()
    data = request.get_json(force=True)
    is_visible = bool(data.get("is_visible", True))

    rec = ModelRegistry.query.filter_by(id=model_id).first()
    if not rec:
        return jsonify({"error": "model not found"}), 404

    rec.is_visible = is_visible
    db.session.commit()
    payload = _refresh_active_models_cache()
    return jsonify({"model": rec.to_dict(), "active_models": payload})


@api_bp.put("/admin/model-registry/<int:model_id>/meta")
@admin_required
def admin_update_model_meta(model_id):
    """更新 display_name / description，并同步刷新用户端下拉缓存。"""
    _seed_model_registry_if_empty()
    data = request.get_json(force=True)
    rec = ModelRegistry.query.filter_by(id=model_id).first()
    if not rec:
        return jsonify({"error": "model not found"}), 404

    if "display_name" in data:
        rec.display_name = (data.get("display_name") or "").strip() or rec.name
    if "description" in data:
        rec.description = (data.get("description") or "").strip()
    db.session.commit()

    payload = _refresh_active_models_cache()
    return jsonify({"model": rec.to_dict(), "active_models": payload})


@api_bp.post("/admin/model-registry/activate")
@admin_required
def admin_activate_model():
    """
    激活模型（热切换核心 API）。

    请求体：
      model_key   目标模型 key
      precision   FP32 / FP16
      device      CPU / GPU / CUDA
    """
    _seed_model_registry_if_empty()
    data = request.get_json(force=True)
    model_key = (data.get("model_key") or "").strip()
    precision = (data.get("precision") or "fp32").lower()
    device = (data.get("device") or "cpu").lower()

    rec = ModelRegistry.query.filter_by(model_key=model_key).first()
    if not rec:
        return jsonify({"error": "model not found"}), 404

    state = activate_model(model_key=model_key, precision=precision, device=device)

    # 更新数据库状态：仅一个 Active
    ModelRegistry.query.update({"status": "Inactive"})
    rec.status = "Active"
    db.session.commit()
    _refresh_active_models_cache()

    return jsonify({"runtime": state, "active_model": rec.to_dict()})


@api_bp.put("/admin/model-registry/runtime")
@admin_required
def admin_update_runtime_config():
    """配置中心：动态调整推理精度与设备。"""
    data = request.get_json(force=True)
    precision = (data.get("precision") or "").lower() or None
    device = (data.get("device") or "").lower() or None
    runtime = configure_runtime(device=device, precision=precision)
    return jsonify({"runtime": runtime})


@api_bp.get("/admin/dashboard")
@admin_required
def admin_dashboard():
    """监控大屏统计：近七日趋势 + 模型占比。"""
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=6)

    rows = (
        db.session.query(func.date(ConversionHistory.created_at), func.count(ConversionHistory.id))
        .filter(ConversionHistory.created_at >= datetime.combine(start_date, datetime.min.time()))
        .group_by(func.date(ConversionHistory.created_at))
        .all()
    )
    day_map = {str(day): int(cnt) for day, cnt in rows}
    seven_day = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        ds = d.isoformat()
        seven_day.append({"date": ds, "count": day_map.get(ds, 0)})

    model_rows = (
        db.session.query(ConversionHistory.model_label, func.count(ConversionHistory.id))
        .group_by(ConversionHistory.model_label)
        .order_by(func.count(ConversionHistory.id).desc())
        .all()
    )
    model_dist = [{"name": (name or "Unknown"), "value": int(cnt)} for name, cnt in model_rows]

    return jsonify({"seven_day": seven_day, "model_dist": model_dist})


@api_bp.get("/admin/activity-feed")
@admin_required
def admin_activity_feed():
    """
    实时操作流水线 — 返回最新 15 条审计日志（多表联查）。

    SQL 逻辑：
      SELECT audit_logs.*, users.nickname, users.username
      FROM audit_logs
      LEFT JOIN users ON audit_logs.user_id = users.id
      ORDER BY audit_logs.created_at DESC
      LIMIT 15

      LEFT JOIN 保证 user_id=NULL 的匿名记录也能返回。
    """
    def _infer_module(action):
        a = (action or "").lower()
        if any(k in a for k in ("login", "register", "logout")): return "认证"
        if any(k in a for k in ("avatar", "profile")): return "用户"
        if any(k in a for k in ("upload", "depth", "convert", "image")): return "转换"
        if "model" in a: return "模型"
        if "announce" in a: return "公告"
        return "系统"

    rows = (
        db.session.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(15)
        .all()
    )

    feed = []
    for log, user in rows:
        feed.append({
            "id":         log.id,
            "username":   (user.nickname or user.username) if user else "匿名",
            "action":     log.action or "",
            "module":     _infer_module(log.action),
            "status":     "success",
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        })

    return jsonify({"feed": feed})


@api_bp.get("/admin/conversions")
@admin_required
def admin_conversions():
    """
    资源管理（全量 OSS 转换记录）。

    查询参数：
      user_id, start_at, end_at, page, page_size
    """
    q = ConversionHistory.query
    user_id = request.args.get("user_id", type=int)
    start_at = request.args.get("start_at", "").strip()
    end_at = request.args.get("end_at", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 20, type=int), 1), 100)

    if user_id is not None:
        q = q.filter(ConversionHistory.user_id == user_id)
    if start_at:
        try:
            q = q.filter(ConversionHistory.created_at >= datetime.fromisoformat(start_at))
        except ValueError:
            return jsonify({"error": "Invalid start_at"}), 400
    if end_at:
        try:
            q = q.filter(ConversionHistory.created_at <= datetime.fromisoformat(end_at))
        except ValueError:
            return jsonify({"error": "Invalid end_at"}), 400

    total = q.count()
    records = (
        q.order_by(ConversionHistory.created_at.desc())
         .offset((page - 1) * page_size)
         .limit(page_size)
         .all()
    )

    # 批量补充用户名，避免前端二次请求
    uid_set = {r.user_id for r in records if r.user_id is not None}
    user_map = {}
    if uid_set:
        user_rows = User.query.filter(User.id.in_(uid_set)).all()
        user_map = {u.id: u.username for u in user_rows}

    payload = []
    for r in records:
        row = r.to_dict()
        row["username"] = user_map.get(r.user_id, "")
        payload.append(row)

    return jsonify({
        "records": payload,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@api_bp.get("/admin/audit-logs")
@admin_required
def admin_audit_logs():
    """
    审计日志列表：支持按 IP 和 action 过滤。
    """
    ip = request.args.get("ip", "").strip()
    action = request.args.get("action", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 30, type=int), 1), 200)

    q = AuditLog.query
    if ip:
        q = q.filter(AuditLog.ip.like(f"%{ip}%"))
    if action:
        q = q.filter(AuditLog.action.like(f"%{action}%"))

    total = q.count()
    logs = (
        q.order_by(AuditLog.created_at.desc())
         .offset((page - 1) * page_size)
         .limit(page_size)
         .all()
    )

    # 批量补充用户名
    uid_set = {l.user_id for l in logs if l.user_id is not None}
    user_map = {}
    if uid_set:
        user_rows = User.query.filter(User.id.in_(uid_set)).all()
        user_map = {u.id: u.username for u in user_rows}

    payload = []
    for l in logs:
        row = l.to_dict()
        row["username"] = user_map.get(l.user_id, "")
        payload.append(row)

    return jsonify({
        "logs": payload,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@api_bp.post("/auth/avatar")
@jwt_required
@audit_action(action="update_avatar", object_type="avatar", object_id_key="avatar_url")
def upload_avatar():
    """接收 multipart/form-data 文件，上传至阿里云 OSS，返回公开 URL。"""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.content_type not in ALLOWED_IMG:
        return jsonify({"error": "Only JPG/PNG/GIF/WebP allowed"}), 400

    user = g.current_user
    try:
        new_url = upload_file_to_oss(f, folder="avatars")
    except RuntimeError as e:
        logger.warning(f"[avatar] OSS config error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"[avatar] OSS upload failed: {e}")
        return jsonify({"error": "Upload failed, please try again"}), 500

    # 删除 OSS 上的旧头像
    if user.avatar_url and user.avatar_url.startswith("https://"):
        delete_file_from_oss(user.avatar_url)

    user.avatar_url = new_url
    db.session.commit()
    return jsonify({"avatar_url": new_url, "user": user.to_dict()})


def _save_history_async(app, user_id, original_b64, depth_b64,
                        model_key, model_label, width, height, render_config):
    """
    在独立线程中将原图和深度图上传至 OSS，并将历史记录持久化到 MySQL。

    设计原则：
        - 独立守护线程执行，不阻塞 /upload 接口响应
        - 利用 app.app_context() 保证 SQLAlchemy 会话安全
        - base64 → bytes → BytesIO 模拟 FileStorage，复用 upload_file_to_oss
        - 任何步骤失败仅打 warning，不影响主流程

    参数：
        app           - Flask app 实例（线程内需要应用上下文）
        user_id       - 当前用户 ID
        original_b64  - 原图 base64 字符串（data:image/png;base64,... 格式）
        depth_b64     - 深度图 base64 字符串
        model_key     - 模型标识
        model_label   - 模型名称
        width/height  - 图像尺寸
        render_config - 3D 渲染参数字典，如 {"intensity": 0.04}
    """
    def _run():
        try:
            with app.app_context():
                def b64_to_fileobj(b64_str, content_type="image/png"):
                    """将 base64 字符串转换为类 FileStorage 对象供 OSS 上传使用。"""
                    # 去除 data URI 前缀（如 data:image/png;base64,）
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    raw = base64.b64decode(b64_str)
                    buf = io.BytesIO(raw)
                    buf.seek(0)
                    # 模拟 werkzeug FileStorage 的最小接口
                    buf.content_type = content_type
                    buf.stream = buf
                    return buf

                # 上传原图至 OSS images/ 目录
                original_obj = b64_to_fileobj(original_b64, "image/png")
                original_url = upload_file_to_oss(original_obj, folder="images")

                # 上传深度图至 OSS depths/ 目录
                depth_obj = b64_to_fileobj(depth_b64, "image/png")
                depth_url = upload_file_to_oss(depth_obj, folder="depths")

                # 将两个 URL 和渲染参数存入 conversion_history 表
                record = ConversionHistory(
                    user_id       = user_id,
                    original_url  = original_url,
                    depth_url     = depth_url,
                    thumbnail_url = original_url,   # 缩略图复用原图 URL
                    model_key     = model_key,
                    model_label   = model_label,
                    image_width   = width,
                    image_height  = height,
                    render_config = render_config,  # JSON 自动序列化
                )
                db.session.add(record)
                db.session.commit()
                logger.info(f"[history] Saved record id={record.id} uid={user_id}")
        except Exception as e:
            logger.warning(f"[history] Failed to save history: {e}")

    threading.Thread(target=_run, daemon=True).start()


@api_bp.post("/upload")
@jwt_required
@audit_action(action="upload_image", object_type="image", object_id_key="session_id")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        return jsonify({"error": "Only JPG/PNG/WEBP supported"}), 400

    max_size  = int(request.form.get("max_size", 1024))

    # 防错校验：若用户提交了被禁用模型 ID，直接友好拦截
    requested_model_key = (request.form.get("model_key") or "").strip()
    if requested_model_key:
        req_model = ModelRegistry.query.filter_by(model_key=requested_model_key).first()
        if req_model and not req_model.is_visible:
            return jsonify({"error": "该算法模块正在维护中"}), 400

    # 强制使用“管理端当前激活模型”：忽略用户端传入的 model_key
    # 目的：确保线上推理模型由管理员统一控制，保持结果一致性与可运维性。
    runtime = get_runtime_state()
    model_key = runtime.get("active_model_key") or "dav2-small"

    image_bytes = f.read()
    logger.info(f"Upload: {f.filename}, model={model_key}, {len(image_bytes)} bytes")

    image_np = bytes_to_numpy(image_bytes)
    image_np = resize_keep_aspect(image_np, max_size=max_size)
    H, W = image_np.shape[:2]

    with inference_guard():
        estimator = get_estimator(model_key)
        depth_result = estimator.estimate(image_np)
    sid = _store(image_np, depth_result)

    # 生成响应数据
    original_b64   = numpy_to_base64(image_np)
    depth_norm_b64 = numpy_to_base64(
        np.stack([depth_result["depth_norm"]] * 3, axis=-1)
    )

    logger.info(f"Depth done. session={sid}, shape=({H},{W})")

    # ── 异步保存历史记录到 OSS + MySQL ────────────────────────────
    # 默认渲染参数：视差强度 intensity=0.04（与前端 Depth3DViewer 默认值一致）
    # 此处仅记录初始快照，用户调整后可通过前端再次保存覆盖
    from flask import current_app
    _save_history_async(
        app          = current_app._get_current_object(),
        user_id      = g.current_user.id if g.current_user else None,
        original_b64 = original_b64,
        depth_b64    = depth_norm_b64,
        model_key    = model_key,
        model_label  = depth_result["model_label"],
        width        = W,
        height       = H,
        render_config = {"intensity": 0.04},  # 初始默认渲染参数
    )

    return jsonify({
        "session_id":  sid,
        "original":    original_b64,
        "depth_color": numpy_to_base64(depth_result["depth_color"]),
        "depth_norm":  depth_norm_b64,
        "width":       W,
        "height":      H,
        "model_key":   depth_result["model_key"],
        "model_label": depth_result["model_label"],
    })


@api_bp.post("/generate")
@jwt_required
def generate():
    data  = request.get_json(force=True)
    sid   = data.get("session_id", "")
    shift = float(np.clip(float(data.get("shift", 0.05)), -0.15, 0.15))
    session = _get(sid)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    syn  = get_synthesizer()
    view = syn.synthesize(session["image"], session["depth_raw"], shift=shift)
    return jsonify({"image": numpy_to_base64(view), "shift": shift})


@api_bp.post("/stereo")
@jwt_required
def stereo():
    data  = request.get_json(force=True)
    sid   = data.get("session_id", "")
    shift = float(np.clip(abs(float(data.get("shift", 0.05))), 0.01, 0.15))
    session = _get(sid)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    syn = get_synthesizer()
    left, right = syn.generate_stereo_pair(session["image"], session["depth_raw"], shift)
    anaglyph    = syn.generate_anaglyph(session["image"], session["depth_raw"], shift)
    sbs         = syn.generate_side_by_side(session["image"], session["depth_raw"], shift)
    return jsonify({
        "left":         numpy_to_base64(left),
        "right":        numpy_to_base64(right),
        "anaglyph":     numpy_to_base64(anaglyph),
        "side_by_side": numpy_to_base64(sbs),
        "shift":        shift,
    })


@api_bp.post("/multiview")
@jwt_required
def multiview():
    data      = request.get_json(force=True)
    sid       = data.get("session_id", "")
    num_views = int(np.clip(int(data.get("num_views", 7)), 3, 15))
    max_shift = float(np.clip(float(data.get("max_shift", 0.08)), 0.01, 0.15))
    session = _get(sid)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    syn   = get_synthesizer()
    views = syn.generate_multi_view(
        session["image"], session["depth_raw"],
        num_views=num_views, max_shift=max_shift
    )
    shifts = list(np.linspace(-max_shift, max_shift, num_views))
    return jsonify({
        "views":  [numpy_to_base64(v) for v in views],
        "shifts": [round(float(s), 4) for s in shifts],
    })


# ══════════════════════════════════════════════════════════════════
# 分享链接
# ══════════════════════════════════════════════════════════════════

@api_bp.post("/share/create")
@jwt_required
def share_create():
    """
    生成分享链接（登录用户）。
    接收 conversion_id 和有效时长（小时），创建 ShareLink 记录。
    返回 token 和完整分享路径。
    """
    import uuid as _uuid
    data = request.get_json(force=True) or {}
    conversion_id = data.get('conversion_id')
    hours = int(data.get('hours', 24))
    if not conversion_id:
        return jsonify({'error': '缺少 conversion_id'}), 400
    if hours not in (1, 6, 24, 72, 168):
        return jsonify({'error': '无效的时长参数'}), 400
    rec = db.session.get(ConversionHistory, conversion_id)
    if not rec or rec.user_id != g.current_user.id:
        return jsonify({'error': '转换记录不存在'}), 404
    token     = _uuid.uuid4().hex
    expire_at = datetime.utcnow() + timedelta(hours=hours)
    link = ShareLink(share_token=token, conversion_id=conversion_id, expire_at=expire_at)
    db.session.add(link)
    db.session.commit()
    return jsonify({
        'token':     token,
        'share_url': f'/share/{token}',
        'expire_at': expire_at.strftime('%Y-%m-%d %H:%M UTC'),
    })


@api_bp.get("/share/view/<string:token>")
def share_view(token):
    """
    访客端：Token 校验与数据获取（无需登录）。

    安全策略：
      - 返回原图 URL（供 DIBR 渲染着色），但不在 UI 上暴露下载入口
      - 返回深度图 URL（位移层）
      - 不返回任何编辑/修改接口
    """
    link = ShareLink.query.filter_by(share_token=token).first()
    if not link:
        return jsonify({'error': 'TOKEN_NOT_FOUND', 'message': '链接不存在'}), 404
    if link.is_expired():
        return jsonify({'error': 'TOKEN_EXPIRED', 'message': '链接已过期'}), 410
    rec = link.conversion
    render_cfg = rec.render_config or {}
    return jsonify({
        'color_url':    rec.original_url,   # 原图作为 DIBR 颜色层
        'depth_url':    rec.depth_url,      # 深度图作为位移层
        'model_label':  rec.model_label or '',
        'image_width':  rec.image_width,
        'image_height': rec.image_height,
        'intensity':    render_cfg.get('intensity', 0.04),
        'expire_at':    link.expire_at.strftime('%Y-%m-%d %H:%M UTC'),
    })


# ══════════════════════════════════════════════════════════════════
# 图片跨域代理
# ══════════════════════════════════════════════════════════════════

@api_bp.get("/proxy-image")
def proxy_image():
    """
    图片跨域代理 — 供前端 ExportButton 绕过浏览器 CORS 限制使用。
    仅允许 http/https 协议 URL，超时 10 秒。
    """
    import requests as req_lib
    url = request.args.get('url', '').strip()
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'invalid url'}), 400
    try:
        resp = req_lib.get(url, timeout=10, stream=True)
        content_type = resp.headers.get('Content-Type', 'image/png')
        from flask import Response
        return Response(
            resp.content,
            status=resp.status_code,
            headers={
                'Content-Type': content_type,
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=3600',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 502

@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"})
