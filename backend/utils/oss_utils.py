"""
oss_utils.py — 阿里云 OSS 文件上传工具

依赖：oss2
安装：pip install oss2

环境变量（在 .env 中配置）：
    OSS_ACCESS_KEY_ID      - 阿里云 AccessKeyId
    OSS_ACCESS_KEY_SECRET  - 阿里云 AccessKeySecret
    OSS_ENDPOINT           - OSS Endpoint，如 oss-cn-hangzhou.aliyuncs.com
    OSS_BUCKET_NAME        - Bucket 名称
"""
import os
import uuid
from loguru import logger

try:
    import oss2
except ImportError:
    oss2 = None  # 未安装时给出友好提示，不崩溃


def _get_bucket() -> "oss2.Bucket":
    """初始化并返回 OSS Bucket 实例。"""
    if oss2 is None:
        raise RuntimeError(
            "oss2 is not installed. Run: pip install oss2"
        )
    access_key_id     = os.getenv("OSS_ACCESS_KEY_ID", "")
    access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    endpoint          = os.getenv("OSS_ENDPOINT", "")
    bucket_name       = os.getenv("OSS_BUCKET_NAME", "")

    if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
        raise RuntimeError(
            "OSS config incomplete. Set OSS_ACCESS_KEY_ID, "
            "OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME in .env"
        )

    auth = oss2.Auth(access_key_id, access_key_secret)
    return oss2.Bucket(auth, endpoint, bucket_name)


# Content-Type 映射
_MIME_EXT = {
    "image/jpeg":  ".jpg",
    "image/png":   ".png",
    "image/gif":   ".gif",
    "image/webp":  ".webp",
}


def upload_file_to_oss(file_obj, folder: str = "avatars") -> str:
    """
    将文件对象上传至阿里云 OSS。

    参数：
        file_obj  - werkzeug FileStorage 对象（request.files 中的文件）
        folder    - OSS 中的目录前缀，默认 'avatars'

    返回：
        可公开访问的完整 URL 字符串

    异常：
        RuntimeError  - OSS 配置不完整或 oss2 未安装
        oss2.exceptions.OssError - 上传失败
    """
    bucket = _get_bucket()

    content_type = getattr(file_obj, "content_type", "image/jpeg") or "image/jpeg"
    ext = _MIME_EXT.get(content_type, ".jpg")

    # 生成 UUID 文件名防止冲突，格式：avatars/<uuid>.ext
    object_key = f"{folder.strip('/')}/{uuid.uuid4().hex}{ext}"

    file_obj.stream.seek(0)
    file_bytes = file_obj.stream.read()

    logger.info(f"[OSS] Uploading to {object_key}, size={len(file_bytes)} bytes")

    result = bucket.put_object(
        object_key,
        file_bytes,
        headers={"Content-Type": content_type},
    )

    if result.status != 200:
        raise RuntimeError(f"OSS upload failed, HTTP {result.status}")

    endpoint  = os.getenv("OSS_ENDPOINT", "")
    bucket_name = os.getenv("OSS_BUCKET_NAME", "")

    # 拼接公开访问 URL：https://<bucket>.<endpoint>/<object_key>
    url = f"https://{bucket_name}.{endpoint}/{object_key}"
    logger.info(f"[OSS] Upload success: {url}")
    return url


def delete_file_from_oss(url: str) -> None:
    """
    根据公开 URL 删除 OSS 上的文件（用于替换旧头像时清理）。
    失败时仅打 warning，不抛异常。
    """
    endpoint    = os.getenv("OSS_ENDPOINT", "")
    bucket_name = os.getenv("OSS_BUCKET_NAME", "")
    prefix = f"https://{bucket_name}.{endpoint}/"
    if not url.startswith(prefix):
        return
    object_key = url[len(prefix):]
    try:
        bucket = _get_bucket()
        bucket.delete_object(object_key)
        logger.info(f"[OSS] Deleted {object_key}")
    except Exception as e:
        logger.warning(f"[OSS] Failed to delete {object_key}: {e}")
