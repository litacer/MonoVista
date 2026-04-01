<template>
  <div class="share-page" @contextmenu.prevent>
    <div v-if="loading" class="share-loading">
      <div class="share-spinner"></div>
      <p>正在加载预览…</p>
    </div>
    <div v-else-if="error" class="share-error">
      <el-empty :image-size="120">
        <template #description>
          <h3 class="err-title">链接已失效</h3>
          <p class="err-sub">{{ errorMsg }}</p>
        </template>
      </el-empty>
      <button class="cta-btn" @click="goHome">我也要试试 →</button>
    </div>
    <div v-else class="share-content">
      <header class="share-topbar">
        <span class="share-brand">Mono<span class="brand-accent">Vista</span></span>
        <span class="share-badge">只读预览</span>
        <span class="share-expire">有效至 {{ info.expire_at }}</span>
      </header>
      <div class="preview-wrap">
        <div class="canvas-container" ref="containerRef"
          @mousemove="onMouseMove"
          @mouseleave="rawMouse.set(0,0)"
        ></div>
      </div>
      <div class="share-meta">
        <span class="meta-label">模型</span>
        <span class="meta-val">{{ info.model_label || '—' }}</span>
        <span class="meta-label">分辨率</span>
        <span class="meta-val">{{ info.image_width }}×{{ info.image_height }}</span>
      </div>
      <section class="share-footer">
        <div class="footer-intro">
          <h3>MonoVista — 单目深度估计平台</h3>
          <p>上传一张普通照片，即可生成高质量深度图与 3D 视差效果。</p>
        </div>
        <button class="cta-btn" @click="goHome">我也要试试 →</button>
      </section>
    </div>
  </div>
</template>

<script setup>
/**
 * ShareView.vue — 访客只读分享页
 *
 * DIBR 渲染（与 Depth3DViewer.vue 完全一致）：
 *   uColor = 原图（颜色层）
 *   uDepth = 深度图（位移层）
 *   disparity = uMouse * uIntensity * depth(uv)
 *   uv_new    = uv + disparity
 *   近景(depth大)位移大 → 前景浮出 3D 感
 *
 * 安全：@contextmenu.prevent + user-select:none
 * 只读：无滑块、无编辑、无下载入口
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as THREE from 'three'
import { fetchShareView } from '@/api'

const route  = useRoute()
const router = useRouter()
const loading  = ref(true)
const error    = ref(false)
const errorMsg = ref('该分享链接不存在或已过期')
const info     = ref({})

const containerRef = ref(null)
const rawMouse     = new THREE.Vector2(0, 0)
const smoothMouse  = new THREE.Vector2(0, 0)
const SMOOTH_K     = 0.06
let renderer = null, scene = null, camera = null, mesh = null, animId = null

const vertexShader = /* glsl */`
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }
`

// DIBR 片段着色器：双纹理 —— 颜色层(uColor) + 位移层(uDepth)
const fragmentShader = /* glsl */`
  uniform sampler2D uColor;
  uniform sampler2D uDepth;
  uniform vec2      uMouse;
  uniform float     uIntensity;
  varying vec2      vUv;
  const float INSET=0.02, FADE=0.05;
  void main() {
    float d      = texture2D(uDepth, vUv).r;
    vec2 uvNew   = vUv + uMouse * uIntensity * d;
    vec2 uvC     = clamp(uvNew, vec2(INSET), vec2(1.0-INSET));
    vec2 ov      = abs(uvNew - clamp(uvNew, 0.0, 1.0));
    float alpha  = clamp(1.0 - smoothstep(0.0,FADE,ov.x) - smoothstep(0.0,FADE,ov.y), 0.0, 1.0);
    vec4 col     = texture2D(uColor, uvC);
    gl_FragColor = vec4(col.rgb, col.a * alpha);
  }
`

function initThree(colorUrl, depthUrl, intensity) {
  const container = containerRef.value
  if (!container) return

  // 等容器有实际宽度（避免 clientWidth=0 的竞态）
  const W = container.clientWidth  || window.innerWidth
  const H = container.clientHeight || 540

  scene  = new THREE.Scene()
  scene.background = new THREE.Color(0x080c14)
  camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 10)
  camera.position.set(0, 0, 1)
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(W, H)
  container.appendChild(renderer.domElement)

  // 通过后端代理加载纹理，绕过 OSS CORS 限制
  const proxyUrl = (url) =>
    url ? `/api/proxy-image?url=${encodeURIComponent(url)}` : url

  const loader = new THREE.TextureLoader()
  loader.crossOrigin = 'anonymous'

  let colorLoaded = false, depthLoaded = false
  let colorTex = null, depthTex = null

  function tryStart() {
    if (!colorLoaded || !depthLoaded) return

    const mat = new THREE.ShaderMaterial({
      uniforms: {
        uColor:     { value: colorTex },
        uDepth:     { value: depthTex },
        uMouse:     { value: smoothMouse },
        uIntensity: { value: intensity },
      },
      vertexShader, fragmentShader,
      transparent: true, depthWrite: false,
    })
    mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat)
    scene.add(mesh)

    // contain 缩放平面（与 Depth3DViewer.fitPlane 一致）
    const aspect = (info.value.image_width || colorTex.image.width || 1) /
                   (info.value.image_height || colorTex.image.height || 1)
    const visH = 2 * Math.tan((camera.fov * Math.PI / 180) / 2) * camera.position.z
    const visW = visH * camera.aspect
    const PAD  = 0.95
    mesh.scale.set(
      aspect > camera.aspect ? visW * PAD          : visH * PAD * aspect,
      aspect > camera.aspect ? visW * PAD / aspect : visH * PAD,
      1
    )
    animate()
  }

  colorTex = loader.load(
    proxyUrl(colorUrl),
    (tex) => {
      tex.minFilter = THREE.LinearFilter
      tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping
      colorLoaded = true
      tryStart()
    },
    undefined,
    (err) => { console.error('[ShareView] color texture failed', err) }
  )

  depthTex = loader.load(
    proxyUrl(depthUrl),
    (tex) => {
      tex.minFilter = THREE.LinearFilter
      tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping
      depthLoaded = true
      tryStart()
    },
    undefined,
    (err) => { console.error('[ShareView] depth texture failed', err) }
  )
}

