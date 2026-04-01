<template>
  <div class="admin-page">
    <el-card>
      <el-form :inline="true" class="toolbar">
        <el-form-item label="IP">
          <el-input v-model="filters.ip" placeholder="按 IP 过滤" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="操作类型">
          <el-input v-model="filters.action" placeholder="例如 upload/delete/login" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" border stripe class="admin-table">
        <el-table-column prop="id" label="ID" width="74" />
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="action" label="操作" width="150" />
        <el-table-column prop="object_type" label="对象类型" width="120" />
        <el-table-column prop="object_id" label="对象ID" min-width="150" />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column prop="browser" label="浏览器" min-width="160" />
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
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { fetchAdminAuditLogs } from '@/api'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)

const filters = reactive({ ip: '', action: '' })

async function loadData() {
  const { data } = await fetchAdminAuditLogs({
    page: page.value,
    page_size: pageSize.value,
    ip: filters.ip || undefined,
    action: filters.action || undefined,
  })
  rows.value = data.logs
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
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
