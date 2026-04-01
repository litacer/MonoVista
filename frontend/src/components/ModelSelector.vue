<template>
  <div class="model-selector" ref="rootRef">
    <div class="ms-header">
      <h3>深度估计模型</h3>
    </div>

    <!-- 触发按钮 -->
    <button class="ms-trigger" @click="open = !open" :class="{ active: open }">
      <span class="ms-trigger-inner">
        <span class="ms-trigger-label">
          <span class="ms-trigger-name">{{ selected ? selected.label : '选择模型…' }}</span>
          <span v-if="selected?.description" class="ms-trigger-meta">{{ selected.description }}</span>
        </span>
        <svg class="ms-chevron" :class="{ flipped: open }" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 4L6 8L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    </button>

    <!-- 下拉面板 -->
    <transition name="dropdown">
      <div v-if="open" class="ms-dropdown">
        <!-- 列头 -->
        <div class="ms-col-head">
          <span>MODEL</span>
          <span>DESCRIPTION</span>
        </div>

        <transition-group name="row" tag="ul" class="ms-list">
          <li
            v-for="m in store.models"
            :key="m.key"
            class="ms-row"
            :class="{ active: store.selectedModel === m.key }"
            @click="select(m.key)"
            :title="m.description || ''"
          >
            <span class="ms-bar"></span>
            <span class="ms-cell ms-name">
              <span class="ms-key">{{ m.label }}</span>
            </span>
            <span class="ms-cell ms-desc-col">{{ m.description || '暂无描述' }}</span>
          </li>
        </transition-group>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDepthStore } from '@/stores/depth'

const store = useDepthStore()
const open = ref(false)
const rootRef = ref(null)

onMounted(() => {
  if (store.models.length === 0) store.loadModels()
  document.addEventListener('click', onOutside)
})
onUnmounted(() => document.removeEventListener('click', onOutside))

function onOutside(e) {
  if (rootRef.value && !rootRef.value.contains(e.target)) open.value = false
}

const selected = computed(() => store.models.find(m => m.key === store.selectedModel))

function select(key) {
  store.selectedModel = key
  open.value = false
}
</script>

<style scoped>
/* ── 容器 ── */
.model-selector {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── 标题 ── */
.ms-header h3 {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 8px;
}

/* ── 触发按钮 ── */
.ms-trigger {
  width: 100%;
  background: rgba(14, 20, 32, 0.55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s ease, background 0.18s ease;
}
.ms-trigger:hover,
.ms-trigger.active {
  border-color: rgba(0,212,255,0.45);
}
.ms-trigger.active {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-bottom-color: transparent;
}
html.light-mode .ms-trigger {
  background: rgba(255,255,255,0.6);
}

.ms-trigger-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ms-trigger-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}
.ms-trigger-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-pri);
  font-family: 'Syne', sans-serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ms-trigger-meta {
  font-size: 0.68rem;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-dim);
  letter-spacing: 0.04em;
}

.ms-chevron {
  flex-shrink: 0;
  color: var(--text-dim);
  transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1);
}
.ms-chevron.flipped { transform: rotate(180deg); }

/* ── 下拉面板 ── */
.ms-dropdown {
  position: absolute;
  top: 100%;
  left: 0; right: 0;
  z-index: 200;
  background: rgba(10, 16, 28, 0.82);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(0,212,255,0.35);
  border-top: none;
  border-radius: 0 0 8px 8px;
  overflow: hidden;
}
html.light-mode .ms-dropdown {
  background: rgba(245,248,255,0.88);
}

/* ── 列头 ── */
.ms-col-head {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  padding: 6px 14px 6px 20px;
  border-bottom: 1px solid var(--border);
  gap: 10px;
}
.ms-col-head span {
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
}

/* ── 列表 ── */
.ms-list { list-style: none; }

/* ── 行 ── */
.ms-row {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  align-items: center;
  gap: 10px;
  padding: 10px 14px 10px 20px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s ease;
}
.ms-row:last-child { border-bottom: none; }
.ms-row:hover      { background: rgba(255,255,255,0.03); }
.ms-row.active     { background: rgba(0,212,255,0.04); }
html.light-mode .ms-row:hover  { background: rgba(0,0,0,0.03); }

/* ── 1px 高亮条 ── */
.ms-bar {
  position: absolute;
  left: 0; top: 8px; bottom: 8px;
  width: 1px;
  background: transparent;
  transition: background 0.15s ease;
}
.ms-row.active .ms-bar { background: var(--accent); }

/* ── 单元格 ── */
.ms-cell {
  font-size: 0.78rem;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
  transition: color 0.15s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ms-row.active .ms-cell { color: var(--text-sec); }

/* ── 名称列 ── */
.ms-name {
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: hidden;
}
.ms-key {
  font-size: 0.84rem;
  font-weight: 400;
  color: var(--text-sec);
  font-family: 'Syne', sans-serif;
  transition: font-weight 0.15s, color 0.15s;
}
.ms-row.active .ms-key {
  font-weight: 700;
  color: var(--text-pri);
}
.ms-desc-col {
  font-size: 0.68rem;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 下拉动画 ── */
.dropdown-enter-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.dropdown-leave-active { transition: opacity 0.14s ease, transform 0.14s ease; }
.dropdown-enter-from   { opacity: 0; transform: translateY(-6px); }
.dropdown-leave-to     { opacity: 0; transform: translateY(-4px); }

/* ── 行动画 ── */
.row-enter-active,
.row-leave-active  { transition: opacity 0.18s ease, transform 0.18s ease; }
.row-enter-from    { opacity: 0; transform: translateY(-4px); }
.row-leave-to      { opacity: 0; transform: translateY(4px); }

/* ── 响应式 ── */
@media (max-width: 600px) {
  .ms-col-head { grid-template-columns: 1fr; }
  .ms-row      { grid-template-columns: 1fr; }
}
</style>
