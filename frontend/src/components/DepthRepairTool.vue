<template>
  <div class="repair-tool">
    <div class="toolbar">
      <h3>深度图修复工具</h3>
      <div class="controls">
        <div class="control-group">
          <label>画笔大小</label>
          <input type="range" min="5" max="100" step="1" v-model.number="brushSize" class="slider" />
          <span class="value">{{ brushSize }}px</span>
        </div>
        <div class="control-group">
          <label>深度值</label>
          <input type="range" min="0" max="255" step="1" v-model.number="depthValue" class="slider" />
          <span class="value">{{ depthValue }}</span>
        </div>
        <div class="control-group">
          <label>画笔硬度</label>
          <input type="range" min="0.1" max="1" step="0.1" v-model.number="brushHardness" class="slider" />
          <span class="value">{{ (brushHardness * 100).toFixed(0) }}%</span>
        </div>
        <div class="control-group">
          <label>深度图透明度</label>
          <input type="range" min="0.1" max="1" step="0.05" v-model.number="depthOpacity" class="slider" />
          <span class="value">{{ (depthOpacity * 100).toFixed(0) }}%</span>
        </div>
        <button class="btn btn-primary" @click="saveRepair">⬇ 保存</button>
        <button class="btn btn-ghost" @click="resetDepth">↺ 重置</button>
      </div>
    </div>

    <div class="content">
      <div class="left-panel">
        <h4>深度图编辑</h4>
        <!-- 双层叠加画布：底层原图 + 顶层深度图，用户涂抹时更直观 -->
        <div class="canvas-stack" ref="canvasStackRef">
          <!-- 底层：原图（只展示，不可交互）-->
          <img
            ref="bgImgRef"
            class="bg-layer"
            :src="store.original"
            alt="original"
            draggable="false"
            @load="onBgImgLoad"
          />
          <!-- 顶层：深度图画布，绝对定位精确覆盖原图渲染区域 -->
          <canvas
            ref="depthCanvasRef"
            class="depth-canvas"
            :style="canvasStyle"
            @mousedown="onCanvasMouseDown"
            @mousemove="onCanvasMouseMove"
            @mouseup="onCanvasMouseUp"
            @mouseleave="onCanvasMouseLeave"
          ></canvas>
        </div>
        <p class="hint">左键涂抹，右键擦除</p>
      </div>

      <div class="right-panel">
        <h4>3D 实时预览</h4>
        <div class="preview-canvas" ref="previewRef"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { useDepthStore } from '@/stores/depth'

const store = useDepthStore()
const depthCanvasRef  = ref(null)
const previewRef      = ref(null)
const bgImgRef        = ref(null)
const canvasStackRef  = ref(null)
const brushSize      = ref(30)
const depthValue     = ref(128)
const brushHardness  = ref(0.8)
const depthOpacity   = ref(0.65)

/**
 * canvasStyle — 精确覆盖原图渲染区域的内联样式。
 *
 * 问题根源：
 *   底层 <img> 使用 object-fit: contain，图片会按比例缩放并居中，
 *   实际渲染区域（rendered box）小于容器尺寸且有偏移。
 *   若顶层 canvas 直接 inset:0 填满容器，两者渲染区域不重合。
 *
 * 解决方案：
 *   onBgImgLoad / onStackResize 时计算 contain 后的实际 left/top/width/height，
 *   用 position:absolute + 精确数值覆盖，保证像素级对齐。
 */
const canvasStyle = reactive({
  position: 'absolute',
  left: '0px', top: '0px',
  width: '100%', height: '100%',
  opacity: depthOpacity,
  cursor: 'crosshair',
})

/** 计算 object-fit:contain 后图片在容器内的实际渲染区域 */
function calcContainRect() {
  const stack = canvasStackRef.value
  const img   = bgImgRef.value
  if (!stack || !img || !img.naturalWidth) return null

  const cW = stack.clientWidth
  const cH = stack.clientHeight
  const iW = img.naturalWidth
  const iH = img.naturalHeight

  // contain 缩放比例：取宽高中较小的缩放因子
  const scale = Math.min(cW / iW, cH / iH)
  const rW = iW * scale
  const rH = iH * scale
  // 居中偏移
  const left = (cW - rW) / 2
  const top  = (cH - rH) / 2
  return { left, top, width: rW, height: rH }
}

