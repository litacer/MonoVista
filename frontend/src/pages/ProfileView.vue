<template>
  <div class="profile-page" v-if="auth.user">

    <!-- ══ 左栏：个人资料 ══ -->
    <aside class="left-col">
      <div class="avatar-block">
        <div class="avatar-wrap">
          <img :src="previewAvatar || auth.user.avatar_url || fallbackAvatar" class="avatar" alt="avatar" />
          <label class="avatar-btn" title="更换头像">
            <input type="file" accept="image/*" @change="onAvatarPick" hidden />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </label>
        </div>
        <h2 class="user-name">{{ auth.user.nickname || auth.user.username }}</h2>
        <p class="user-handle">@{{ auth.user.username }}</p>
        <div class="hero-badges">
          <span class="badge level">{{ auth.user.level }}</span>
          <span class="badge role" :class="auth.user.role">{{ auth.user.role }}</span>
        </div>
        <div class="sig-wrap">
          <template v-if="!editingSig">
            <span class="sig-text" @click="startEditSig">{{ auth.user.signature || '点击添加签名…' }}</span>
          </template>
          <template v-else>
            <input ref="sigInputRef" v-model="sigDraft" class="sig-input"
              maxlength="100" placeholder="最多 100 字"
              @blur="saveSig" @keydown.enter="saveSig" @keydown.esc="cancelSig" />
            <span class="sig-counter">{{ sigDraft.length }}/100</span>
          </template>
        </div>
      </div>

      <div class="field-list">
        <div class="field-row">
          <span class="field-label">昵称</span>
          <template v-if="!editField.nickname">
            <span class="field-val">{{ auth.user.nickname }}</span>
            <button class="field-btn" @click="startEdit('nickname')">编辑</button>
          </template>
          <template v-else>
            <input class="field-input" v-model="fieldDraft" />
            <button class="field-btn primary" @click="confirmEdit('nickname')">保存</button>
            <button class="field-btn" @click="cancelEdit('nickname')">取消</button>
          </template>
        </div>
        <div class="field-row">
          <span class="field-label">用户名</span>
          <span class="field-val mono">{{ auth.user.username }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">邮箱</span>
          <span class="field-val" :class="{ dim: !auth.user.email }">{{ auth.user.email || '未绑定' }}</span>
          <button class="field-btn primary" @click="openBind('email')">{{ auth.user.email ? '换绑' : '绑定' }}</button>
        </div>
        <div class="field-row">
          <span class="field-label">手机号</span>
          <span class="field-val" :class="{ dim: !auth.user.phone }">{{ auth.user.phone || '未绑定' }}</span>
          <button class="field-btn primary" @click="openBind('phone')">{{ auth.user.phone ? '换绑' : '绑定' }}</button>
        </div>
        <div class="field-row">
          <span class="field-label">注册于</span>
          <span class="field-val mono dim">{{ fmtTime(auth.user.created_at) }}</span>
        </div>
      </div>

      <button class="change-pwd-btn" @click="showPwdDialog = true">修改密码</button>
      <button class="logout-btn" @click="logout">退出登录</button>
    </aside>

    <!-- ══ 右栏：Tab 内容 ══ -->
    <main class="right-col">
      <nav class="tab-bar">
        <button
          v-for="t in tabs" :key="t.key"
          class="tab-btn" :class="{ active: activeTab === t.key }"
          @click="activeTab = t.key"
        >
          <span class="tab-icon">{{ t.icon }}</span>
          {{ t.label }}
          <span v-if="t.key === 'history' && depthStore.history.length" class="tab-count">
            {{ depthStore.history.length }}
          </span>
        </button>
      </nav>

      <!-- 最近动态 -->
      <div v-if="activeTab === 'activity'" class="tab-pane">
        <div v-if="auditLoading" class="pane-loading"><div class="loader"></div></div>
        <p v-else-if="!auditLogs.length" class="pane-empty">暂无操作记录</p>
        <ul v-else class="audit-list">
          <li v-for="log in auditLogs" :key="log.id" class="audit-item">
            <span class="audit-dot"></span>
            <div class="audit-body">
              <span class="audit-action">{{ actionLabel(log.action) }}</span>
              <span class="audit-meta">{{ log.os }} · {{ log.browser }} · {{ log.device }}</span>
              <span class="audit-meta">IP: {{ log.ip }} · {{ fmtTime(log.created_at) }}</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- 转换历史 -->
      <div v-else-if="activeTab === 'history'" class="tab-pane">
        <div v-if="histLoading" class="pane-loading"><div class="loader"></div></div>
        <p v-else-if="!depthStore.history.length" class="pane-empty">暂无转换记录</p>
        <div v-else class="hist-grid">
          <div
            v-for="rec in depthStore.history" :key="rec.id"
            class="hist-card" @click="goToWorkspace(rec)"
          >
            <div class="hist-thumb-wrap">
              <img class="hist-thumb" :src="rec.thumbnail_url" :alt="rec.model_label" loading="lazy" />
              <img class="hist-depth" :src="rec.depth_url" alt="depth" loading="lazy" />
              <span class="hist-hint">↗ 工作台</span>
            </div>
            <div class="hist-info">
              <span class="hist-model">{{ rec.model_label || rec.model_key }}</span>
              <span class="hist-sub">{{ rec.image_width }}×{{ rec.image_height }} · {{ ((rec.render_config?.intensity ?? 0.04)*100).toFixed(1) }}%</span>
              <span class="hist-time">{{ fmtTime(rec.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- ══ 绑定弹窗 ══ -->
    <el-dialog
      v-model="bindDialog.visible"
      :title="bindDialog.type === 'email' ? '绑定邮箱' : '绑定手机号'"
      width="420px" :close-on-click-modal="false"
    >
      <div class="bind-form">
        <el-form label-width="80px" @submit.prevent>
          <el-form-item :label="bindDialog.type === 'email' ? '邮箱' : '手机号'">
            <el-input v-model="bindDialog.target"
              :placeholder="bindDialog.type === 'email' ? '输入邮箱地址' : '输入手机号'"
              :type="bindDialog.type === 'email' ? 'email' : 'tel'" />
          </el-form-item>
          <el-form-item label="验证码">
            <div class="code-row">
              <el-input v-model="bindDialog.code" placeholder="6 位验证码" maxlength="6" />
              <el-button
                :disabled="bindDialog.countdown > 0 || !bindDialog.target"
                @click="sendCode" :loading="bindDialog.sending"
              >
                {{ bindDialog.countdown > 0 ? `${bindDialog.countdown}s 后重发` : '发送验证码' }}
              </el-button>
            </div>
          </el-form-item>
          <p v-if="bindDialog.error" class="bind-error">{{ bindDialog.error }}</p>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="bindDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="confirmBindAction" :loading="bindDialog.confirming">确认绑定</el-button>
      </template>
    </el-dialog>

    <!-- ══ 修改密码弹窗 ══ -->
    <el-dialog
      v-model="showPwdDialog"
      title="修改密码"
      width="420px"
      :close-on-click-modal="false"
      @closed="resetPwdForm"
    >
      <el-form
        ref="pwdFormRef"
        :model="pwdForm"
        :rules="pwdRules"
        label-width="90px"
        @submit.prevent
      >
        <el-form-item label="原密码" prop="oldPwd">
          <el-input
            v-model="pwdForm.oldPwd"
            type="password"
            placeholder="请输入当前密码"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPwd">
          <el-input
            v-model="pwdForm.newPwd"
            type="password"
            placeholder="6 ~ 64 位"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPwd">
          <el-input
            v-model="pwdForm.confirmPwd"
            type="password"
            placeholder="再次输入新密码"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <p v-if="pwdError" class="pwd-error">{{ pwdError }}</p>
      </el-form>
      <template #footer>
        <el-button @click="showPwdDialog = false">取消</el-button>
        <el-button type="primary" :loading="pwdSubmitting" @click="submitPwdChange">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- Toast -->
    <transition name="toast-fade">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.message }}</div>
    </transition>

  </div>
</template>

<script setup>
import { reactive, ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDepthStore } from '@/stores/depth'
import { uploadAvatar, fetchAuditLogs, sendBindCode, confirmBind, changePassword } from '@/api'

const auth = useAuthStore()
const depthStore = useDepthStore()
const router = useRouter()

const fallbackAvatar = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTI4IiBoZWlnaHQ9IjEyOCIgdmlld0JveD0iMCAwIDEyOCAxMjgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjEyOCIgaGVpZ2h0PSIxMjgiIGZpbGw9IiMxMzFlMmIiLz48Y2lyY2xlIGN4PSI2NCIgY3k9IjQ4IiByPSIyMCIgZmlsbD0iIzAwZDRmZiIvPjxyZWN0IHg9IjI0IiB5PSI3NiIgd2lkdGg9IjgwIiBoZWlnaHQ9IjI4IiByeD0iMTQiIGZpbGw9IiMwMGQ0ZmYiIG9wYWNpdHk9Ii4zNSIvPjwvc3ZnPg=='
const previewAvatar = ref('')
const toast = reactive({ show: false, type: 'ok', message: '' })
let toastTimer = null

const activeTab = ref('activity')
const tabs = [
  { key: 'activity', icon: '◎', label: '最近动态' },
  { key: 'history',  icon: '◈', label: '转换历史' },
]

const auditLogs = ref([])
const auditLoading = ref(false)
const histLoading = ref(false)

async function goToWorkspace(rec) {
  depthStore.restoreFromRecord(rec)
  await router.push('/workspace')
}

// ── 签名即时编辑 ────────────────────────────────────────────────
const editingSig = ref(false)
const sigDraft = ref('')
const sigInputRef = ref(null)

function startEditSig() {
  sigDraft.value = auth.user?.signature || ''
  editingSig.value = true
  nextTick(() => sigInputRef.value?.focus())
}
function cancelSig() { editingSig.value = false }
async function saveSig() {
  if (!editingSig.value) return
  editingSig.value = false
  const sig = sigDraft.value.trim()
  if (sig === (auth.user?.signature || '')) return
  const ok = await auth.saveProfile({ signature: sig })
  showToast(ok ? '签名已更新' : (auth.error || '保存失败'), ok ? 'ok' : 'err')
}

// ── 昵称内联编辑 ────────────────────────────────────────────────
const editField = reactive({ nickname: false })
const fieldDraft = ref('')

function startEdit(field) { fieldDraft.value = auth.user?.[field] || ''; editField[field] = true }
function cancelEdit(field) { editField[field] = false }
async function confirmEdit(field) {
  editField[field] = false
  const ok = await auth.saveProfile({ [field]: fieldDraft.value.trim() })
  showToast(ok ? '保存成功' : (auth.error || '保存失败'), ok ? 'ok' : 'err')
}

// ── 头像 ────────────────────────────────────────────────────────
async function onAvatarPick(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { previewAvatar.value = reader.result }
  reader.readAsDataURL(file)
  try {
    const { data } = await uploadAvatar(file)
    auth.user.avatar_url = data.avatar_url
    previewAvatar.value = data.avatar_url
    showToast('头像已更新', 'ok')
  } catch (err) {
    showToast(err?.response?.data?.error || '头像上传失败', 'err')
  }
}

// ── 绑定弹窗 ────────────────────────────────────────────────────
const bindDialog = reactive({
  visible: false, type: 'email', target: '', code: '',
  sending: false, confirming: false, countdown: 0, error: '',
})
let countdownTimer = null

function openBind(type) {
  Object.assign(bindDialog, { type, target: '', code: '', error: '', countdown: 0, visible: true })
}
async function sendCode() {
  if (!bindDialog.target) {
    bindDialog.error = `请先输入${bindDialog.type === 'email' ? '邮箱' : '手机号'}`
    return
  }
  bindDialog.sending = true
  bindDialog.error = ''
  try {
    await sendBindCode(bindDialog.type, bindDialog.target)
    showToast('验证码已发送', 'ok')
    bindDialog.countdown = 60
    clearInterval(countdownTimer)
    countdownTimer = setInterval(() => {
      bindDialog.countdown -= 1
      if (bindDialog.countdown <= 0) clearInterval(countdownTimer)
    }, 1000)
  } catch (err) {
    bindDialog.error = err?.response?.data?.error || '发送失败，请稍后重试'
  } finally {
    bindDialog.sending = false
  }
}
async function confirmBindAction() {
  if (!bindDialog.code) { bindDialog.error = '请输入验证码'; return }
  bindDialog.confirming = true
  bindDialog.error = ''
  try {
    const { data } = await confirmBind(bindDialog.type, bindDialog.target, bindDialog.code)
    auth.user = data.user
    bindDialog.visible = false
    showToast('绑定成功', 'ok')
  } catch (err) {
    bindDialog.error = err?.response?.data?.error || '绑定失败，请重试'
  } finally {
    bindDialog.confirming = false
  }
}

// ── 初始化 ──────────────────────────────────────────────────────
onMounted(async () => {
  await auth.refreshProfile()
  auditLoading.value = true
  histLoading.value = true
  try {
    const [auditRes] = await Promise.all([
      fetchAuditLogs(20),
      depthStore.loadHistory(20),
    ])
    auditLogs.value = auditRes.data.logs || []
  } finally {
    auditLoading.value = false
    histLoading.value = false
  }
})

onUnmounted(() => {
  if (toastTimer) clearTimeout(toastTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})

function showToast(message, type = 'ok') {
  if (toastTimer) clearTimeout(toastTimer)
  Object.assign(toast, { show: true, type, message })
  toastTimer = setTimeout(() => { toast.show = false }, 3000)
}
function logout() { auth.logout(); router.push('/auth/login') }

// ── 修改密码 ────────────────────────────────────────────────────
const showPwdDialog  = ref(false)
const pwdSubmitting  = ref(false)
const pwdError       = ref('')
const pwdFormRef     = ref(null)
const pwdForm = reactive({ oldPwd: '', newPwd: '', confirmPwd: '' })

const pwdRules = {
  oldPwd: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
  ],
  newPwd: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度须为 6 ~ 64 位', trigger: 'blur' },
  ],
  confirmPwd: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== pwdForm.newPwd) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

function resetPwdForm() {
  pwdForm.oldPwd = ''
  pwdForm.newPwd = ''
  pwdForm.confirmPwd = ''
  pwdError.value = ''
  pwdFormRef.value?.clearValidate()
}

async function submitPwdChange() {
  pwdError.value = ''
  try {
    await pwdFormRef.value.validate()
  } catch {
    return  // 表单校验未通过，不提交
  }
  pwdSubmitting.value = true
  try {
    await changePassword({ old_password: pwdForm.oldPwd, new_password: pwdForm.newPwd })
    showPwdDialog.value = false
    // 密码修改成功：清除 Token，提示重新登录（安全要求）
    showToast('密码已更新，请重新登录', 'ok')
    setTimeout(() => {
      auth.logout()
      router.push('/auth/login')
    }, 1800)
  } catch (e) {
    pwdError.value = e?.response?.data?.error || '修改失败，请稍后重试'
  } finally {
    pwdSubmitting.value = false
  }
}

const ACTION_LABELS = { upload_image: '上传图像', update_avatar: '更换头像', save_depth: '保存深度图' }
function actionLabel(action) { return ACTION_LABELS[action] || action }
function fmtTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
/* ══ 双栏网格布局 ══ */
.profile-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
  align-items: start;
}

