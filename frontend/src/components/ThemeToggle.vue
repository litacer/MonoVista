<template>
  <button
    class="theme-toggle"
    :class="{ light: !theme.isDark }"
    @click="theme.toggle()"
    :title="theme.isDark ? '切换到浅色模式' : '切换到深色模式'"
    aria-label="toggle theme"
  >
    <span class="track">
      <span class="thumb">
        <!-- 深色：月亮；浅色：太阳 -->
        <svg v-if="theme.isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      </span>
    </span>
  </button>
</template>

<script setup>
import { useThemeStore } from '@/stores/theme'
const theme = useThemeStore()
</script>

<style scoped>
.theme-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
}

.track {
  display: flex;
  align-items: center;
  width: 52px;
  height: 28px;
  border-radius: 999px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  padding: 3px;
  transition: background 0.3s ease, border-color 0.3s ease;
  position: relative;
}

.light .track {
  background: #ddeeff;
  border-color: #99ccee;
}

.thumb {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  transform: translateX(0);
  color: #000;
}

.light .thumb {
  transform: translateX(24px);
  color: #fff;
}
</style>