/** 更新 canvas 位置，使其精确覆盖原图渲染区域 */
function updateCanvasPosition() {
  const rect = calcContainRect()
  if (!rect) return
  canvasStyle.left   = rect.left   + 'px'
  canvasStyle.top    = rect.top    + 'px'
  canvasStyle.width  = rect.width  + 'px'
  canvasStyle.height = rect.height + 'px'
  canvasStyle.opacity = depthOpacity.value
}

function onBgImgLoad() {
  updateCanvasPosition()
}

let _resizeObs = null

let isDrawing = false, lastX = 0, lastY = 0
let depthCtx = null, depthCanvas = null
let renderer = null, scene = null, camera = null, mesh = null, animId = null
let depthTexture = null

const rawMouse    = new THREE.Vector2(0, 0)
const smoothMouse = new THREE.Vector2(0, 0)
const SMOOTH_K    = 0.06

const vertexShader = /* glsl */`
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = /* glsl */`
  uniform sampler2D uColor;
  uniform sampler2D uDepth;
  uniform vec2      uMouse;
  uniform float     uIntensity;
  varying vec2      vUv;
  const float INSET = 0.02, FADE = 0.05;
  void main() {
    float d = texture2D(uDepth, vUv).r;
    vec2 disparity = uMouse * uIntensity * d;
    vec2 uvNew = vUv + disparity;
    vec2 uvC = clamp(uvNew, vec2(INSET), vec2(1.0 - INSET));
    vec2 ov = abs(uvNew - clamp(uvNew, 0.0, 1.0));
    float alpha = clamp(1.0 - smoothstep(0.0, FADE, ov.x) - smoothstep(0.0, FADE, ov.y), 0.0, 1.0);
    vec4 col = texture2D(uColor, uvC);
    gl_FragColor = vec4(col.rgb, col.a * alpha);
  }
