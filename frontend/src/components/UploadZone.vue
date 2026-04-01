<template>
  <section class="upload-zone"
    :class="{ 'drag-over': isDragging }"
    @dragover.prevent="isDragging = true"
    @dragleave="isDragging = false"
    @drop.prevent="onDrop"
    @click="triggerInput"
  >
    <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" @change="onFileChange" hidden />
    <div class="upload-content">
      <div class="upload-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <p class="upload-title">拖拽图像至此，或点击上传</p>
      <p class="upload-hint">支持 JPG / PNG / WebP，最大 20MB</p>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['file-selected'])
const fileInput = ref(null)
const isDragging = ref(false)

function triggerInput() { fileInput.value?.click() }
function onFileChange(e) {
  const file = e.target.files[0]
  if (file) emit('file-selected', file)
}
function onDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) emit('file-selected', file)
}
</script>

<style scoped>
.upload-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: 64px 32px;
  cursor: pointer;
  transition: all 0.25s;
  text-align: center;
  background: var(--bg-card);
}
.upload-zone:hover,
.upload-zone.drag-over {
  border-color: var(--accent);
  background: rgba(0,212,255,0.04);
  box-shadow: var(--glow);
}
.upload-content { pointer-events: none; }
.upload-icon { color: var(--accent); margin-bottom: 16px; opacity: 0.8; }
.upload-title { font-size: 1.1rem; font-weight: 600; color: var(--text-pri); margin-bottom: 8px; }
.upload-hint { font-size: 0.85rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
</style>
