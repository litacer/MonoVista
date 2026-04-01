"""
audit_utils.py — 操作日志审计工具

使用方式：
    from backend.utils.audit_utils import audit_action

    @api_bp.post("/upload")
    @jwt_required
    @audit_action(action="upload_image", object_type="image")
    def upload():
        ...

装饰器会在被装饰函数成功返回后，异步将日志写入 audit_logs 表。
日志记录失败时仅打 warning，不影响主接口响应。

依赖：
    pip install user-agents
"""
from functools import wraps
from datetime import datetime
import threading
from flask import request, g
from loguru import logger

try:
    from user_agents import parse as ua_parse
except ImportError:
    ua_parse = None


def _get_client_ip() -> str:
    """优先读取反向代理注入的真实 IP，降级到 remote_addr。"""
    for header in ("X-Forwarded-For", "X-Real-IP"):
        val = request.headers.get(header)
        if val:
            return val.split(",")[0].strip()
    return request.remote_addr or ""


def _parse_ua(ua_string: str) -> dict:
    """
    使用 user-agents 库解析 User-Agent 字符串。
    返回 os / browser / device 三个字段。
    """
    if ua_parse is None:
        return {"os": "", "browser": "", "device": ""}
    ua = ua_parse(ua_string)
    os_str = f"{ua.os.family} {ua.os.version_string}".strip()
    browser_str = f"{ua.browser.family} {ua.browser.version_string}".strip()
    if ua.is_mobile:
        device = "Mobile"
    elif ua.is_tablet:
        device = "Tablet"
    elif ua.is_bot:
        device = "Bot"
    else:
        device = "PC"
    return {"os": os_str, "browser": browser_str, "device": device}


def _write_log(app, user_id, action, object_type, object_id, ip, ua_info):
    """
    在独立线程中将日志持久化到数据库。
    使用 app.app_context() 保证 SQLAlchemy 会话安全。
    """
    from backend.models.user import db, AuditLog
    try:
        with app.app_context():
            log = AuditLog(
                user_id     = user_id,
                action      = action,
                object_type = object_type,
                object_id   = str(object_id) if object_id else None,
                ip          = ip,
                os          = ua_info.get("os", ""),
                browser     = ua_info.get("browser", ""),
                device      = ua_info.get("device", ""),
                created_at  = datetime.utcnow(),
            )
            db.session.add(log)
            db.session.commit()
            logger.debug(f"[audit] {action} uid={user_id} ip={ip}")
    except Exception as e:
        logger.warning(f"[audit] Failed to write log: {e}")


def audit_action(action: str, object_type: str = "", object_id_key: str = None):
    """
    通用审计装饰器。

    参数：
        action        - 动作描述，如 'upload_image' / 'save_depth'
        object_type   - 操作对象类型，如 'image' / 'depth_map'
        object_id_key - 从响应 JSON 中提取 object_id 的键名（可选）

    行为：
        1. 调用被装饰函数
        2. 若函数正常返回（HTTP 2xx），在后台线程异步写入日志
        3. 若函数抛出异常，直接透传，不写日志

    与业务代码高度解耦：
        - 不修改请求/响应内容
        - 日志写入失败不影响主流程
        - 利用线程异步，不阻塞接口响应
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import current_app
            app = current_app._get_current_object()

            # 提前捕获请求上下文信息（线程切换后无法访问）
            ip = _get_client_ip()
            ua_string = request.headers.get("User-Agent", "")
            ua_info = _parse_ua(ua_string)
            user_id = getattr(g, "current_user", None)
            user_id = user_id.id if user_id else None

            # 执行原始接口函数
            response = fn(*args, **kwargs)

            # 仅在成功时记录日志（状态码 2xx）
            status = response[1] if isinstance(response, tuple) else 200
            if status < 300:
                # 从响应 JSON 中提取 object_id（可选）
                obj_id = None
                if object_id_key:
                    try:
                        resp_json = response[0].get_json() if isinstance(response, tuple) else response.get_json()
                        obj_id = resp_json.get(object_id_key) if resp_json else None
                    except Exception:
                        pass

                # 异步写日志，不阻塞响应
                threading.Thread(
                    target=_write_log,
                    args=(app, user_id, action, object_type, obj_id, ip, ua_info),
                    daemon=True,
                ).start()

            return response
        return wrapper
    return decorator
