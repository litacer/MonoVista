<template>
  <div class="workspace">

    <!-- ===== STEP 1: Upload ===== -->
    <section v-if="!store.sessionId" class="upload-stage">
      <header class="stage-header">
        <h2>工作台</h2>
        <p class="ws-sub">选择模型 → 上传图像 → 深度估计 → 立体生成</p>
      </header>
      <ModelSelector />
      <div v-if="store.loading" class="global-loading">
        <div class="loader"></div>
        <p>{{ store.loadingMsg }}</p>
        <p class="hint">首次使用该模型需自动下载权重，请耐心等待</p>
      </div>
      <UploadZone v-else @file-selected="onFileSelected" />
      <div v-if="store.error" class="error-msg">⚠ {{ store.error }}</div>
    </section>

    <!-- ===== STEP 2: Result ===== -->
    <section v-else class="result-stage">
      <header class="result-header">
        <div class="result-title">
          <h2>分析结果</h2>
          <span class="model-badge">{{ store.usedModelLabel }}</span>
          <span class="size-badge">{{ store.imageSize.width }}×{{ store.imageSize.height }}</span>
        </div>
        <div class="result-actions">
          <ExportButton
            :renderer="viewer3dRef?.renderer"
            :stereo-result="store.stereoResult"
          />
          <!-- 分享按钮：仅在有真实 session（非历史恢复）且有转换历史时显示 -->
          <button
            v-if="store.sessionId && !String(store.sessionId).startsWith('hist_')"
            class="btn btn-share"
            :disabled="sharing"
            :title="'生成分享链接'"
            @click="showShareDialog = true"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
            分享
          </button>
          <button class="btn btn-ghost" @click="store.reset()">↺ 重新上传</button>
        </div>
      </header>

      <div class="result-body">
        <div class="result-main">
          <DepthPanel />
          <nav class="tab-nav">
            <button v-for="tab in tabs" :key="tab.key"
              class="tab-btn" :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <span class="tab-icon">{{ tab.icon }}</span>{{ tab.label }}
            </button>
          </nav>
          <div v-if="store.loading" class="tab-loading">
            <div class="loader"></div>
            <span>{{ store.loadingMsg }}</span>
          </div>
          <div v-else class="tab-body">
            <div v-if="activeTab === 'view'"      class="tab-pane"><ViewControl /></div>
            <div v-else-if="activeTab === 'stereo'"    class="tab-pane"><StereoOutput /></div>
            <div v-else-if="activeTab === 'multiview'" class="tab-pane"><MultiviewPlayer /></div>
            <div v-else-if="activeTab === '3d'"        class="tab-pane">
              <Depth3DViewer ref="viewer3dRef" />
            </div>
            <div v-else-if="activeTab === 'repair'"    class="tab-pane"><DepthRepairTool /></div>
          </div>
          <div v-if="store.error" class="error-msg">⚠ {{ store.error }}</div>
        </div>
      </div>
    </section>

    <!-- ══ 分享弹窗 ══ -->
    <el-dialog v-model="showShareDialog" title="生成分享链接" width="380px" :close-on-click-modal="false">
      <div class="share-dialog-body">
        <p class="share-desc">访客无需登录即可预览 3D 深度效果（只读，不含原图下载）</p>
        <div class="share-duration">
          <span class="dur-label">有效时长</span>
          <div class="dur-chips">
            <span
              v-for="opt in durationOpts" :key="opt.value"
              class="dur-chip" :class="{ active: shareHours === opt.value }"
              @click="shareHours = opt.value"
            >{{ opt.label }}</span>
          </div>
        </div>
        <div v-if="shareUrl" class="share-result">
          <input class="share-input" :value="shareUrl" readonly @click="copyShareUrl" />
          <button class="btn btn-primary" @click="copyShareUrl">{{ copied ? '✓ 已复制' : '复制链接' }}</button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showShareDialog = false">关闭</el-button>
        <el-button type="primary" :loading="sharing" @click="generateShare">生成链接</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useDepthStore } from '@/stores/depth'
import { ElMessage } from 'element-plus'
import { createShareLink } from '@/api'
import ModelSelector   from '@/components/ModelSelector.vue'
import UploadZone      from '@/components/UploadZone.vue'
import DepthPanel      from '@/components/DepthPanel.vue'
import ViewControl     from '@/components/ViewControl.vue'
import StereoOutput    from '@/components/StereoOutput.vue'
import MultiviewPlayer from '@/components/MultiviewPlayer.vue'
import Depth3DViewer   from '@/components/Depth3DViewer.vue'
import DepthRepairTool from '@/components/DepthRepairTool.vue'
import ExportButton    from '@/components/ExportButton.vue'

const store = useDepthStore()
const activeTab = ref('view')
const tabs = [
  { key: 'view',      icon: '◈', label: '视角控制' },
  { key: 'stereo',    icon: '⊕', label: '立体图像' },
  { key: 'multiview', icon: '▶', label: '多视角动画' },
  { key: '3d',        icon: '◆', label: '3D 视差' },
  { key: 'repair',    icon: '✎', label: '深度修复' },
]
async function onFileSelected(file) {
  await store.upload(file)
  activeTab.value = 'view'
}

// ── 历史侧边栏已移至个人中心页面 ──
const viewer3dRef = ref(null)

