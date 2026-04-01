"""
多模型深度估计管理器

加载顺序：
  1. Transformers 模型：优先从 models_cache/hf/<key>/ 本地目录加载
  2. MiDaS 模型：优先从 models_cache/midas/<key>.pt 本地文件加载
  本地不存在时自动联网下载并保存。

提前下载：python download_models.py
"""

import io
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# !! 必须在 torch / transformers import 之前设置，否则它们会读 C 盘默认缓存 !!
PROJECT_ROOT = Path(__file__).parent.parent.parent
HF_DIR    = PROJECT_ROOT / "models_cache" / "hf"
MIDAS_DIR = PROJECT_ROOT / "models_cache" / "midas"
HF_DIR.mkdir(parents=True, exist_ok=True)
MIDAS_DIR.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"]            = str(PROJECT_ROOT / "models_cache" / "huggingface")
os.environ["TORCH_HOME"]         = str(PROJECT_ROOT / "models_cache" / "torch")
os.environ["TRANSFORMERS_CACHE"] = str(PROJECT_ROOT / "models_cache" / "transformers")
os.environ["HUGGINGFACE_HUB_CACHE"] = str(PROJECT_ROOT / "models_cache" / "huggingface" / "hub")

import torch
import numpy as np
from PIL import Image
import cv2
from loguru import logger
from typing import Union

MODEL_REGISTRY = {
    "dav2-small":  {"label": "Depth Anything V2 Small",       "backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Small-hf",         "description": "速度最快，适合实时预览",     "speed": "fast"},
    "dav2-base":   {"label": "Depth Anything V2 Base",        "backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Base-hf",          "description": "速度与精度均衡",           "speed": "medium"},
    "dav2-large":  {"label": "Depth Anything V2 Large",       "backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Large-hf",         "description": "精度最高，推荐 GPU",        "speed": "slow"},
    "midas-large": {"label": "MiDaS DPT-Large",              "backend": "torch_hub",    "model_id": "DPT_Large",                                         "description": "Intel MiDaS，精度高",      "speed": "medium"},
    "midas-hybrid":{"label": "MiDaS DPT-Hybrid",             "backend": "torch_hub",    "model_id": "DPT_Hybrid",                                        "description": "MiDaS 混合架构，速度快",   "speed": "fast"},
    "midas-small": {"label": "MiDaS v2.1 Small",             "backend": "torch_hub",    "model_id": "MiDaS_small",                                       "description": "轻量版，CPU 可流畅运行",  "speed": "fast"},
    "mono2-stereo":{"label": "Monodepth2 (Stereo 640x192)",  "backend": "transformers", "model_id": "Mxbonn/monodepth2-mono_stereo_640x192",              "description": "经典自监督，KITTI 训练",  "speed": "fast"},
}


