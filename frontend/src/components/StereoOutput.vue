<template>
  <div class="stereo-panel">
    <div class="panel-header">
      <h3>立体图像输出</h3>
      <div class="controls">
        <label class="shift-label">视差强度</label>
        <input type="range" min="0.01" max="0.15" step="0.005" v-model.number="shift" class="slider" />
        <span class="shift-val">{{ shift.toFixed(3) }}</span>
        <button class="btn btn-primary" :disabled="store.loading" @click="generate">生成</button>
      </div>
    </div>
    <div class="mode-tabs">
      <button v-for="m in modes" :key="m.key"
        class="tab" :class="{ active: activeMode === m.key }" @click="activeMode = m.key"
      >{{ m.label }}</button>
    </div>
    <div class="output-area">
      <img v-if="currentSrc" :src="currentSrc" :alt="activeMode" class="stereo-img" />
      <div v-else class="empty"><p>点击「生成」后在此预览立体图像</p></div>
    </div>
    <div v-if="currentSrc" class="action-row">
      <a :href="currentSrc" :download="`monovista_${activeMode}.png`" class="btn btn-ghost">↓ 下载</a>
      <span class="hint">{{ modeHint }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDepthStore } from '@/stores/depth'
const store = useDepthStore()
const activeMode = ref('anaglyph')
const shift = ref(0.05)
const modes = [
  { key: 'anaglyph',     label: '红青 3D' },
  { key: 'side_by_side', label: '左右并排 SBS' },
  { key: 'left',         label: '左视图' },
  { key: 'right',        label: '右视图' },
]
const modeHints = {
  anaglyph: '配红青3D眼镜观看', side_by_side: '适用于VR头显或交叉眼法',
  left: '左眼视角', right: '右眼视角',
}
const currentSrc = computed(() => store.stereoResult?.[activeMode.value] ?? null)
const modeHint   = computed(() => modeHints[activeMode.value] ?? '')
function generate() { store.fetchStereo(shift.value) }
</script>

<style scoped>
.stereo-panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.panel-header {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
}
.panel-header h3 { font-size: 1rem; font-weight: 700; }
.controls { display: flex; align-items: center; gap: 10px; }
.shift-label { font-size: 0.82rem; color: var(--text-sec); white-space: nowrap; }
.slider { width: 120px; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--border); outline: none; cursor: pointer; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%; background: var(--accent); cursor: pointer; }
.shift-val { font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; color: var(--accent); min-width: 38px; }
.mode-tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-deep); }
.tab { flex: 1; padding: 9px; border: none; background: none; color: var(--text-sec); font-family: 'Syne', sans-serif; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.18s; border-bottom: 2px solid transparent; }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); background: rgba(0,212,255,0.05); }
.output-area { height: 400px; background: var(--bg-deep); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.stereo-img { max-width: 100%; max-height: 400px; width: auto; height: auto; display: block; object-fit: contain; }
.empty { color: var(--text-dim); font-size: 0.9rem; padding: 40px; text-align: center; }
.action-row { padding: 10px 20px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 16px; }
.hint { font-size: 0.78rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
</style>
