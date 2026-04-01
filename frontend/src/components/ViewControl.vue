<template>
  <div class="view-ctrl">
    <div class="ctrl-header">
      <h3>视角控制</h3>
      <span class="tag">shift: {{ shiftDisplay }}</span>
    </div>
    <div class="slider-wrap">
      <span class="slider-label">← 左视角</span>
      <input type="range" min="-0.15" max="0.15" step="0.005"
        v-model.number="shift" @input="onShiftInput" class="slider" />
      <span class="slider-label">右视角 →</span>
    </div>
    <div class="view-output">
      <div v-if="store.loading" class="loading-state">
        <div class="loader"></div><span>生成中...</span>
      </div>
      <img v-else-if="displaySrc" :src="displaySrc" alt="virtual view" class="view-img" />
      <div v-else class="view-placeholder">
        <p>拖动滑块预览虚拟视角</p>
        <p class="hint">向左/右拖动模拟不同相机位置</p>
      </div>
    </div>
    <div v-if="displaySrc" class="download-row">
      <a :href="displaySrc" download="monovista_view.png" class="btn btn-ghost">↓ 下载</a>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDepthStore } from '@/stores/depth'
const store = useDepthStore()
const shift = ref(0)
const shiftDisplay = computed(() => {
  const v = shift.value
  if (v > 0) return `+${v.toFixed(3)}`
  if (v < 0) return v.toFixed(3)
  return '0 (原始视角)'
})
const displaySrc = computed(() => store.currentView || store.original)
let debounceTimer = null
function onShiftInput() {
  clearTimeout(debounceTimer)
  if (Math.abs(shift.value) < 0.002) { store.currentView = null; return }
  debounceTimer = setTimeout(() => store.fetchView(shift.value), 350)
}
</script>

<style scoped>
.view-ctrl {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 20px;
  display: flex; flex-direction: column; gap: 16px;
}
.ctrl-header { display: flex; align-items: center; justify-content: space-between; }
.ctrl-header h3 { font-size: 1rem; font-weight: 700; }
.slider-wrap { display: flex; align-items: center; gap: 12px; }
.slider-label { font-size: 0.78rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; white-space: nowrap; }
.slider {
  flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px;
  background: linear-gradient(to right, #7b5ea7, var(--border) 50%, var(--accent));
  outline: none; cursor: pointer;
}
.slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 20px; height: 20px;
  border-radius: 50%; background: var(--accent);
  box-shadow: 0 0 8px rgba(0,212,255,0.5); cursor: pointer; border: 2px solid var(--bg-deep);
}
.view-output {
  height: 400px; background: var(--bg-deep);
  border-radius: var(--radius); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.view-img { max-width: 100%; max-height: 400px; width: auto; height: auto; display: block; object-fit: contain; }
.loading-state { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--text-sec); font-size: 0.9rem; }
.view-placeholder { text-align: center; color: var(--text-dim); }
.view-placeholder p { margin-bottom: 6px; }
.view-placeholder .hint { font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; }
.download-row { display: flex; justify-content: flex-end; }
</style>
