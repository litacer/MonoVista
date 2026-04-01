<template>
  <div class="multiview-panel">
    <div class="panel-header">
      <h3>多视角动画</h3>
      <div class="controls">
        <label>视角数</label>
        <select v-model.number="numViews" class="sel">
          <option v-for="n in [5,7,9,11,15]" :key="n" :value="n">{{ n }}</option>
        </select>
        <label>最大位移</label>
        <input type="range" min="0.03" max="0.15" step="0.01" v-model.number="maxShift" class="slider" />
        <span class="val">{{ maxShift.toFixed(2) }}</span>
        <button class="btn btn-primary" :disabled="store.loading" @click="generate">生成</button>
      </div>
    </div>
    <div class="viewer">
      <img v-if="currentFrame" :src="currentFrame" alt="multiview" class="frame-img" />
      <div v-else class="empty"><p>点击「生成」后播放多视角动画</p></div>
    </div>
    <div v-if="store.multiviewResult" class="player-controls">
      <button class="btn btn-ghost icon-btn" @click="prev">‹</button>
      <button class="btn btn-primary play-btn" @click="togglePlay">{{ playing ? '⏸ 暂停' : '▶ 播放' }}</button>
      <button class="btn btn-ghost icon-btn" @click="next">›</button>
      <div class="speed-group">
        <span class="val">速度</span>
        <select v-model.number="interval" class="sel">
          <option :value="60">快</option>
          <option :value="120">中</option>
          <option :value="220">慢</option>
        </select>
      </div>
      <span class="counter">{{ currentIndex + 1 }} / {{ total }}</span>
      <div class="thumb-strip">
        <img v-for="(v, i) in store.multiviewResult.views" :key="i"
          :src="v" :class="{ active: i === currentIndex }"
          class="thumb" @click="jumpTo(i)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useDepthStore } from '@/stores/depth'
const store = useDepthStore()
const numViews = ref(7)
const maxShift = ref(0.08)
const interval = ref(120)
const currentIndex = ref(0)
const playing = ref(false)
let timer = null
const total = computed(() => store.multiviewResult?.views?.length ?? 0)
const currentFrame = computed(() => store.multiviewResult?.views?.[currentIndex.value] ?? null)
watch(() => store.multiviewResult, (val) => { if (val) { currentIndex.value = 0; startPlay() } })
watch(interval, () => { if (playing.value) { stopPlay(); startPlay() } })
function generate() { store.fetchMultiview(numViews.value, maxShift.value) }
function startPlay() {
  clearInterval(timer); playing.value = true
  timer = setInterval(() => { currentIndex.value = (currentIndex.value + 1) % total.value }, interval.value)
}
function stopPlay() { clearInterval(timer); playing.value = false }
function togglePlay() { playing.value ? stopPlay() : startPlay() }
function prev() { stopPlay(); currentIndex.value = (currentIndex.value - 1 + total.value) % total.value }
function next() { stopPlay(); currentIndex.value = (currentIndex.value + 1) % total.value }
function jumpTo(i) { stopPlay(); currentIndex.value = i }
onUnmounted(stopPlay)
</script>

<style scoped>
.multiview-panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.panel-header { padding: 12px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.panel-header h3 { font-size: 1rem; font-weight: 700; }
.controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.controls label { font-size: 0.8rem; color: var(--text-sec); white-space: nowrap; }
.sel { background: var(--bg-deep); border: 1px solid var(--border); color: var(--text-pri); border-radius: 6px; padding: 3px 7px; font-size: 0.82rem; cursor: pointer; }
.slider { width: 80px; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--border); cursor: pointer; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--accent); cursor: pointer; }
.val { font-size: 0.78rem; color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.viewer { height: 400px; background: var(--bg-deep); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.frame-img { max-width: 100%; max-height: 400px; width: auto; height: auto; display: block; object-fit: contain; }
.empty { color: var(--text-dim); font-size: 0.9rem; padding: 40px; text-align: center; }
.player-controls { padding: 10px 14px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.icon-btn { font-size: 1.3rem; padding: 5px 12px; }
.play-btn { min-width: 86px; justify-content: center; }
.speed-group { display: flex; align-items: center; gap: 5px; margin-left: 6px; }
.counter { font-size: 0.76rem; font-family: 'JetBrains Mono', monospace; color: var(--text-dim); margin-left: auto; }
.thumb-strip { display: flex; gap: 5px; overflow-x: auto; width: 100%; padding: 2px 0; }
.thumb { width: 44px; height: 33px; object-fit: cover; border-radius: 4px; border: 2px solid transparent; cursor: pointer; flex-shrink: 0; opacity: 0.55; transition: all 0.15s; }
.thumb.active, .thumb:hover { border-color: var(--accent); opacity: 1; }
</style>