function animate() {
  animId = requestAnimationFrame(animate)
  smoothMouse.x += SMOOTH_K * (rawMouse.x - smoothMouse.x)
  smoothMouse.y += SMOOTH_K * (rawMouse.y - smoothMouse.y)
  if (mesh) mesh.material.uniformsNeedUpdate = true
  renderer?.render(scene, camera)
}

function onMouseMove(e) {
  const rect = containerRef.value?.getBoundingClientRect()
  if (!rect) return
  rawMouse.x =  ((e.clientX - rect.left) / rect.width  - 0.5) * 2
  rawMouse.y = -((e.clientY - rect.top)  / rect.height - 0.5) * 2
}

function goHome() { router.push('/auth/login') }

onMounted(async () => {
  try {
    const { data } = await fetchShareView(route.params.token)
    info.value    = data
    loading.value = false
    // 等待 DOM 完全绘制后再初始化 Three.js（v-else 切换后需要一帧）
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
    initThree(data.color_url, data.depth_url, data.intensity ?? 0.04)
  } catch (e) {
    errorMsg.value = e?.response?.data?.error === 'TOKEN_EXPIRED'
      ? '该分享链接已过期，请联系分享者重新生成。'
      : '该分享链接不存在或已被删除。'
    error.value   = true
    loading.value = false
  }
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  if (renderer) { renderer.dispose(); renderer.domElement.remove() }
})
</script>

<style scoped>
.share-page {
  min-height: 100vh; background: #080c14; color: #e0e6f0;
  font-family: 'Syne', 'Inter', sans-serif;
  user-select: none; -webkit-user-select: none;
  display: flex; flex-direction: column;
}
.share-loading { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; color:#60718a; }
.share-spinner { width:40px; height:40px; border:3px solid rgba(0,212,255,0.2); border-top-color:#00d4ff; border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.share-error { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; padding:40px; }
.err-title { font-size:1.4rem; font-weight:700; color:#e0e6f0; margin:0 0 8px; }
.err-sub   { font-size:0.9rem; color:#60718a; margin:0; }
.share-content { display:flex; flex-direction:column; flex:1; }
.share-topbar {
  display:flex; align-items:center; gap:14px; padding:14px 28px;
  border-bottom:1px solid rgba(255,255,255,0.06);
  background:rgba(8,12,20,0.9); backdrop-filter:blur(8px);
  position:sticky; top:0; z-index:10;
}
.share-brand  { font-size:1.1rem; font-weight:800; }
.brand-accent { color:#00d4ff; }
.share-badge  { font-size:0.7rem; padding:2px 10px; border-radius:999px; border:1px solid rgba(0,212,255,0.3); color:#00d4ff; font-family:'JetBrains Mono',monospace; }
.share-expire { font-size:0.72rem; color:#60718a; margin-left:auto; font-family:'JetBrains Mono',monospace; }
.preview-wrap { background:#080c14; }
.canvas-container { width:100%; height:540px; }
.canvas-container :deep(canvas) { display:block; width:100% !important; height:100% !important; }
.share-meta {
  display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:12px 28px;
  border-top:1px solid rgba(255,255,255,0.06); border-bottom:1px solid rgba(255,255,255,0.06);
  background:rgba(255,255,255,0.02);
}
.meta-label { font-size:0.72rem; color:#60718a; }
.meta-val   { font-size:0.82rem; color:#00d4ff; font-family:'JetBrains Mono',monospace; margin-right:16px; }
.share-footer {
  display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px;
  padding:28px 40px; border-top:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.015);
}
.footer-intro h3 { font-size:1rem; font-weight:700; margin:0 0 6px; color:#e0e6f0; }
.footer-intro p  { font-size:0.84rem; color:#60718a; margin:0; }
.cta-btn {
  padding:10px 28px; border-radius:999px;
  background:linear-gradient(135deg,#00d4ff,#0090cc);
  color:#080c14; font-weight:700; font-size:0.92rem;
  border:none; cursor:pointer; transition:opacity 0.15s; white-space:nowrap;
}
.cta-btn:hover { opacity:0.88; }
</style>
