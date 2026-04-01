"""API 集成测试脚本
在后端运行后执行: python test_api.py
"""
import requests, sys, io, numpy as np
from PIL import Image

BASE = "http://localhost:5000/api"

def make_test_image():
    arr = np.zeros((100,100,3), dtype=np.uint8)
    for i in range(100):
        arr[i,:,0] = i*2
        arr[:,i,2] = i*2
    arr[:,:,1] = 128
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG")
    return buf.getvalue()

def test_health():
    print("[1] 健康检查 ...", end=" ")
    r = requests.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 200
    print("OK", r.json())

def test_models():
    print("[2] 模型列表 ...", end=" ")
    r = requests.get(f"{BASE}/models", timeout=5)
    assert r.status_code == 200
    data = r.json()
    print(f"OK ({len(data['models'])} models)")

def test_upload(image_bytes):
    print("[3] 上传图像 + 深度估计 ...", end=" ", flush=True)
    r = requests.post(f"{BASE}/upload",
        files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        data={"max_size": 256, "model_key": "dav2-small"},
        timeout=120)
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert "session_id" in data
    print(f"OK session={data['session_id'][:8]}... {data['width']}x{data['height']}")
    return data["session_id"]

def test_generate(sid):
    print("[4] 生成虚拟视角 ...", end=" ", flush=True)
    for shift in [-0.05, 0.0, 0.05]:
        r = requests.post(f"{BASE}/generate", json={"session_id": sid, "shift": shift}, timeout=30)
        assert r.status_code == 200
    print("OK")

def test_stereo(sid):
    print("[5] 生成立体图像 ...", end=" ", flush=True)
    r = requests.post(f"{BASE}/stereo", json={"session_id": sid, "shift": 0.05}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ["left","right","anaglyph","side_by_side"]:
        assert k in data
    print("OK")

def test_multiview(sid):
    print("[6] 生成多视角序列 ...", end=" ", flush=True)
    r = requests.post(f"{BASE}/multiview", json={"session_id": sid, "num_views": 5, "max_shift": 0.06}, timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert len(data["views"]) == 5
    print(f"OK ({len(data['views'])} views)")

if __name__ == "__main__":
    print("="*50)
    print(" MonoVista API Integration Test")
    print("="*50)
    image_bytes = make_test_image()
    try:
        test_health()
        test_models()
        sid = test_upload(image_bytes)
        test_generate(sid)
        test_stereo(sid)
        test_multiview(sid)
        print("="*50)
        print(" All tests PASSED")
        print("="*50)
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