// ── 分享链接 ────────────────────────────────────────────────────
const showShareDialog = ref(false)
const sharing         = ref(false)
const shareUrl        = ref('')
const shareHours      = ref(24)
const copied          = ref(false)

const durationOpts = [
  { label: '1 小时',  value: 1  },
  { label: '6 小时',  value: 6  },
  { label: '24 小时', value: 24 },
  { label: '3 天',    value: 72 },
]

/**
 * generateShare — 调用后端生成分享 Token。
 * 需要先从历史记录获取 conversion_id；
 * 此处从 store.sessionId 推断（upload 后后端返回的 session_id
 * 与 conversion_history.id 绑定，通过 /history 接口获取最新一条）。
 */
async function generateShare() {
  sharing.value  = true
  shareUrl.value = ''
  try {
    // 取最新一条历史记录的 id（upload 后自动保存）
    const { data: histData } = await import('@/api').then(m => m.fetchHistory(1))
    const convId = histData?.records?.[0]?.id
    if (!convId) {
      ElMessage.warning('请先保存转换结果到历史记录后再分享')
      return
    }
    const { data } = await createShareLink(convId, shareHours.value)
    shareUrl.value = window.location.origin + data.share_url
    ElMessage.success(`链接有效期 ${shareHours.value} 小时`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '生成失败')
  } finally {
    sharing.value = false
  }
}

function copyShareUrl() {
  navigator.clipboard.writeText(shareUrl.value).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}
</script>

<style scoped>
.workspace { max-width: 1400px; margin: 0 auto; padding: 40px 32px 80px; }
.upload-stage { display: flex; flex-direction: column; gap: 24px; }
.stage-header h2 { font-size: 1.8rem; font-weight: 800; color: var(--text-pri); margin-bottom: 4px; }
.ws-sub { font-size: 0.88rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
.global-loading {
  display: flex; flex-direction: column; align-items: center; gap: 16px;
  padding: 60px; text-align: center; color: var(--text-sec);
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg);
}
.global-loading .hint { font-size: 0.82rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
.result-stage { display: flex; flex-direction: column; gap: 24px; }
.result-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.result-title { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.result-title h2 { font-size: 1.6rem; font-weight: 800; color: var(--text-pri); }
.result-actions { display: flex; gap: 10px; }
.model-badge { padding: 4px 12px; border-radius: 999px; background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.25); color: var(--accent); font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.size-badge { padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); color: var(--text-dim); font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; }

/* ── 主内容布局 ── */
.result-body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  align-items: start;
}
.result-main { display: flex; flex-direction: column; gap: 24px; min-width: 0; }

/* ── Tab / 其他样式 ── */
.tab-nav { display: flex; gap: 4px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 6px; }
.tab-btn { flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 16px; border-radius: 10px; border: none; background: none; color: var(--text-sec); font-family: 'Syne', sans-serif; font-weight: 600; font-size: 0.92rem; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
.tab-btn:hover { color: var(--text-pri); background: rgba(255,255,255,0.04); }
.tab-btn.active { background: rgba(0,212,255,0.1); color: var(--accent); border: 1px solid rgba(0,212,255,0.2); }
.tab-icon { font-size: 1rem; }
.tab-loading { min-height: 200px; display: flex; align-items: center; justify-content: center; gap: 16px; color: var(--text-sec); font-size: 0.95rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.tab-pane { animation: fadeUp 0.3s ease; }
.error-msg { padding: 12px 16px; border-radius: var(--radius); background: rgba(255,107,107,0.1); border: 1px solid rgba(255,107,107,0.3); color: var(--accent3); font-size: 0.9rem; }

/* ── 分享按钮（简约风格，与 btn-ghost 同级） ── */
.btn-share {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 14px; border-radius: 10px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-sec); font-size: 0.88rem;
  font-family: 'Syne', sans-serif; font-weight: 600;
  cursor: pointer; transition: all 0.18s; white-space: nowrap;
}
.btn-share:hover:not(:disabled) {
  border-color: rgba(0,212,255,0.4);
  color: var(--accent);
  background: rgba(0,212,255,0.06);
}
.btn-share:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-share svg { flex-shrink: 0; }

/* ── 分享弹窗内容 ── */
.share-dialog-body { display: flex; flex-direction: column; gap: 16px; }
.share-desc { font-size: 0.84rem; color: var(--text-sec); margin: 0; }
.share-duration { display: flex; flex-direction: column; gap: 8px; }
.dur-label { font-size: 0.8rem; color: var(--text-sec); }
.dur-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.dur-chip {
  padding: 5px 14px; border-radius: 999px; font-size: 0.82rem;
  border: 1px solid var(--border); background: var(--bg-raised);
  cursor: pointer; transition: all 0.15s; user-select: none;
}
.dur-chip:hover { border-color: var(--accent); }
.dur-chip.active { border-color: var(--accent); background: rgba(0,212,255,0.1); color: var(--accent); }
.share-result { display: flex; gap: 8px; align-items: center; }
.share-input {
  flex: 1; padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg-deep);
  color: var(--text-pri); font-size: 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  outline: none; cursor: pointer;
}
@media (max-width: 900px) {
  .result-body.with-history { grid-template-columns: 1fr; }
  .history-sidebar { position: static; max-height: 360px; }
}
@media (max-width: 680px) {
  .tab-btn { font-size: 0.8rem; padding: 10px 8px; }
  .tab-icon { display: none; }
  .workspace { padding: 24px 16px 60px; }
}
</style>