`

function onCanvasMouseDown(e) {
  isDrawing = true
  const { x, y } = getCanvasCoords(e)
  lastX = x; lastY = y
  drawBrushPoint(x, y, e.buttons === 2 ? 0 : depthValue.value)
}

function onCanvasMouseMove(e) {
  if (!isDrawing || !depthCtx) return
  const { x, y } = getCanvasCoords(e)
  const isErasing = e.buttons === 2
  const value = isErasing ? 0 : depthValue.value
  // 插值：鼠标移动过快时补中间点，保证笔触连续
  const dist = Math.hypot(x - lastX, y - lastY)
  const step = Math.max(1, brushSize.value * 0.3)
  if (dist > step) {
    const steps = Math.ceil(dist / step)
    for (let i = 1; i <= steps; i++) {
      const t = i / steps
      drawBrushPoint(lastX + (x - lastX) * t, lastY + (y - lastY) * t, value)
    }
  } else {
    drawBrushPoint(x, y, value)
  }
  lastX = x; lastY = y
  // 使用 rAF 节流：避免每次 mousemove 都触发 THREE.js 纹理上传
  scheduleTextureUpdate()
}

function onCanvasMouseUp() { isDrawing = false }
function onCanvasMouseLeave() { isDrawing = false }

// rAF 节流：把 depthTexture.needsUpdate 合并到下一帧，避免每 mousemove 都上传纹理
let _texDirty = false
function scheduleTextureUpdate() {
  if (_texDirty) return
  _texDirty = true
  requestAnimationFrame(() => {
    if (depthTexture) depthTexture.needsUpdate = true
    _texDirty = false
  })
}

/**
 * drawBrushPoint — 使用 Canvas 2D 原生径向渐变绘制笔触。
 *
 * 性能关键：完全避免 getImageData / putImageData 的 CPU 像素循环。
 * 改为创建 RadialGradient（中心不透明 → 边缘透明），
 * 配合 globalCompositeOperation 在 GPU 侧完成混合，
 * 即使画笔半径 100px 也几乎无 CPU 开销。
 *
 * @param cx    - 画笔中心 x（canvas 内部坐标）
 * @param cy    - 画笔中心 y
 * @param value - 深度灰度值 0-255（0 = 擦除/黑，255 = 最亮）
 */
function drawBrushPoint(cx, cy, value) {
  const r        = brushSize.value
  const hardness = brushHardness.value
  // 软边起点：hardness=1 时起点在中心，=0 时从 0 开始渐变
  const innerR   = r * hardness * 0.5

  const grad = depthCtx.createRadialGradient(cx, cy, innerR, cx, cy, r)
  const col  = `rgb(${value},${value},${value})`
  grad.addColorStop(0, col)                           // 中心：全强度
  grad.addColorStop(1, 'rgba(0,0,0,0)')               // 边缘：完全透明

  // source-over 叠加：新笔触与已有内容正常混合
  depthCtx.globalCompositeOperation = 'source-over'
  depthCtx.globalAlpha = 0.25                         // 每笔不透明度，多笔叠加产生累积效果
  depthCtx.fillStyle   = grad
  depthCtx.beginPath()
  depthCtx.arc(cx, cy, r, 0, Math.PI * 2)
  depthCtx.fill()
  depthCtx.globalAlpha = 1.0
}

function initThree() {
  const container = previewRef.value
  if (!container) return
  scene = new THREE.Scene()
  const W = container.clientWidth, H = container.clientHeight || 400
  camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 10)
  camera.position.set(0, 0, 1)
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(W, H)
  container.appendChild(renderer.domElement)
  container.addEventListener('mousemove', onPreviewMouseMove)
  container.addEventListener('mouseleave', () => rawMouse.set(0, 0))
  animate()
}

function onPreviewMouseMove(e) {
  const rect = previewRef.value.getBoundingClientRect()
  rawMouse.x = ((e.clientX - rect.left) / rect.width - 0.5) * 2
  rawMouse.y = -((e.clientY - rect.top) / rect.height - 0.5) * 2
}

function buildMesh(colorSrc) {
  if (mesh) {
    scene.remove(mesh)
    mesh.material.uniforms.uColor.value.dispose()
    mesh.material.uniforms.uDepth.value.dispose()
    mesh.geometry.dispose(); mesh.material.dispose(); mesh = null
  }
  const loader = new THREE.TextureLoader()
  const colorTex = loader.load(colorSrc)
  colorTex.minFilter = THREE.LinearFilter
  colorTex.wrapS = colorTex.wrapT = THREE.ClampToEdgeWrapping
  depthTexture = new THREE.CanvasTexture(depthCanvas)
  depthTexture.minFilter = THREE.LinearFilter
  depthTexture.wrapS = depthTexture.wrapT = THREE.ClampToEdgeWrapping
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: colorTex },
      uDepth: { value: depthTexture },
      uMouse: { value: smoothMouse },
      uIntensity: { value: 0.04 },
    },
    vertexShader, fragmentShader,
    transparent: true, depthWrite: false,
  })
  mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat)
  mesh.position.set(0, 0, 0)
  scene.add(mesh)
  fitPlane()
}

let imgAspect = 1
function fitPlane() {
  if (!mesh || !camera) return
  const d = camera.position.z, h = 2 * Math.tan((camera.fov * Math.PI / 180) / 2) * d
  const w = h * camera.aspect, PAD = 0.95
  let planeW, planeH
  if (imgAspect > camera.aspect) {
    planeW = w * PAD; planeH = planeW / imgAspect
  } else {
    planeH = h * PAD; planeW = planeH * imgAspect
  }
  mesh.scale.set(planeW, planeH, 1)
}

function animate() {
  animId = requestAnimationFrame(animate)
  smoothMouse.x += SMOOTH_K * (rawMouse.x - smoothMouse.x)
  smoothMouse.y += SMOOTH_K * (rawMouse.y - smoothMouse.y)
  if (mesh) mesh.material.uniformsNeedUpdate = true
  renderer?.render(scene, camera)
}

function initDepthCanvas() {
  depthCanvas = depthCanvasRef.value
  if (!depthCanvas) return
  depthCtx = depthCanvas.getContext('2d')
  const W = store.imageSize.width, H = store.imageSize.height
  // canvas 内部分辨率与图像原始尺寸一致，CSS 层由 object-fit:contain 缩放
  depthCanvas.width = W; depthCanvas.height = H
  if (store.depthNorm) {
    const img = new Image()
    img.onload = () => {
      depthCtx.drawImage(img, 0, 0)
      imgAspect = W / H
      buildMesh(store.original)
    }
    img.src = store.depthNorm
  }
}

/**
 * getCanvasCoords — 将鼠标客户端坐标转换为 canvas 内部像素坐标。
 * canvas CSS 尺寸与内部分辨率（原图像素）不同，需按比例换算。
 */
function getCanvasCoords(e) {
  const canvas = depthCanvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  const rect   = canvas.getBoundingClientRect()
  const scaleX = canvas.width  / rect.width
  const scaleY = canvas.height / rect.height
  // 更新透明度（随时响应滑块变化）
  canvasStyle.opacity = depthOpacity.value
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top)  * scaleY,
  }
}

function saveRepair() {
  if (!depthCanvas) return
  const base64 = depthCanvas.toDataURL('image/png')
  const link = document.createElement('a')
  link.href = base64
  link.download = 'repaired_depth.png'
  link.click()
}

function resetDepth() {
  if (!depthCtx || !store.depthNorm) return
  const img = new Image()
  img.onload = () => {
    depthCtx.clearRect(0, 0, depthCanvas.width, depthCanvas.height)
    depthCtx.drawImage(img, 0, 0)
    if (depthTexture) depthTexture.needsUpdate = true
  }
  img.src = store.depthNorm
}

onMounted(() => {
  initDepthCanvas()
  initThree()
  // ResizeObserver：容器尺寸变化时重新计算 canvas 覆盖位置
  _resizeObs = new ResizeObserver(() => {
    updateCanvasPosition()
  })
  if (canvasStackRef.value) _resizeObs.observe(canvasStackRef.value)
})
onUnmounted(() => {
  cancelAnimationFrame(animId)
  if (renderer) { renderer.dispose(); renderer.domElement.remove() }
  if (_resizeObs) _resizeObs.disconnect()
})
</script>

<style scoped>
.repair-tool { display: flex; flex-direction: column; gap: 16px; padding: 20px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.toolbar h3 { font-size: 1rem; font-weight: 700; margin: 0; }
.controls { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.control-group { display: flex; align-items: center; gap: 8px; }
.control-group label { font-size: 0.82rem; color: var(--text-sec); white-space: nowrap; }
.slider { width: 120px; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--border); outline: none; cursor: pointer; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--accent); cursor: pointer; }
.value { font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; color: var(--accent); min-width: 45px; }
.content { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; min-height: 436px; }
.left-panel, .right-panel { display: flex; flex-direction: column; gap: 8px; }
.left-panel h4, .right-panel h4 { font-size: 0.9rem; font-weight: 700; margin: 0; }

/* ── 双层叠加画布容器 ── */
.canvas-stack {
  flex: 1;
  position: relative;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-deep);
  overflow: hidden;
  min-height: 266px;
  max-height: 508px;
}

/*
  底层：原图填满容器，object-fit:contain 保持比例居中。
  pointer-events:none 确保鼠标事件穿透到上层 canvas。
*/
.bg-layer {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
}

/*
  顶层：深度图 canvas。
  position/left/top/width/height/opacity 全部由 Vue :style="canvasStyle" 动态绑定，
  精确覆盖原图的 object-fit:contain 渲染区域，不使用 inset:0 填满容器。
*/
.depth-canvas {
  position: absolute;
  display: block;
}

.preview-canvas { flex: 1; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-deep); min-height: 266px; max-height: 508px; }
.preview-canvas :deep(canvas) { display: block; width: 100%; height: 100%; }
.hint { font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; margin: 0; }
@media (max-width: 1000px) { .content { grid-template-columns: 1fr; min-height: auto; } }
</style>
