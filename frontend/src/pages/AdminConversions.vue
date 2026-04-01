<template>
  <div class="admin-page">
    <el-card>
      <el-form :inline="true" class="toolbar">
        <el-form-item label="用户ID">
          <el-input v-model="filters.user_id" placeholder="用户ID" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="filters.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" border stripe class="admin-table">
        <el-table-column prop="id" label="ID" width="76" />
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column label="原图" width="118">
          <template #default="{ row }">
            <img :src="row.thumbnail_url" class="thumb" @click="preview(row.thumbnail_url)" />
          </template>
        </el-table-column>
        <el-table-column prop="model_label" label="模型" width="150" />
        <el-table-column label="参数 JSON" min-width="240">
          <template #default="{ row }">
            <el-button size="small" text @click="openConfig(row)">查看</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          @current-change="changePage"
        />
      </div>
    </el-card>

    <el-dialog v-model="showImage" title="图片预览" width="720px">
      <img :src="previewUrl" class="preview-img" />
    </el-dialog>

    <el-dialog v-model="showConfig" title="参数详情" width="520px">
      <pre class="json-box">{{ configText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { fetchAdminConversions } from '@/api'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({ user_id: '', range: [] })

const showImage = ref(false)
const previewUrl = ref('')
const showConfig = ref(false)
const configText = ref('')

function preview(url) {
  previewUrl.value = url
  showImage.value = true
}

function openConfig(row) {
  configText.value = JSON.stringify(row.render_config || {}, null, 2)
  showConfig.value = true
}

async function loadData() {
  const params = { page: page.value, page_size: pageSize.value }
  if (filters.user_id) params.user_id = Number(filters.user_id)
  if (filters.range?.length === 2) {
    params.start_at = filters.range[0]
    params.end_at = filters.range[1]
  }
  const { data } = await fetchAdminConversions(params)
  rows.value = data.records
  total.value = data.total
}

function search() {
  page.value = 1
  loadData()
}

function changePage(p) {
  page.value = p
  loadData()
}

loadData()
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.thumb { width: 88px; height: 56px; object-fit: cover; border-radius: 6px; cursor: pointer; border: 1px solid var(--border); }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
.preview-img { width: 100%; border-radius: 8px; }
.json-box { margin: 0; white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
</style>
