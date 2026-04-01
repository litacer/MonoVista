from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(80), nullable=False, default="新用户")
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    avatar_url = db.Column(db.Text, nullable=True)
    signature = db.Column(db.String(100), nullable=True, default="")
    phone = db.Column(db.String(20), nullable=True)
    level = db.Column(db.String(20), nullable=False, default="Lv1")
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "signature": self.signature or "",
            "phone": self.phone or "",
            "level": self.level,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    """
    audit_logs 表 — 操作行为审计

    字段说明：
        user_id       关联用户 ID（外键）
        action        动作描述，如 'upload_image' / 'save_depth' / 'update_avatar'
        object_type   操作对象类型，如 'image' / 'depth_map' / 'avatar'
        object_id     操作对象 ID（可为空，如 session_id）
        ip            客户端 IP
        os            操作系统（由 user-agents 解析）
        browser       浏览器及版本（由 user-agents 解析）
        device        设备类型（Mobile / PC 等）
        created_at    操作时间戳（UTC，自动生成）
    """
    __tablename__ = "audit_logs"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action      = db.Column(db.String(64), nullable=False)
    object_type = db.Column(db.String(64), nullable=True)
    object_id   = db.Column(db.String(128), nullable=True)
    ip          = db.Column(db.String(64), nullable=True)
    os          = db.Column(db.String(128), nullable=True)
    browser     = db.Column(db.String(128), nullable=True)
    device      = db.Column(db.String(64), nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id":          self.id,
            "user_id":     self.user_id,
            "action":      self.action,
            "object_type": self.object_type,
            "object_id":   self.object_id,
            "ip":          self.ip,
            "os":          self.os,
            "browser":     self.browser,
            "device":      self.device,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


class ModelRegistry(db.Model):
    """
    model_registry 表 — 模型仓库

    字段：
      name          模型名称（如 Monodepth2）
      model_key     推理系统内使用的模型 key（与 depth_estimator 的 key 对齐）
      framework     框架类型：PyTorch / ONNX
      oss_weight_path 权重在 OSS 的路径（或 URL）
      version       版本号
      status        Active / Inactive
      infer_latency_ms 平均推理耗时（ms）
      vram_mb       显存占用（MB）
    """
    __tablename__ = "model_registry"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(120), nullable=False)
    display_name    = db.Column(db.String(120), nullable=True)
    description     = db.Column(db.Text, nullable=True)
    is_visible      = db.Column(db.Boolean, nullable=False, default=True)
    model_key       = db.Column(db.String(64), nullable=False, unique=True, index=True)
    framework       = db.Column(db.String(20), nullable=False, default="PyTorch")
    oss_weight_path = db.Column(db.Text, nullable=True)
    version         = db.Column(db.String(32), nullable=False, default="v1.0.0")
    status          = db.Column(db.String(16), nullable=False, default="Inactive")
    infer_latency_ms = db.Column(db.Float, nullable=True)
    vram_mb         = db.Column(db.Float, nullable=True)
    created_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name or self.name,
            "description": self.description or "",
            "is_visible": bool(self.is_visible),
            "model_key": self.model_key,
            "framework": self.framework,
            "oss_weight_path": self.oss_weight_path,
            "version": self.version,
            "status": self.status,
            "infer_latency_ms": self.infer_latency_ms,
            "vram_mb": self.vram_mb,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Announcement(db.Model):
    """
    announcements 表 — 系统公告

    字段说明：
        title       公告标题（最多 200 字）
        content     富文本内容（HTML，经后端 XSS 过滤后存储）
        type        公告类型：info / warning / success
        is_active   是否激活（True = 对用户展示）
        create_time 创建时间（UTC，自动生成）
    """
    __tablename__ = "announcements"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    content     = db.Column(db.Text(length=2**32 - 1), nullable=False, default="")  # LONGTEXT
    type        = db.Column(db.String(20), nullable=False, default="info")  # info/warning/success
    is_active   = db.Column(db.Boolean, nullable=False, default=True)
    create_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id":          self.id,
            "title":       self.title,
            "content":     self.content,
            "type":        self.type,
            "is_active":   bool(self.is_active),
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class ConversionHistory(db.Model):
    """
    conversion_history 表 — 用户转换历史记录

    字段说明：
        user_id         关联用户 ID（外键）
        original_url    原始图像在 OSS 上的访问 URL
        depth_url       深度图在 OSS 上的访问 URL（归一化灰度图）
        thumbnail_url   缩略图 URL（使用 original_url 即可，前端按需裁剪）
        model_key       推理时使用的深度估计模型标识，如 'dav2-small'
        model_label     模型人类可读名称，如 'DAV2 Small'
        image_width     原始图像宽度（像素）
        image_height    原始图像高度（像素）
        render_config   JSON 字段，存储 3D 渲染参数快照，结构如下：
                        {
                          "intensity": 0.04,    // 视差强度系数
                          "smooth_k":  0.06     // 鼠标平滑系数（保留扩展）
                        }
        created_at      记录创建时间（UTC，自动生成）
    """
    __tablename__ = "conversion_history"

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    original_url  = db.Column(db.Text, nullable=False)    # 原图 OSS URL
    depth_url     = db.Column(db.Text, nullable=False)    # 深度图 OSS URL
    thumbnail_url = db.Column(db.Text, nullable=True)     # 缩略图 URL（可复用 original_url）
    model_key     = db.Column(db.String(64), nullable=True)   # 模型标识
    model_label   = db.Column(db.String(128), nullable=True)  # 模型名称
    image_width   = db.Column(db.Integer, nullable=True)  # 图像宽度
    image_height  = db.Column(db.Integer, nullable=True)  # 图像高度
    render_config = db.Column(db.JSON, nullable=True)     # 3D 渲染参数 JSON
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id":            self.id,
            "user_id":       self.user_id,
            "original_url":  self.original_url,
            "depth_url":     self.depth_url,
            "thumbnail_url": self.thumbnail_url or self.original_url,
            "model_key":     self.model_key,
            "model_label":   self.model_label,
            "image_width":   self.image_width,
            "image_height":  self.image_height,
            "render_config": self.render_config or {},
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }


class ShareLink(db.Model):
    """
    share_links 表 — 受限公开分享链接

    安全设计：
        - share_token 使用 uuid4，128 位随机性，暴力枚举不可行
        - 接口只返回深度图 URL 和渲染参数，不返回原图物理路径
        - expire_at 过期后服务端拒绝返回数据
        - conversion_id 外键 CASCADE，删除历史时分享链接自动失效
    """
    __tablename__ = "share_links"

    id            = db.Column(db.Integer, primary_key=True)
    share_token   = db.Column(db.String(64), unique=True, nullable=False, index=True)
    conversion_id = db.Column(db.Integer, db.ForeignKey("conversion_history.id", ondelete="CASCADE"), nullable=False)
    expire_at     = db.Column(db.DateTime, nullable=False)
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversion = db.relationship("ConversionHistory", backref="share_links", lazy="joined")

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expire_at

    def to_dict(self):
        return {
            "id":            self.id,
            "share_token":   self.share_token,
            "conversion_id": self.conversion_id,
            "expire_at":     self.expire_at.isoformat() if self.expire_at else None,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }
