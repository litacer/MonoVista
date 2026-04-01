import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(
    localStorage.getItem('mv_theme') !== 'light'
  )

  function applyTheme(dark) {
    if (dark) {
      document.documentElement.classList.remove('light-mode')
    } else {
      document.documentElement.classList.add('light-mode')
    }
  }

  function toggle() {
    isDark.value = !isDark.value
  }

  watch(isDark, (dark) => {
    applyTheme(dark)
    localStorage.setItem('mv_theme', dark ? 'dark' : 'light')
  }, { immediate: true })

  return { isDark, toggle }
})