class DepthEstimator:
    def __init__(self, model_key: str = "dav2-small", device: str = None):
        if model_key not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model key: {model_key}")
        self.model_key = model_key
        self.info      = MODEL_REGISTRY[model_key]
        self.device    = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._pipe             = None
        self._midas            = None
        self._midas_transforms = None
        logger.info(f"DepthEstimator: key={model_key}, device={self.device}")

    def load(self):
        if self.info["backend"] == "transformers":
            self._load_transformers()
        else:
            self._load_midas()
        logger.info(f"[{self.info['label']}] ready on {self.device}")
        return self

    def _load_transformers(self):
        from transformers import pipeline as hf_pipeline
        from transformers import AutoModelForDepthEstimation, AutoImageProcessor
        key        = self.model_key
        model_id   = self.info["model_id"]
        local_path = HF_DIR / key
        if (local_path / "config.json").exists():
            logger.info(f"[{key}] Loading from local: {local_path}")
            model_src = str(local_path)
        else:
            logger.info(f"[{key}] Downloading {model_id} ...")
            processor = AutoImageProcessor.from_pretrained(model_id)
            model     = AutoModelForDepthEstimation.from_pretrained(model_id)
            local_path.mkdir(parents=True, exist_ok=True)
            processor.save_pretrained(str(local_path))
            model.save_pretrained(str(local_path))
            logger.info(f"[{key}] Saved to {local_path}")
            model_src = str(local_path)
        self._pipe = hf_pipeline(
            task="depth-estimation",
            model=model_src,
            device=0 if self.device == "cuda" else -1,
        )

    def _load_midas(self):
        key        = self.model_key
        model_type = self.info["model_id"]
        pt_path    = MIDAS_DIR / f"{key}.pt"
        if pt_path.exists():
            logger.info(f"[{key}] Loading weights from local: {pt_path}")
            model = torch.hub.load("intel-isl/MiDaS", model_type, trust_repo=True, pretrained=False)
            state = torch.load(str(pt_path), map_location=self.device)
            model.load_state_dict(state)
        else:
            logger.info(f"[{key}] Downloading MiDaS {model_type} ...")
            model = torch.hub.load("intel-isl/MiDaS", model_type, trust_repo=True)
            torch.save(model.state_dict(), str(pt_path))
            logger.info(f"[{key}] Saved to {pt_path}")
        model.to(self.device).eval()
        self._midas = model
        transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
        self._midas_transforms = (
            transforms.dpt_transform if model_type in ("DPT_Large", "DPT_Hybrid")
            else transforms.small_transform
        )

    def estimate(self, image: Union[Image.Image, np.ndarray, bytes]) -> dict:
        pil_image = self._to_pil(image)
        if self.info["backend"] == "transformers":
            depth_raw = self._infer_transformers(pil_image)
        else:
            depth_raw = self._infer_midas(pil_image)
        H, W = np.array(pil_image).shape[:2]
        if depth_raw.shape != (H, W):
            depth_raw = cv2.resize(depth_raw, (W, H), interpolation=cv2.INTER_LINEAR)
        d_min, d_max = depth_raw.min(), depth_raw.max()
        if d_max - d_min > 1e-6:
            depth_norm = ((depth_raw - d_min) / (d_max - d_min) * 255).astype(np.uint8)
        else:
            depth_norm = np.zeros_like(depth_raw, dtype=np.uint8)
        depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_INFERNO)
        depth_color = cv2.cvtColor(depth_color, cv2.COLOR_BGR2RGB)
        return {
            "depth_raw":    depth_raw,
            "depth_norm":   depth_norm,
            "depth_color":  depth_color,
            "original_size": pil_image.size,
            "model_key":    self.model_key,
            "model_label":  self.info["label"],
        }

    def _infer_transformers(self, pil_image: Image.Image) -> np.ndarray:
        result = self._pipe(pil_image)
        return np.array(result["depth"], dtype=np.float32)

    def _infer_midas(self, pil_image: Image.Image) -> np.ndarray:
        img_np = np.array(pil_image)
        input_batch = self._midas_transforms(img_np).to(self.device)
        with torch.no_grad():
            prediction = self._midas(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img_np.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        return prediction.cpu().numpy().astype(np.float32)

    @staticmethod
    def _to_pil(image) -> Image.Image:
        if isinstance(image, bytes):
            return Image.open(io.BytesIO(image)).convert("RGB")
        elif isinstance(image, np.ndarray):
            return Image.fromarray(image.astype(np.uint8)).convert("RGB")
        elif isinstance(image, Image.Image):
            return image.convert("RGB")
        raise TypeError(f"Unsupported type: {type(image)}")


# 模型池
_pool:   dict = {}
_device: str  = None

# ========================= 模型运行时（热切换） =========================
_runtime_lock = threading.RLock()
_runtime_cond = threading.Condition(_runtime_lock)
_runtime_active_requests = 0
_runtime_switching = False
_runtime_state = {
    "active_model_key": None,
    "precision": "fp32",   # fp32 / fp16
    "device": None,         # cpu / cuda
    "last_switch_at": None,
    "loading": False,
    "message": "",
}


def _normalize_device(device: str) -> str:
    d = (device or "").lower()
    if d in ("gpu", "cuda"):
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cpu"


@contextmanager
def inference_guard():
    """
    推理请求守卫（线程安全）：

    1) 每个推理请求进入时，active_requests +1。
    2) 当触发模型热切换时，会先置 switching=True，阻止新请求继续进入；
       然后等待 active_requests 归零，再执行权重替换。
    3) 推理结束后 active_requests -1，并通知等待中的切换线程。

    这保证了：
    - 不会在“半加载模型”上执行推理
    - 不会出现模型对象并发写入导致的崩溃

    平滑过渡策略建议（高可用）：
    - 当前实现是“短暂停流 + 等待在途请求结束 + 原子替换”。
    - 若追求更高可用，可扩展为“双缓冲（A/B）”：
      新模型在后台预热成功后切换指针，老模型延迟回收，做到近似无感切换。
    """
    with _runtime_cond:
        while _runtime_switching:
            _runtime_cond.wait()
        global _runtime_active_requests
        _runtime_active_requests += 1
    try:
        yield
    finally:
        with _runtime_cond:
            _runtime_active_requests -= 1
            if _runtime_active_requests <= 0:
                _runtime_cond.notify_all()


def get_runtime_state() -> dict:
    with _runtime_lock:
        return dict(_runtime_state)


def configure_runtime(device: str = None, precision: str = None) -> dict:
    """更新运行配置（不触发权重切换）。"""
    with _runtime_lock:
        if device:
            _runtime_state["device"] = _normalize_device(device)
        if precision:
            p = (precision or "").lower()
            if p in ("fp16", "fp32"):
                _runtime_state["precision"] = p
        _runtime_state["message"] = "runtime config updated"
        return dict(_runtime_state)


def activate_model(model_key: str, device: str = None, precision: str = None) -> dict:
    """
    热切换激活模型（线程安全实现）。

    切换流程：
      A. 标记 switching=True，阻止新推理进入
      B. 等待在途请求 active_requests 归零（平滑排空）
      C. 加载/切换目标模型并更新运行时状态
      D. 释放 switching，恢复请求处理

    注意：为简化落地，当前使用“停流排空 + 原子切换”。
    若后续吞吐进一步提高，可升级成“双缓冲热切换”。
    """
    if model_key not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model key: {model_key}")

    chosen_device = _normalize_device(device or _runtime_state.get("device") or _device)
    chosen_precision = (precision or _runtime_state.get("precision") or "fp32").lower()
    if chosen_precision not in ("fp16", "fp32"):
        chosen_precision = "fp32"

    with _runtime_cond:
        global _runtime_switching
        _runtime_switching = True
        _runtime_state["loading"] = True
        _runtime_state["message"] = f"switching to {model_key}..."
        while _runtime_active_requests > 0:
            _runtime_cond.wait(timeout=0.05)

    try:
        est = DepthEstimator(model_key=model_key, device=chosen_device)
        est.load()

        # FP16 仅在 CUDA 下有效，CPU 自动回退到 FP32
        if chosen_precision == "fp16" and chosen_device == "cuda":
            if est._midas is not None:
                est._midas.half()

        _pool[model_key] = est

        with _runtime_lock:
            _runtime_state["active_model_key"] = model_key
            _runtime_state["device"] = chosen_device
            _runtime_state["precision"] = chosen_precision if chosen_device == "cuda" else "fp32"
            _runtime_state["last_switch_at"] = int(time.time())
            _runtime_state["loading"] = False
            _runtime_state["message"] = f"active model: {model_key}"
            return dict(_runtime_state)
    finally:
        with _runtime_cond:
            _runtime_switching = False
            _runtime_state["loading"] = False
            _runtime_cond.notify_all()



def init_pool(default_key: str = "dav2-small", device: str = None):
    global _device
    _device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Model pool init: default={default_key}, device={_device}")

    # 初始化运行时状态
    with _runtime_lock:
        _runtime_state["device"] = _normalize_device(_device)
        _runtime_state["precision"] = "fp16" if _runtime_state["device"] == "cuda" else "fp32"

    # 默认模型走统一激活逻辑，确保运行时状态与模型池一致
    activate_model(default_key, device=_runtime_state["device"], precision=_runtime_state["precision"])


def _get_or_load(model_key: str) -> DepthEstimator:
    if model_key not in _pool:
        est = DepthEstimator(model_key=model_key, device=_runtime_state.get("device") or _device)
        est.load()
        _pool[model_key] = est
    return _pool[model_key]


def get_estimator(model_key: str = None) -> DepthEstimator:
    # 若未显式指定 model_key，始终返回当前激活模型（用于线上推理）
    key = model_key or (_runtime_state.get("active_model_key") or "dav2-small")
    return _get_or_load(key)


def list_models() -> list:
    return [
        {
            "key":         k,
            "label":       v["label"],
            "description": v["description"],
            "speed":       v["speed"],
            "loaded":      k in _pool,
            "local_hf":    (HF_DIR / k / "config.json").exists(),
            "local_pt":    (MIDAS_DIR / f"{k}.pt").exists(),
        }
        for k, v in MODEL_REGISTRY.items()
    ]
