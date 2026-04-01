"""
图像工具函数
"""
import io
import base64
import numpy as np
from PIL import Image
import cv2


def numpy_to_base64(image: np.ndarray, fmt: str = "PNG") -> str:
    pil = Image.fromarray(image.astype(np.uint8))
    buffer = io.BytesIO()
    pil.save(buffer, format=fmt)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = fmt.lower().replace("jpeg", "jpg")
    return f"data:image/{mime};base64,{b64}"


def bytes_to_numpy(image_bytes: bytes) -> np.ndarray:
    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(pil, dtype=np.uint8)


def resize_keep_aspect(image: np.ndarray, max_size: int = 1024) -> np.ndarray:
    H, W = image.shape[:2]
    scale = min(max_size / max(H, W), 1.0)
    if scale == 1.0:
        return image
    new_w, new_h = int(W * scale), int(H * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def depth_to_colormap(depth_norm: np.ndarray) -> np.ndarray:
    color_bgr = cv2.applyColorMap(depth_norm, cv2.COLORMAP_INFERNO)
    return cv2.cvtColor(color_bgr, cv2.COLOR_BGR2RGB)
