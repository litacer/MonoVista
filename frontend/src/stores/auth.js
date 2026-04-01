import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  registerUser,
  loginUser,
  forgotPassword,
  fetchProfile,
  updateProfile,
  setAuthToken,
  fetchCaptcha,
} from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('mv_token') || '')
  const user = ref(null)
  const loading = ref(false)
  const error = ref('')

  // ── 验证码状态 ──────────────────────────────────────────────────
  // captchaUuid  - 当前验证码对应的 Redis Key UUID
  // captchaImage - Base64 图片字符串，直接绑定到 <img src>
  const captchaUuid = ref('')
  const captchaImage = ref('')

  /** loadCaptcha — 调用后端接口刷新验证码（登录页初始化 + 点击图片时调用） */
  async function loadCaptcha() {
    try {
      const { data } = await fetchCaptcha()
      captchaUuid.value = data.uuid
      captchaImage.value = data.image
    } catch (e) {
      console.error('Failed to load captcha', e)
    }
  }

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => (user.value?.role || '').toLowerCase() === 'admin')

  function _persistToken(newToken) {
    token.value = newToken || ''
    if (token.value) {
      localStorage.setItem('mv_token', token.value)
    } else {
      localStorage.removeItem('mv_token')
    }
    setAuthToken(token.value)
  }

  async function initAuth() {
    if (!token.value) {
      setAuthToken('')
      return
    }
    setAuthToken(token.value)
    try {
      const { data } = await fetchProfile()
      user.value = data.user
    } catch {
      logout()
    }
  }

  async function register(payload) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await registerUser(payload)
      _persistToken(data.token)
      user.value = data.user
      return true
    } catch (e) {
      error.value = e?.response?.data?.error || e.message
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(payload) {
    loading.value = true
    error.value = ''
    try {
      // payload 包含 username、password、captcha_uuid、captcha_code
      // 后端校验验证码后销毁 Redis Key，再验证用户名/密码
      const { data } = await loginUser(payload)
      _persistToken(data.token)
      user.value = data.user
      return true
    } catch (e) {
      error.value = e?.response?.data?.error || e.message
      // 登录失败后自动刷新验证码，防止用户使用已失效的验证码重试
      await loadCaptcha()
      return false
    } finally {
      loading.value = false
    }
  }

  async function resetPassword(payload) {
    loading.value = true
    error.value = ''
    try {
      await forgotPassword(payload)
      return true
    } catch (e) {
      error.value = e?.response?.data?.error || e.message
      return false
    } finally {
      loading.value = false
    }
  }

  async function refreshProfile() {
    if (!token.value) return
    const { data } = await fetchProfile()
    user.value = data.user
  }

  async function saveProfile(payload) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await updateProfile(payload)
      user.value = data.user
      return true
    } catch (e) {
      error.value = e?.response?.data?.error || e.message
      return false
    } finally {
      loading.value = false
    }
  }

  function logout() {
    _persistToken('')
    user.value = null
    error.value = ''
  }

  return {
    token,
    user,
    loading,
    error,
    isLoggedIn,
    isAdmin,
    captchaUuid,
    captchaImage,
    loadCaptcha,
    initAuth,
    register,
    login,
    resetPassword,
    refreshProfile,
    saveProfile,
    logout,
  }
})
