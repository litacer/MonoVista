import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  //baseURL: 'https://6d8061b8.r35.cpolar.top/api',
  timeout: 180000,
})

// -----------------------------------------------------------------------------
// Axios 拦截器（管理端授权逻辑说明）
//
// 1) 请求拦截器：统一从 localStorage 注入 Bearer Token。
//    这样用户端与管理端共享同一套 JWT，不需要维护两套 token。
//
// 2) 响应拦截器：当访问 /api/admin/* 返回 401/403 时，
//    说明 token 失效或角色不足（role !== admin），
//    自动跳转到统一登录页 /auth/login，并附带 redirect 参数。
//    登录成功后由路由守卫按 role 自动分流到 admin 或 user 端。
// -----------------------------------------------------------------------------
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('mv_token') || ''
  
  //config.headers['ngrok-skip-browser-warning'] = 'true'
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res,
  (error) => {
    // 如果 cpolar 域名过期或隧道关闭，通常会报 404 或 502
    // if (!error.response) {
    //   console.error('无法连接到后端服务器，请检查 cpolar 隧道是否开启')
    // }

    const status = error?.response?.status
    const url = error?.config?.url || ''
    const isAdminApi = String(url).startsWith('/admin')

    // 管理端专属授权失败处理：防止无权限用户停留在后台页面
    if (isAdminApi && (status === 401 || status === 403)) {
      localStorage.removeItem('mv_token')
      const redirect = encodeURIComponent(window.location.pathname)
      window.location.href = `/auth/login?redirect=${redirect}`
    }
    return Promise.reject(error)
  },
)

export function setAuthToken(token = '') {
  if (token) {
    http.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete http.defaults.headers.common.Authorization
  }
}

export const fetchModels = () => http.get('/models')
export const fetchActiveModels = () => http.get('/models/active')

export const uploadImage = (file, modelKey, maxSize = 1024) => {
  const form = new FormData()
  form.append('file', file)
  form.append('model_key', modelKey)
  form.append('max_size', maxSize)
  return http.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const generateView = (sessionId, shift) =>
  http.post('/generate', { session_id: sessionId, shift })

export const generateStereo = (sessionId, shift) =>
  http.post('/stereo', { session_id: sessionId, shift })

export const generateMultiview = (sessionId, numViews = 7, maxShift = 0.08) =>
  http.post('/multiview', { session_id: sessionId, num_views: numViews, max_shift: maxShift })

export const registerUser = (payload) => http.post('/auth/register', payload)
export const loginUser = (payload) => http.post('/auth/login', payload)
export const forgotPassword = (payload) => http.post('/auth/forgot-password', payload)
export const fetchProfile = () => http.get('/auth/profile')
export const updateProfile = (payload) => http.put('/auth/profile', payload)
export const changePassword = (payload) => http.post('/auth/change-password', payload)
export const fetchAuditLogs = (limit = 20) => http.get(`/audit/logs?limit=${limit}`)
export const fetchCaptcha = () => http.get('/auth/captcha')

// ── 账号绑定 ──
export const sendBindCode = (type, target) =>
  http.post('/auth/bind/send-code', { type, target })
export const confirmBind = (type, target, code) =>
  http.post('/auth/bind/confirm', { type, target, code })

// ── 转换历史 ──
export const saveHistory = (payload) => http.post('/history', payload)
export const fetchHistory = (limit = 20) => http.get(`/history?limit=${limit}`)

// 管理端 API
export const fetchAdminDashboard = () => http.get('/admin/dashboard')
export const fetchAdminActivityFeed = () => http.get('/admin/activity-feed')
export const fetchAdminConversions = (params = {}) => http.get('/admin/conversions', { params })
export const fetchAdminAuditLogs = (params = {}) => http.get('/admin/audit-logs', { params })

// 模型实验室（Model Registry）
export const fetchAdminModelRegistry = () => http.get('/admin/model-registry')
export const activateAdminModel = (payload) => http.post('/admin/model-registry/activate', payload)
export const updateAdminRuntime = (payload) => http.put('/admin/model-registry/runtime', payload)
export const updateAdminModelVisibility = (modelId, isVisible) =>
  http.put(`/admin/model-registry/${modelId}/visibility`, { is_visible: isVisible })
export const updateAdminModelMeta = (modelId, payload) =>
  http.put(`/admin/model-registry/${modelId}/meta`, payload)

export const uploadAvatar = (file) => {
  const form = new FormData()
  form.append('file', file)
  return http.post('/auth/avatar', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── 公告（用户端，无需登录）──
export const fetchAnnouncements = () => http.get('/announcements')

// ── 公告管理（管理端）──
export const fetchAdminAnnouncements = () => http.get('/admin/announcements')
export const createAdminAnnouncement = (payload) => http.post('/admin/announcements', payload)
export const updateAdminAnnouncement = (id, payload) => http.put(`/admin/announcements/${id}`, payload)
export const toggleAdminAnnouncement = (id) => http.patch(`/admin/announcements/${id}/toggle`)
export const deleteAdminAnnouncement = (id) => http.delete(`/admin/announcements/${id}`)

// ── 分享链接 ──
export const createShareLink = (conversionId, hours) =>
  http.post('/share/create', { conversion_id: conversionId, hours })
export const fetchShareView = (token) =>
  http.get(`/share/view/${token}`)

// ── Benchmark ──
export const runBenchmark = (file, modelIds) => {
  const form = new FormData()
  form.append('file', file)
  form.append('model_ids', JSON.stringify(modelIds))
  return http.post('/admin/benchmark/run', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  })
}
