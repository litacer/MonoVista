# MonoVista — 单目深度估计图像动态立体转换工具

## 技术栈
| 层次 | 技术 |
|------|------|
| 深度估计 | Depth Anything V2 / MiDaS / Monodepth2 |
| 后端 | Python 3.9+ / Flask 3 |
| 前端 | Vue 3 + Vite + Pinia + Three.js |
| 立体合成 | DIBR (自实现) + OpenCV |

## 快速启动

### 第一步：安装 Python 依赖
```bash
cd D:\毕设\MonoVista
pip install -r requirements.txt
```

### 第二步：启动后端
```bash
python app.py
```
首次运行自动下载模型到 `models_cache/` 目录（约 100MB），需要网络。
后端运行在 `http://localhost:5000`

### 第三步：启动前端
```bash
cd frontend
npm install
npm run dev
```
前端运行在 `http://localhost:3000`

### 一键启动（Windows）
```powershell
.\start.ps1
```

## API 接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health`    | 健康检查 |
| GET  | `/api/models`    | 获取可用模型列表 |
| POST | `/api/upload`    | 上传图像，返回深度图 + session_id |
| POST | `/api/generate`  | 生成单个虚拟视角 |
| POST | `/api/stereo`    | 生成立体图像套装 |
| POST | `/api/multiview` | 生成多视角动画序列 |

## 环境变量（.env）
```
DEPTH_MODEL_KEY=dav2-small   # 默认模型
DEVICE=                        # 留空自动选择 cuda/cpu
FLASK_DEBUG=true
PORT=5000
```

## 模型说明
| Key | 模型 | 速度 |
|-----|------|------|
| dav2-small  | Depth Anything V2 Small | 快 |
| dav2-base   | Depth Anything V2 Base  | 中 |
| dav2-large  | Depth Anything V2 Large | 慢 |
| midas-large | MiDaS DPT-Large         | 中 |
| midas-hybrid| MiDaS DPT-Hybrid        | 快 |
| midas-small | MiDaS v2.1 Small        | 快 |
| mono2-stereo| Monodepth2 Stereo       | 快 |

模型首次使用时自动下载并缓存到 `models_cache/` 目录。
