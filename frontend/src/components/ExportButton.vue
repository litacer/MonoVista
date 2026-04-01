<template>
  <button
    class="btn btn-export"
    :class="{ loading: exporting }"
    :disabled="exporting"
    @click="doExport"
    title="将原图、深度图、立体图和3D截图打包下载"
  >
    <span v-if="!exporting" class="export-icon">⬇</span>
    <span v-else class="export-spinner"></span>
    {{ exporting ? exportStatus : '一键导出' }}
  </button>
</template>

<script setup>
/**
 * ExportButton.vue — 一键打包导出
 *
 * 导出内容：
 *   1. original.{ext}  — 原始上传图像
 *   2. depth_color.png — 彩色深度图
 *   3. depth_norm.png  — 灰度深度图
 *   4. stereo_left/right.png — 立体对（若已生成）
 *   5. preview_3d.png  — Three.js 实时截图（若已激活）
 *   6. meta.json       — 会话元信息
 *
 * 跨域处理：
 *   先直接 fetch；若 CORS 失败则改走后端代理 /api/proxy-image?url=...
 *
 * 依赖：npm install jszip file-saver
 */
import { ref } from 'vue'
import { useDepthStore } from '@/stores/depth'

const props = defineProps({
  /** Three.js WebGLRenderer 实例，用于截图 */
  renderer:    { type: Object, default: null },
  /** 立体图像结果 { left_image, right_image } */
  stereoResult: { type: Object, default: null },
})

const store        = useDepthStore()
const exporting    = ref(false)
const exportStatus = ref('')

/**
 * fetchBlob — 获取图片 Blob，自动处理跨域。
 * 1. data: URI → 直接 fetch
 * 2. 直接 cors fetch → 成功则返回
 * 3. 后端代理 /api/proxy-image?url=... → 兜底
 * 4. 均失败 → 返回 null（跳过该文件）
 */
async function fetchBlob(url) {
  if (!url) return null
  if (url.startsWith('data:')) return (await fetch(url)).blob()
  try {
    const res = await fetch(url, { mode: 'cors' })
    if (res.ok) return res.blob()
  } catch (_) { /* CORS 失败，走代理 */ }
  try {
    const res = await fetch(`/api/proxy-image?url=${encodeURIComponent(url)}`)
    if (res.ok) return res.blob()
  } catch (_) { /* 代理也失败 */ }
  console.warn('[ExportButton] fetchBlob failed:', url)
  return null
}

/**
 * captureRenderer — 同步截取 Three.js 当前帧。
 * 要求 renderer 在 animate() 同一帧内调用，或开启 preserveDrawingBuffer。
 */
function captureRenderer() {
  try {
    const canvas = props.renderer?.domElement
    if (!canvas) return null
    const dataUrl = canvas.toDataURL('image/png')
    const arr = dataUrl.split(',')
    const mime = arr[0].match(/:(.*?);/)[1]
    const bstr = atob(arr[1])
    let n = bstr.length
    const u8 = new Uint8Array(n)
    while (n--) u8[n] = bstr.charCodeAt(n)
    return new Blob([u8], { type: mime })
  } catch (e) {
    console.warn('[ExportButton] captureRenderer failed:', e)
    return null
  }
}

function getExt(url) {
  if (!url) return 'png'
  if (/data:image\/(jpeg|jpg)/.test(url)) return 'jpg'
  if (/data:image\/webp/.test(url)) return 'webp'
  const m = url.match(/\.([a-zA-Z0-9]+)(\?|$)/)
  return m ? m[1].toLowerCase() : 'png'
}

async function doExport() {
  if (exporting.value) return
  exporting.value = true

  // 动态导入，避免影响首屏加载
  let JSZip, saveAs
  try {
    ;([{ default: JSZip }, { saveAs }] = await Promise.all([
      import('jszip'),
      import('file-saver'),
    ]))
  } catch {
    alert('请先安装依赖：npm install jszip file-saver')
    exporting.value = false
    return
  }

  const zip = new JSZip()
  const folderName = (store.sessionId || 'monovista').replace(/^hist_/, 'history_')
  const folder = zip.folder(folderName)

  try {
    // 1. 原图
    exportStatus.value = '打包原图…'
    const origExt  = getExt(store.original)
    const origBlob = await fetchBlob(store.original)
    if (origBlob) folder.file(`original.${origExt}`, origBlob)

    // 2. 彩色深度图
    exportStatus.value = '打包深度图…'
    const dcBlob = await fetchBlob(store.depthColor)
    if (dcBlob) folder.file('depth_color.png', dcBlob)

    // 3. 灰度深度图
    const dnBlob = await fetchBlob(store.depthNorm)
    if (dnBlob) folder.file('depth_norm.png', dnBlob)

    // 4. 立体对
    if (props.stereoResult) {
      exportStatus.value = '打包立体图像…'
      const lBlob = await fetchBlob(props.stereoResult.left_image)
      const rBlob = await fetchBlob(props.stereoResult.right_image)
      if (lBlob) folder.file('stereo_left.png',  lBlob)
      if (rBlob) folder.file('stereo_right.png', rBlob)
    }

    // 5. Three.js 截图
    exportStatus.value = '截取3D预览…'
    const ssBlob = captureRenderer()
    if (ssBlob) folder.file('preview_3d.png', ssBlob)

    // 6. 元信息
    folder.file('meta.json', JSON.stringify({
      session_id:  store.sessionId,
      model:       store.usedModelLabel,
      image_size:  store.imageSize,
      exported_at: new Date().toISOString(),
      files: [
        origBlob ? `original.${origExt}` : null,
        dcBlob   ? 'depth_color.png'     : null,
        dnBlob   ? 'depth_norm.png'      : null,
        props.stereoResult ? 'stereo_left.png / stereo_right.png' : null,
        ssBlob   ? 'preview_3d.png'      : null,
      ].filter(Boolean),
    }, null, 2))

    // 7. 压缩 & 下载
    exportStatus.value = '压缩中…'
    const blob = await zip.generateAsync(
      { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } },
      ({ percent }) => { exportStatus.value = `压缩中 ${percent.toFixed(0)}%` }
    )
    saveAs(blob, `${folderName}.zip`)
    exportStatus.value = '✓ 完成'
    setTimeout(() => { exportStatus.value = '' }, 2500)

  } catch (e) {
    console.error('[ExportButton] export failed:', e)
    exportStatus.value = '导出失败'
    setTimeout(() => { exportStatus.value = '' }, 2500)
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.btn-export {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 10px;
  border: 1px solid rgba(0, 212, 255, 0.35);
  background: rgba(0, 212, 255, 0.08);
  color: var(--accent);
  font-size: 0.88rem;
  font-family: 'Syne', sans-serif;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
  white-space: nowrap;
}
.btn-export:hover:not(:disabled) {
  background: rgba(0, 212, 255, 0.16);
  border-color: var(--accent);
  box-shadow: 0 0 12px rgba(0, 212, 255, 0.2);
}
.btn-export:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.export-icon { font-size: 0.9rem; }

/* 旋转加载圈 */
.export-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0, 212, 255, 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
