<template>
  <div class="depth-panel">
    <div class="panel-tabs">
      <button
        v-for="tab in tabs" :key="tab.key"
        class="tab" :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>
    <div class="panel-body">
      <div class="img-row">
        <div class="img-wrap">
          <span class="img-label">原始图像</span>
          <img :src="store.original" alt="original" />
        </div>
        <div class="img-wrap">
          <span class="img-label">{{ activeTab === 'color' ? '伪彩色深度图' : '灰度深度图' }}</span>
          <img :src="activeTab === 'color' ? store.depthColor : store.depthNorm" alt="depth" />
        </div>
      </div>
      <div class="meta">
        <span class="tag">{{ store.imageSize.width }} × {{ store.imageSize.height }} px</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useDepthStore } from '@/stores/depth'
const store = useDepthStore()
const activeTab = ref('color')
const tabs = [
  { key: 'color', label: '伪彩色' },
  { key: 'gray',  label: '灰度' },
]
</script>

<style scoped>
.depth-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.panel-tabs { display: flex; border-bottom: 1px solid var(--border); }
.tab {
  flex: 1; padding: 10px;
  background: none; border: none;
  color: var(--text-sec);
  font-family: 'Syne', sans-serif; font-weight: 600; font-size: 0.9rem;
  cursor: pointer; transition: all 0.2s;
}
.tab.active {
  color: var(--accent);
  background: rgba(0,212,255,0.07);
  border-bottom: 2px solid var(--accent);
}
.panel-body { padding: 14px 16px; }
.img-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 10px;
}
.img-wrap {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg-deep);
  height: 160px;
  display: flex; align-items: center; justify-content: center;
}
.img-label {
  position: absolute; top: 6px; left: 6px;
  background: rgba(8,12,20,0.8);
  color: var(--text-sec);
  font-size: 0.7rem; font-family: 'JetBrains Mono', monospace;
  padding: 2px 7px; border-radius: 5px; z-index: 1;
}
.img-wrap img {
  max-width: 100%; max-height: 160px;
  width: auto; height: auto;
  display: block; object-fit: contain;
}
.meta { display: flex; gap: 8px; }
</style>
