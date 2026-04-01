import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  fetchModels, fetchActiveModels, uploadImage, generateView,
  generateStereo, generateMultiview,
  fetchHistory, saveHistory,
} from '@/api'

export const useDepthStore = defineStore('depth', () => {
  const models = ref([])
  const selectedModel = ref('dav2-small')

  const sessionId = ref(null)
  const original = ref(null)
  const depthColor = ref(null)
  const depthNorm = ref(null)
  const usedModelLabel = ref('')
  const imageSize = ref({ width: 0, height: 0 })

  const currentView = ref(null)
  const stereoResult = ref(null)
  const multiviewResult = ref(null)

  const loading = ref(false)
  const loadingMsg = ref('')
  const error = ref(null)

  // ── 转换历史 ─────────────────────────────────────────────────
  // history      - 从后端拉取的历史记录列表
  // historyLoaded - 是否已加载过（避免重复请求）
  const history = ref([])
  const historyLoaded = ref(false)

  async function loadModels() {
    try {
      const { data } = await fetchActiveModels()
      models.value = data.models || []
      if (!models.value.length) {
        selectedModel.value = ''
        return
      }
      // 当前选择不在可见模型中时，自动回退到第一项
      if (!models.value.some(m => m.key === selectedModel.value)) {
        selectedModel.value = models.value[0].key
      }
    } catch (e) {
      console.error('Failed to load active models', e)
      // 兜底：若 active 接口异常，退回原始模型接口
      try {
        const { data } = await fetchModels()
        models.value = data.models || []
      } catch (err) {
        console.error('Fallback load models failed', err)
      }
    }
  }

  async function upload(file) {
    loading.value = true
    loadingMsg.value = '深度估计中，请稍候...'
    error.value = null
    try {
      const { data } = await uploadImage(file, selectedModel.value)
      sessionId.value = data.session_id
      original.value = data.original
      depthColor.value = data.depth_color
      depthNorm.value = data.depth_norm
      usedModelLabel.value = data.model_label
      imageSize.value = { width: data.width, height: data.height }
      currentView.value = null
      stereoResult.value = null
      multiviewResult.value = null
    } catch (e) {
      error.value = e?.response?.data?.error || e.message
    } finally {
      loading.value = false
      loadingMsg.value = ''
    }
  }

  async function fetchView(shift) {
    if (!sessionId.value) return
    loading.value = true
    loadingMsg.value = '生成视角中...'
    try {
      const { data } = await generateView(sessionId.value, shift)
      currentView.value = data.image
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
      loadingMsg.value = ''
    }
  }

  async function fetchStereo(shift) {
    if (!sessionId.value) return
    loading.value = true
    loadingMsg.value = '生成立体图像中...'
    try {
      const { data } = await generateStereo(sessionId.value, shift)
      stereoResult.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
      loadingMsg.value = ''
    }
  }

  async function fetchMultiview(numViews, maxShift) {
    if (!sessionId.value) return
    loading.value = true
    loadingMsg.value = '生成多视角序列中...'
    try {
      const { data } = await generateMultiview(sessionId.value, numViews, maxShift)
      multiviewResult.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
      loadingMsg.value = ''
    }
  }

  function reset() {
    sessionId.value = null
    original.value = null
    depthColor.value = null
    depthNorm.value = null
    usedModelLabel.value = ''
    currentView.value = null
    stereoResult.value = null
    multiviewResult.value = null
    error.value = null
  }

  /**
   * restoreFromRecord — 从历史记录恢复工作台状态（无需重新推理）
   *
   * 将 OSS URL 直接填入 store 对应字段，DepthPanel 会自动展示
   * original/depthColor/depthNorm 图像。后续 Tab 操作（视角/立体/3D）
   * 仍需后端 session，此处生成一个伪 sessionId 标记"已从历史恢复"。
   * 如需完整推理能力，用户可点击"重新上传"。
   *
   * @param {object} rec - ConversionHistory.to_dict() 对象
   */
  function restoreFromRecord(rec) {
    // 清空旧状态，防止 Tab 内容残留
    reset()
    // 用 OSS URL 作为展示源（DepthPanel 直接渲染 <img :src=>）
    sessionId.value     = `hist_${rec.id}`   // 伪 session，标记历史模式
    original.value      = rec.original_url
    depthColor.value    = rec.depth_url
    depthNorm.value     = rec.depth_url
    usedModelLabel.value = rec.model_label || rec.model_key || '历史记录'
    imageSize.value      = { width: rec.image_width || 0, height: rec.image_height || 0 }
  }

  // ── 历史记录操作 ──────────────────────────────────────────────

  /**
   * loadHistory — 从后端拉取当前用户的转换历史列表
   * 每次打开历史面板时调用，结果缓存在 history ref 中
   */
  async function loadHistory(limit = 20) {
    try {
      const { data } = await fetchHistory(limit)
      history.value = data.records || []
      historyLoaded.value = true
    } catch (e) {
      console.error('Failed to load history', e)
    }
  }

  /**
   * updateHistoryConfig — 更新最近一条历史记录的 render_config
   * 当用户调整视差强度后调用，将当前参数快照保存到历史
   *
   * 注意：此处调用后端 POST /history 重新创建一条记录，
   * 以保留每次调整的完整快照（类似版本快照语义）。
   * 如果只需更新最新一条，可改为 PATCH 接口。
   *
   * @param {object} renderConfig  - 3D 渲染参数，如 { intensity: 0.06 }
   * @param {string} originalUrl   - 当前原图 OSS URL
   * @param {string} depthUrl      - 当前深度图 OSS URL
   */
  async function updateHistoryConfig(renderConfig, originalUrl, depthUrl) {
    if (!originalUrl || !depthUrl) return
    try {
      await saveHistory({
        original_url: originalUrl,
        depth_url: depthUrl,
        model_key: selectedModel.value,
        model_label: usedModelLabel.value,
        image_width: imageSize.value.width,
        image_height: imageSize.value.height,
        render_config: renderConfig,
      })
      // 保存后刷新历史列表
      await loadHistory()
    } catch (e) {
      console.error('Failed to save history config', e)
    }
  }

  return {
    models, selectedModel,
    sessionId, original, depthColor, depthNorm,
    usedModelLabel, imageSize,
    currentView, stereoResult, multiviewResult,
    loading, loadingMsg, error,
    history, historyLoaded,
    loadModels, upload, fetchView, fetchStereo, fetchMultiview, reset, restoreFromRecord,
    loadHistory, updateHistoryConfig,
  }
})
