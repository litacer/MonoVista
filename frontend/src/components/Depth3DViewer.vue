<template>
  <div class="depth3d-panel">
    <div class="panel-header">
      <h3>3D 深度视差展示</h3>
      <span class="tag">WebGL · DIBR</span>
    </div>
    <div class="canvas-wrap" ref="containerRef" :style="{ height: containerHeight + 'px' }">
      <div v-if="!store.original" class="empty"><p>上传图像后启用 3D 视差效果</p></div>
    </div>
    <div v-if="store.original" class="ctrl-row">
      <label>视差强度</label>
      <input type="range" min="0" max="0.12" step="0.002"
        v-model.number="intensity" class="slider" />
      <span class="val">{{ (intensity * 100).toFixed(1) }}%</span>
      <button class="btn btn-ghost" style="margin-left:auto" @click="resetMouse">重置视角</button>
    </div>
  </div>
</template>

<script setup>
/**
 * Depth3DViewer.vue
 * ============================================================
 * 窗口式 DIBR（Depth Image Based Rendering）视差效果
 *
 * 核心公式（逐像素，片段着色器内执行）：
 *   uv_new  = uv + depth(uv) * uMouse * uIntensity   -- 反向映射
 *   disparity = uMouse * uIntensity * d               -- 视差向量
 *   uv_clamped = clamp(uv_new, inset, 1-inset)        -- 边缘夹取
 *
 * 参考：Fehn 2004, SPIE §3.2 Inverse Mapping
 * ============================================================
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { useDepthStore } from '@/stores/depth'
import { useThemeStore } from '@/stores/theme'

const store        = useDepthStore()
const themeStore   = useThemeStore()
const containerRef = ref(null)
const intensity    = ref(0.04)
const containerHeight = ref(400)  // 动态高度，纹理加载后按图片比例更新

// Three.js 状态（非响应式，直接持有引用）
let renderer = null
let scene    = null
let camera   = null
let mesh     = null
let animId   = null
let ro       = null   // ResizeObserver

// 鼠标平滑插值：rawMouse 为即时目标，smoothMouse 每帧指数逼近
const rawMouse    = new THREE.Vector2(0, 0)
const smoothMouse = new THREE.Vector2(0, 0)
const SMOOTH_K    = 0.06   // 平滑系数；越小越"粘滞"

// ============================================================
// 顶点着色器：极简直通，平面几何完全静止
// 所有视差效果在片段着色器的 UV 偏移中完成，
// 符合"图像框架不动、内容随鼠标飘移"的窗口式 3D 要求。
// ============================================================
const vertexShader = /* glsl */`
  varying vec2 vUv;
  void main() {
    vUv = uv;
    // 直接投影到裁剪空间，不做任何顶点位移
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

// ============================================================
// 片段着色器：DIBR 核心算法
//
// Step 1  读取深度 d = texture(uDepth, vUv).r
//         d ∈ [0,1]，1=近景，0=远景
//
// Step 2  计算视差向量
//         disparity = uMouse * uIntensity * d
//         物理含义：相机沿基线 B=uIntensity 平移时，
//         深度为 d 的像素产生的水平视差 Δx = (B/Z)·f ≈ B·d（归一化坐标）
//
// Step 3  反向映射（Inverse Warping，避免正向映射孔洞）
//         uv_new = vUv + disparity
//
// Step 4  边缘夹取 + 渐隐遮罩，抑制拉丝伪影
//         uv_clamped = clamp(uv_new, INSET, 1-INSET)
//         alpha 在溢出区域由 smoothstep 平滑归零
// ============================================================
const fragmentShader = /* glsl */`
  uniform sampler2D uColor;     // 原始彩色图
  uniform sampler2D uDepth;     // 灰度深度图（r 通道 = 归一化深度）
  uniform vec2      uMouse;     // JS 侧平滑后的归一化鼠标偏移 [-1,1]²
  uniform float     uIntensity; // 立体强度系数（用户可调）
  varying vec2      vUv;

  // 边缘夹取内缩量与渐隐宽度（UV 空间单位）
  const float INSET = 0.02;
  const float FADE  = 0.05;

  void main() {
    // ── Step 1：读取当前像素深度 ──────────────────────────────
    // 深度图 r 通道即归一化深度值，近景接近 1，远景接近 0
    float d = texture2D(uDepth, vUv).r;

    // ── Step 2：DIBR 视差向量 ─────────────────────────────────
    // disparity = uMouse * uIntensity * d
    // 近处像素(d大)位移大 → 产生强烈前景浮出感
    // 远处像素(d小)几乎不动 → 背景"钉"在原位
    vec2 disparity = uMouse * uIntensity * d;

    // ── Step 3：反向映射新采样坐标 ───────────────────────────
    // uv_new = vUv + disparity
    // 鼠标右移(uMouse.x>0)时近景向右偏移，符合视差方向约定
    vec2 uvNew = vUv + disparity;

    // ── Step 4a：边缘夹取（防拉丝）──────────────────────────
    // 将采样坐标约束在 [INSET, 1-INSET] 内
    // 超出范围的像素贴最近有效像素，等效 GL_CLAMP_TO_EDGE
    vec2 uvC = clamp(uvNew, vec2(INSET), vec2(1.0 - INSET));

    // ── Step 4b：边缘渐隐遮罩（比硬夹取更自然）─────────────
    // 计算 uvNew 超出 [0,1] 的溢出量，驱动 alpha 平滑衰减
    vec2  ov    = abs(uvNew - clamp(uvNew, 0.0, 1.0));
    float alpha = clamp(
      1.0 - smoothstep(0.0, FADE, ov.x)
          - smoothstep(0.0, FADE, ov.y),
      0.0, 1.0
    );

    // ── Step 5：采样并输出，叠加边缘 alpha ───────────────────
    vec4 col = texture2D(uColor, uvC);
    gl_FragColor = vec4(col.rgb, col.a * alpha);
  }