/* ══ 左栏 ══ */
.left-col {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 28px 22px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 80px;
}

/* 头像块 */
.avatar-block { display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; }
.avatar-wrap { position: relative; }
.avatar { width: 86px; height: 86px; border-radius: 50%; object-fit: cover; border: 2px solid var(--accent); display: block; }
.avatar-btn {
  position: absolute; bottom: 0; right: 0;
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent); color: #000;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; border: 2px solid var(--bg-card);
  transition: transform 0.18s;
}
.avatar-btn:hover { transform: scale(1.12); }
.user-name { font-size: 1.18rem; font-weight: 800; color: var(--text-pri); margin: 0; }
.user-handle { font-size: 0.78rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; margin: 0; }
.hero-badges { display: flex; gap: 6px; justify-content: center; }
.badge {
  font-size: 0.64rem; font-family: 'JetBrains Mono', monospace;
  font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  padding: 2px 9px; border-radius: 999px; border: 1px solid;
}
.badge.level  { color: var(--accent);   border-color: rgba(0,212,255,0.3);  background: rgba(0,212,255,0.08); }
.badge.admin  { color: #ffc84a;         border-color: rgba(255,200,0,0.35); background: rgba(255,200,0,0.08); }
.badge.user   { color: var(--text-sec); border-color: var(--border); background: transparent; }

/* 签名 */
.sig-wrap { width: 100%; min-height: 24px; display: flex; align-items: center; justify-content: center; gap: 6px; }
.sig-text { font-size: 0.8rem; color: var(--text-sec); cursor: pointer; border-bottom: 1px dashed var(--border); transition: color 0.15s; text-align: center; }
.sig-text:hover { color: var(--accent); }
.sig-input { font-size: 0.8rem; background: var(--bg-raised); border: 1px solid var(--accent); border-radius: 6px; color: var(--text-pri); padding: 3px 8px; width: 100%; outline: none; }
.sig-counter { font-size: 0.62rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; white-space: nowrap; }

/* 字段列表 */
.field-list { display: flex; flex-direction: column; border-top: 1px solid var(--border); }
.field-row { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.field-row:last-child { border-bottom: none; }
.field-label { font-size: 0.74rem; color: var(--text-dim); width: 50px; flex-shrink: 0; }
.field-val { font-size: 0.84rem; color: var(--text-pri); flex: 1; }
.field-val.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }
.field-val.dim { color: var(--text-dim); }
.field-input { flex: 1; min-width: 80px; font-size: 0.84rem; background: var(--bg-raised); border: 1px solid var(--accent); border-radius: 6px; color: var(--text-pri); padding: 3px 8px; outline: none; }
.field-btn { font-size: 0.7rem; padding: 2px 9px; border-radius: 6px; border: 1px solid var(--border); background: transparent; color: var(--text-sec); cursor: pointer; transition: all 0.15s; white-space: nowrap; }
.field-btn:hover { border-color: var(--accent); color: var(--accent); }
.field-btn.primary { color: var(--accent); border-color: rgba(0,212,255,0.35); }

.logout-btn { width: 100%; padding: 9px; border-radius: 10px; border: 1px solid var(--border); background: transparent; color: var(--text-sec); font-size: 0.86rem; cursor: pointer; transition: all 0.18s; }
.logout-btn:hover { border-color: rgba(255,107,107,0.5); color: #ffb3b3; }

.change-pwd-btn { width: 100%; padding: 9px; border-radius: 10px; border: 1px solid var(--border); background: transparent; color: var(--text-sec); font-size: 0.86rem; cursor: pointer; transition: all 0.18s; }
.change-pwd-btn:hover { border-color: rgba(0,212,255,0.4); color: var(--accent); }

.pwd-error { color: #ffb3b3; font-size: 0.84rem; margin: 4px 0 0; padding-left: 90px; }

/* ══ 右栏 ══ */
.right-col {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

/* Tab 导航 */
.tab-bar { display: flex; border-bottom: 1px solid var(--border); background: color-mix(in srgb, var(--bg-raised) 60%, transparent); }
.tab-btn {
  display: flex; align-items: center; gap: 7px;
  padding: 14px 24px;
  border: none; background: none;
  color: var(--text-sec); font-family: 'Syne', sans-serif;
  font-weight: 600; font-size: 0.9rem; cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.18s, border-color 0.18s;
}
.tab-btn:hover { color: var(--text-pri); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-icon { font-size: 0.9rem; }
.tab-count { font-size: 0.6rem; font-family: 'JetBrains Mono', monospace; background: rgba(0,212,255,0.14); color: var(--accent); padding: 1px 6px; border-radius: 999px; }

/* Tab 面板（可滚动） */
.tab-pane { padding: 20px 24px; flex: 1; overflow-y: auto; max-height: calc(100vh - 200px); }
.pane-loading { display: flex; justify-content: center; padding: 48px; }
.pane-empty { color: var(--text-dim); font-size: 0.9rem; text-align: center; padding: 48px 0; }

/* 审计列表 */
.audit-list { list-style: none; }
.audit-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.audit-item:last-child { border-bottom: none; }
.audit-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-top: 5px; flex-shrink: 0; }
.audit-body { display: flex; flex-direction: column; gap: 3px; }
.audit-action { font-size: 0.9rem; font-weight: 600; color: var(--text-pri); }
.audit-meta { font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }

/* 历史网格 */
.hist-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(156px, 1fr)); gap: 14px; }
.hist-card { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; cursor: pointer; background: var(--bg-raised); transition: border-color 0.18s, transform 0.18s, box-shadow 0.18s; }
.hist-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,212,255,0.12); }
.hist-thumb-wrap { position: relative; width: 100%; aspect-ratio: 3/2; overflow: hidden; display: grid; grid-template-columns: 1fr 1fr; }
.hist-thumb, .hist-depth { width: 100%; height: 100%; object-fit: cover; display: block; }
.hist-hint { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.52); color: var(--accent); font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; font-weight: 700; opacity: 0; transition: opacity 0.18s; }
.hist-card:hover .hist-hint { opacity: 1; }
.hist-info { padding: 8px 10px; display: flex; flex-direction: column; gap: 3px; }
.hist-model { font-size: 0.76rem; font-weight: 600; color: var(--text-pri); font-family: 'Syne', sans-serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hist-sub  { font-size: 0.6rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
.hist-time { font-size: 0.58rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }

/* 绑定弹窗 */
.bind-form { padding: 4px 0; }
.code-row { display: flex; gap: 10px; }
.bind-error { color: var(--accent3); font-size: 0.85rem; margin-top: 6px; }

/* Toast */
.toast { position: fixed; top: 82px; left: 50%; transform: translateX(-50%); z-index: 9999; min-width: 240px; max-width: 360px; padding: 10px 14px; border-radius: 10px; font-size: 0.9rem; box-shadow: 0 8px 24px rgba(0,0,0,0.35); border: 1px solid transparent; }
.toast.ok  { color: #7df1c7; background: rgba(20,52,44,0.95);  border-color: rgba(125,241,199,0.45); }
.toast.err { color: #ffb3b3; background: rgba(67,28,28,0.95);  border-color: rgba(255,107,107,0.55); }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(-8px); }

/* 响应式：小屏单列 */
@media (max-width: 800px) {
  .profile-page { grid-template-columns: 1fr; }
  .left-col { position: static; }
  .tab-pane { max-height: none; }
}
</style>