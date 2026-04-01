<template>
  <div class="ann-page">

    <!-- ══ 顶部操作栏 ══ -->
    <div class="ann-toolbar">
      <h2 class="ann-title">公告管理</h2>
      <el-button type="primary" @click="openCreate">+ 发布公告</el-button>
    </div>

    <!-- ══ 公告列表 ══ -->
    <el-table :data="list" v-loading="loading" border stripe class="ann-table">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="tagType(row.type)" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            @change="toggle(row)"
            active-text="激活"
            inactive-text="禁用"
          />
        </template>
      </el-table-column>
      <el-table-column prop="create_time" label="创建时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- ══ 发布/编辑弹窗 ══ -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑公告' : '发布公告'"
      width="780px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="ann-form">
        <el-form :model="form" label-width="70px">
          <el-form-item label="标题">
            <el-input v-model="form.title" placeholder="公告标题，最多 200 字" maxlength="200" show-word-limit />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.type">
              <el-option label="普通 info" value="info" />
              <el-option label="警告 warning" value="warning" />
              <el-option label="成功 success" value="success" />
            </el-select>
          </el-form-item>
          <el-form-item label="激活">
            <el-switch v-model="form.is_active" active-text="立即激活" inactive-text="草稿" />
          </el-form-item>
          <el-form-item label="内容">
            <!--
              WangEditor 富文本编辑器。

              存储流程说明：
                1. 用户在编辑器中排版（粗体、颜色、对齐、链接等）
                2. 编辑器输出标准 HTML 字符串（如 <p><strong>...</strong></p>）
                3. 点击保存时，前端将此 HTML 字符串 POST/PUT 到后端
                4. 后端 _sanitize_html() 用 bleach 白名单过滤 XSS 后存入 MySQL LONGTEXT 字段

              渲染流程说明：
                1. 用户端通过 GET /api/announcements 拿到已过滤的 HTML 字符串
                2. el-dialog 内用 v-html 指令直接渲染 HTML
                3. 外层加了 .rich-content 作用域 CSS，确保 <strong>/<ul>/<blockquote> 等样式正常显示
            -->
            <div class="editor-wrap">
              <Toolbar
                :editor="editorRef"
                :defaultConfig="toolbarConfig"
                mode="default"
                class="editor-toolbar"
              />
              <Editor
                v-model="form.content"
                :defaultConfig="editorConfig"
                mode="default"
                class="editor-body"
                @onCreated="handleEditorCreated"
              />
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ dialog.isEdit ? '保存修改' : '发布公告' }}
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, shallowRef, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'
import {
  fetchAdminAnnouncements,
  createAdminAnnouncement,
  updateAdminAnnouncement,
  toggleAdminAnnouncement,
  deleteAdminAnnouncement,
} from '@/api'

// ── 列表 ────────────────────────────────────────────────────────
const list = ref([])
const loading = ref(false)

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchAdminAnnouncements()
    list.value = data.announcements || []
  } catch (e) {
    ElMessage.error('加载失败：' + (e?.response?.data?.error || e.message))
  } finally {
    loading.value = false
  }
}
loadList()

// ── WangEditor 实例 ──────────────────────────────────────────────
// 使用 shallowRef 避免 Vue 深度代理 editor 对象导致报错
const editorRef = shallowRef(null)

function handleEditorCreated(editor) {
  editorRef.value = editor
}

onBeforeUnmount(() => {
  // 组件销毁时必须手动销毁 editor，防止内存泄漏
  editorRef.value?.destroy()
})

// WangEditor 工具栏配置：只保留基础排版功能
const toolbarConfig = {
  toolbarKeys: [
    'bold', 'italic', 'underline', 'color', 'bgColor',
    '|', 'justifyLeft', 'justifyCenter', 'justifyRight',
    '|', 'bulletedList', 'numberedList', 'blockquote',
    '|', 'insertLink', 'clearStyle',
  ],
}

const editorConfig = {
  placeholder: '请输入公告正文内容（支持富文本排版）…',
  MENU_CONF: {},
}

// ── 表单状态 ────────────────────────────────────────────────────
const dialog = ref({ visible: false, isEdit: false, editId: null })
const saving = ref(false)
const form = ref({ title: '', content: '', type: 'info', is_active: true })

function openCreate() {
  form.value = { title: '', content: '', type: 'info', is_active: true }
  dialog.value = { visible: true, isEdit: false, editId: null }
}

function openEdit(row) {
  form.value = { title: row.title, content: row.content, type: row.type, is_active: row.is_active }
  dialog.value = { visible: true, isEdit: true, editId: row.id }
}

async function submit() {
  if (!form.value.title.trim()) { ElMessage.warning('请填写标题'); return }
  if (!form.value.content.trim()) { ElMessage.warning('请填写正文内容'); return }
  saving.value = true
  try {
    if (dialog.value.isEdit) {
      await updateAdminAnnouncement(dialog.value.editId, form.value)
      ElMessage.success('公告已更新')
    } else {
      await createAdminAnnouncement(form.value)
      ElMessage.success('公告已发布')
    }
    dialog.value.visible = false
    loadList()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  try {
    await toggleAdminAnnouncement(row.id)
    row.is_active = !row.is_active
    ElMessage.success(row.is_active ? '已激活' : '已禁用')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除公告「${row.title}」？`, '确认删除', { type: 'warning' })
    await deleteAdminAnnouncement(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ── 工具函数 ────────────────────────────────────────────────────
function tagType(type) {
  return { info: '', warning: 'warning', success: 'success' }[type] || ''
}
function fmtTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.ann-page { padding: 24px; }
.ann-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.ann-title { font-size: 1.2rem; font-weight: 700; color: var(--text-pri); margin: 0; }
.ann-table { width: 100%; }

/* WangEditor 容器 */
.ann-form { padding: 4px 0; }
.editor-wrap {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-raised, #fff);
}
.editor-toolbar {
  border-bottom: 1px solid var(--border);
  background: var(--bg-card, #f5f5f5);
}
.editor-body {
  height: 280px;
  overflow-y: auto;
  color: var(--text-pri, #222);
  background: var(--bg-raised, #fff);
}
</style>