`

// ============================================================
// initThree
// ============================================================
function initThree() {
  const container = containerRef.value
  if (!container) return
  scene  = new THREE.Scene()
  // 初始化时根据当前主题设置背景色
  scene.background = new THREE.Color(themeStore.isDark ? 0x080c14 : 0xe4eaf6)
  const W = container.clientWidth
  const H = container.clientHeight || 400
  // 透视相机，静止于 z=1，始终正对平面中心
  camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 10)
  camera.position.set(0, 0, 1)
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(W, H)
  container.appendChild(renderer.domElement)
  ro = new ResizeObserver(() => {
    const w = container.clientWidth, h = container.clientHeight || 400
    renderer.setSize(w, h); camera.aspect = w / h
    camera.updateProjectionMatrix(); fitPlane()
  })
  ro.observe(container)
  container.addEventListener('mousemove', onMouseMove)
  container.addEventListener('mouseleave', () => rawMouse.set(0, 0))
  animate()
}

// ============================================================
// buildMesh：构建承载 ShaderMaterial 的静止平面
// PlaneGeometry 使用 1x1（所有效果在 fragment shader 完成）
// ============================================================
function buildMesh(colorSrc, depthSrc) {
  if (mesh) {
    scene.remove(mesh)
    mesh.material.uniforms.uColor.value.dispose()
    mesh.material.uniforms.uDepth.value.dispose()
    mesh.geometry.dispose(); mesh.material.dispose(); mesh = null
  }
  const loader = new THREE.TextureLoader()
  const colorTex = loader.load(colorSrc, (tex) => {
    // 纹理加载完成后，按图片真实宽高比调整平面和容器高度
    imgAspect = tex.image.width / tex.image.height
    // 容器宽度已知，按比例计算合适高度（最小300，最大600）
    const containerW = containerRef.value?.clientWidth || 800
    const idealH = Math.round(containerW / imgAspect)
    containerHeight.value = Math.min(Math.max(idealH, 300), 600)
    // 等 DOM 更新后重新初始化渲染器尺寸并 fitPlane
    setTimeout(() => {
      if (!renderer || !containerRef.value) return
      const w = containerRef.value.clientWidth
      const h = containerRef.value.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      fitPlane()
    }, 30)
  })
  colorTex.minFilter = THREE.LinearFilter
  colorTex.wrapS = colorTex.wrapT = THREE.ClampToEdgeWrapping
  const depthTex = loader.load(depthSrc)
  depthTex.minFilter = THREE.LinearFilter
  depthTex.wrapS = depthTex.wrapT = THREE.ClampToEdgeWrapping
  // uniforms:
  //   uColor     - 彩色图纹理
  //   uDepth     - 深度图纹理
  //   uMouse     - 平滑鼠标偏移（直接传引用，每帧自动同步）
  //   uIntensity - 强度系数（对应论文中 B·f 乘积的归一化形式）
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uColor:     { value: colorTex },
      uDepth:     { value: depthTex },
      uMouse:     { value: smoothMouse },
      uIntensity: { value: intensity.value },
    },
    vertexShader, fragmentShader,
    transparent: true, depthWrite: false,
  })
  mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat)
  mesh.position.set(0, 0, 0)  // 平面完全静止，居中
  scene.add(mesh)
  // 注意：不在此调用 fitPlane()，等纹理回调中获取真实宽高比后再调用
}

// 缩放平面：按图片宽高比居中显示，留 5% 边距，不超出视锥
let imgAspect = 1  // 图片宽高比，纹理加载后更新
function fitPlane() {
  if (!mesh || !camera) return
  const camD = camera.position.z
  const vFov = camera.fov * Math.PI / 180
  const visH = 2 * Math.tan(vFov / 2) * camD  // 视锥可见高度
  const visW = visH * camera.aspect             // 视锥可见宽度
  const PAD  = 0.95  // 留 5% 边距，不超出视锥
  // 按图片宽高比在视锥内做 contain 缩放
  let planeW, planeH
  if (imgAspect > camera.aspect) {
    // 图片比相机更宽：以宽度为基准
    planeW = visW * PAD
    planeH = planeW / imgAspect
  } else {
    // 图片比相机更高：以高度为基准
    planeH = visH * PAD
    planeW = planeH * imgAspect
  }
  mesh.scale.set(planeW, planeH, 1)
}

// ============================================================
// animate：主渲染循环
// ============================================================
function animate() {
  animId = requestAnimationFrame(animate)
  // 指数平滑：smoothMouse += K*(rawMouse - smoothMouse)
  smoothMouse.x += SMOOTH_K * (rawMouse.x - smoothMouse.x)
  smoothMouse.y += SMOOTH_K * (rawMouse.y - smoothMouse.y)
  if (mesh) {
    // 实时同步强度 uniform（响应滑块）
    mesh.material.uniforms.uIntensity.value = intensity.value
    // uMouse 持有 smoothMouse 对象引用，Three.js 每帧自动读取最新值
    mesh.material.uniformsNeedUpdate = true
  }
  renderer?.render(scene, camera)
}

function onMouseMove(e) {
  const rect = containerRef.value.getBoundingClientRect()
  // 映射到 [-1, 1]²，Y 轴翻转（WebGL Y 向上）
  rawMouse.x =  ((e.clientX - rect.left)  / rect.width  - 0.5) * 2
  rawMouse.y = -((e.clientY - rect.top)   / rect.height - 0.5) * 2
}

function resetMouse() { rawMouse.set(0, 0) }

function destroy() {
  cancelAnimationFrame(animId)
  ro?.disconnect()
  if (renderer) { renderer.dispose(); renderer.domElement.remove(); renderer = null }
  mesh = null; scene = null; camera = null
}

// ============================================================
// 侦听 store 图像变化，重建 mesh
// ============================================================
watch(() => store.original,  (v) => { if (v && store.depthNorm) buildMesh(v, store.depthNorm) })
watch(() => store.depthNorm, (v) => { if (v && store.original)  buildMesh(store.original, v) })

// ============================================================
// 侦听主题切换，同步 Three.js 场景背景色
// isDark 切换时立即更新 scene.background，确保 3D 区域与页面一致
// ============================================================
function applySceneTheme(isDark) {
  if (!scene) return
  const hex = isDark ? 0x080c14 : 0xe4eaf6
  scene.background = new THREE.Color(hex)
}

watch(() => themeStore.isDark, (isDark) => {
  applySceneTheme(isDark)
}, { immediate: false })

onMounted(() => {
  initThree()
  if (store.original && store.depthNorm) buildMesh(store.original, store.depthNorm)
})
onUnmounted(destroy)

/**
 * restoreFromHistory — 一键复原历史快照
 *
 * 当用户在历史侧边栏点击某条记录时，WorkspaceView 调用此方法。
 * 执行步骤：
 *   1. 反序列化 render_config JSON，恢复视差强度等渲染参数
 *   2. 使用 THREE.TextureLoader 重新加载云端 OSS 图片（原图 + 深度图）
 *   3. 重建 ShaderMaterial mesh，3D 场景立即同步为历史快照状态
 *
 * @param {string} colorUrl      - 历史记录中的原图 OSS URL
 * @param {string} depthUrl      - 历史记录中的深度图 OSS URL
 * @param {object} renderConfig  - 历史记录中的渲染参数，如 { intensity: 0.06 }
 */
function restoreFromHistory(colorUrl, depthUrl, renderConfig) {
  // Step 1：反序列化渲染参数并注入到响应式变量
  // intensity 是唯一用户可调参数，直接赋值即可同步滑块和 uniform
  if (renderConfig && typeof renderConfig.intensity === 'number') {
    intensity.value = renderConfig.intensity
  }
  // Step 2 & 3：buildMesh 内部使用 THREE.TextureLoader 加载云端 URL，
  // 加载完成后自动调用 fitPlane() 和 containerHeight 更新
  buildMesh(colorUrl, depthUrl)
}

// 将 restoreFromHistory 和 intensity 暴露给父组件
// 父组件通过 ref="viewer3d" 调用 viewer3d.restoreFromHistory(...)
defineExpose({ restoreFromHistory, intensity, renderer: { get: () => renderer } })
</script>

<style scoped>
.depth3d-panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.panel-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.panel-header h3 { font-size: 1rem; font-weight: 700; }
.canvas-wrap { width: 100%; background: var(--bg-deep); position: relative; display: flex; align-items: center; justify-content: center; transition: height 0.3s ease; }
.canvas-wrap :deep(canvas) { display: block; width: 100% !important; height: 100% !important; }
.empty { color: var(--text-dim); font-size: 0.9rem; text-align: center; pointer-events: none; }
.ctrl-row { padding: 14px 20px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 12px; }
.ctrl-row label { font-size: 0.82rem; color: var(--text-sec); white-space: nowrap; }
.slider { flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--border); outline: none; cursor: pointer; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px rgba(0,212,255,0.5); cursor: pointer; }
.val { font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; color: var(--accent); min-width: 42px; }
</style>