"""
MonoVista 模型下载脚本

用法:
    python download_models.py              # 下载所有模型
    python download_models.py dav2-small   # 只下载指定模型

模型保存位置:
    models_cache/hf/<key>/     -- Transformers 模型（可离线加载）
    models_cache/midas/<key>.pt -- MiDaS .pt 权重文件
"""

import sys
import os
from pathlib import Path

# !! 必须在 torch / transformers import 之前设置环境变量 !!
PROJECT_ROOT = Path(__file__).parent
HF_DIR    = PROJECT_ROOT / "models_cache" / "hf"
MIDAS_DIR = PROJECT_ROOT / "models_cache" / "midas"
HF_DIR.mkdir(parents=True, exist_ok=True)
MIDAS_DIR.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"]               = str(PROJECT_ROOT / "models_cache" / "huggingface")
os.environ["TORCH_HOME"]            = str(PROJECT_ROOT / "models_cache" / "torch")
os.environ["TRANSFORMERS_CACHE"]    = str(PROJECT_ROOT / "models_cache" / "transformers")
os.environ["HUGGINGFACE_HUB_CACHE"] = str(PROJECT_ROOT / "models_cache" / "huggingface" / "hub")

import torch
from loguru import logger

MODEL_REGISTRY = {
    "dav2-small":   {"backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Small-hf"},
    "dav2-base":    {"backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Base-hf"},
    "dav2-large":   {"backend": "transformers", "model_id": "depth-anything/Depth-Anything-V2-Large-hf"},
    "midas-large":  {"backend": "torch_hub",    "model_id": "DPT_Large"},
    "midas-hybrid": {"backend": "torch_hub",    "model_id": "DPT_Hybrid"},
    "midas-small":  {"backend": "torch_hub",    "model_id": "MiDaS_small"},
    "mono2-stereo": {"backend": "transformers", "model_id": "Mxbonn/monodepth2-mono_stereo_640x192"},
}


def download_transformers(key: str, model_id: str):
    local_path = HF_DIR / key
    if (local_path / "config.json").exists():
        logger.info(f"[{key}] 已存在于本地，跳过")
        return
    logger.info(f"[{key}] 下载 {model_id} ...")
    from transformers import AutoModelForDepthEstimation, AutoImageProcessor
    processor = AutoImageProcessor.from_pretrained(model_id)
    model     = AutoModelForDepthEstimation.from_pretrained(model_id)
    local_path.mkdir(parents=True, exist_ok=True)
    processor.save_pretrained(str(local_path))
    model.save_pretrained(str(local_path))
    logger.success(f"[{key}] 已保存到 {local_path}")


def download_midas(key: str, model_type: str):
    pt_path = MIDAS_DIR / f"{key}.pt"
    if pt_path.exists():
        logger.info(f"[{key}] 已存在于本地 ({pt_path.name})，跳过")
        return
    logger.info(f"[{key}] 下载 MiDaS {model_type} ...")
    model = torch.hub.load("intel-isl/MiDaS", model_type, trust_repo=True)
    torch.save(model.state_dict(), str(pt_path))
    logger.success(f"[{key}] 已保存到 {pt_path}")


def download(key: str):
    info = MODEL_REGISTRY.get(key)
    if info is None:
        logger.error(f"未知模型 key: {key}，可用: {list(MODEL_REGISTRY)}")
        return
    if info["backend"] == "transformers":
        download_transformers(key, info["model_id"])
    else:
        download_midas(key, info["model_id"])


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(MODEL_REGISTRY.keys())
    logger.info(f"准备下载模型: {targets}")
    logger.info(f"HF 模型保存至:    {HF_DIR}")
    logger.info(f"MiDaS 保存至:     {MIDAS_DIR}")
    logger.info(f"HF_HOME:          {os.environ['HF_HOME']}")
    logger.info(f"TORCH_HOME:       {os.environ['TORCH_HOME']}")
    print()
    for k in targets:
        try:
            download(k)
        except Exception as e:
            logger.error(f"[{k}] 下载失败: {e}")
    print()
    logger.success("全部完成！")
