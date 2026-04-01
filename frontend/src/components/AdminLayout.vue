<template>
  <div class="admin-shell">
    <el-container class="root">
      <el-aside class="aside" :width="collapsed ? '72px' : '228px'">
        <div class="brand" @click="go('/admin/dashboard')">
          <span class="mark">◆</span>
          <span v-if="!collapsed">MonoVista Admin</span>
        </div>

        <el-menu :default-active="activeMenu" :collapse="collapsed" class="menu" router>
          <el-menu-item index="/admin/dashboard">首页</el-menu-item>
          <el-menu-item index="/admin/conversions">转换管理</el-menu-item>
          <el-menu-item index="/admin/audit">用户审计</el-menu-item>
          <el-menu-item index="/admin/model-registry">模型实验室</el-menu-item>
          <el-menu-item index="/admin/announcements">公告管理</el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-button text @click="collapsed = !collapsed">☰</el-button>
            <el-breadcrumb separator=">">
              <el-breadcrumb-item>管理端</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <ThemeToggle />
            <el-tag effect="dark" type="primary">{{ auth.user?.username }}</el-tag>
            <el-button size="small" type="danger" plain @click="logout">退出</el-button>
          </div>
        </el-header>

        <div class="tabs-wrap">
          <el-tabs v-model="activeTab" type="card" closable @tab-remove="removeTab" @tab-click="goTab">
            <el-tab-pane v-for="tab in tabs" :key="tab.path" :label="tab.title" :name="tab.path" :closable="tab.path !== '/admin/dashboard'" />
          </el-tabs>
        </div>

        <el-main class="main">
          <router-view v-slot="{ Component, route }">
            <keep-alive :include="cachedNames">
              <component :is="Component" :key="route.path" />
            </keep-alive>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapsed = ref(false)
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title || '首页')

const tabs = ref([{ path: '/admin/dashboard', title: '首页', name: 'AdminDashboard' }])
const activeTab = ref('/admin/dashboard')

const cachedNames = computed(() => tabs.value.map(i => i.name))

watch(() => route.path, () => {
  activeTab.value = route.path
  if (!route.meta?.title) return
  if (!String(route.path).startsWith('/admin')) return
  const exist = tabs.value.find(t => t.path === route.path)
  if (!exist) {
    tabs.value.push({
      path: route.path,
      title: route.meta.title,
      name: route.name,
    })
  }
}, { immediate: true })

function go(path) {
  router.push(path)
}

function goTab(tab) {
  go(tab.paneName)
}

function removeTab(path) {
  const idx = tabs.value.findIndex(t => t.path === path)
  if (idx < 0) return
  tabs.value.splice(idx, 1)
  if (activeTab.value === path) {
    const fallback = tabs.value[idx - 1] || tabs.value[idx] || tabs.value[0]
    go(fallback?.path || '/admin/dashboard')
  }
}

function logout() {
  auth.logout()
  router.push('/auth/login')
}
</script>

<style scoped>
.admin-shell { min-height: 100vh; background: var(--bg-deep); }
.root { min-height: 100vh; }
.aside {
  border-right: 1px solid var(--border);
  background: var(--bg-card);
  transition: width .2s ease;
}
.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  font-weight: 700;
  border-bottom: 1px solid var(--border);
  color: var(--text-pri);
  cursor: pointer;
}
.mark { color: var(--accent); }
.menu {
  border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--text-sec);
  --el-menu-active-color: var(--accent);
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 10px; }
.tabs-wrap {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 0 10px;
}
.main { background: var(--bg-deep); }
:deep(.el-tabs__item) { color: var(--text-sec); }
:deep(.el-tabs__item.is-active) { color: var(--accent); }

/* Admin 端 Element Plus 主题变量：跟随全局 dark/light 切换 */
.admin-shell :deep(.el-card),
.admin-shell :deep(.el-table),
.admin-shell :deep(.el-input__wrapper),
.admin-shell :deep(.el-select__wrapper),
.admin-shell :deep(.el-dialog) {
  --el-bg-color: var(--bg-card);
  --el-fill-color-blank: var(--bg-card);
  --el-border-color: var(--border);
  --el-text-color-primary: var(--text-pri);
  --el-text-color-regular: var(--text-sec);
}

.admin-shell :deep(.el-table tr),
.admin-shell :deep(.el-table th.el-table__cell),
.admin-shell :deep(.el-table td.el-table__cell) {
  background: var(--bg-card);
  color: var(--text-pri);
}

/* 浅色模式下增强层级对比，保证后台界面可读性 */
:global(html.light-mode) .admin-shell {
  background: #edf2fb;
}
:global(html.light-mode) .aside,
:global(html.light-mode) .header,
:global(html.light-mode) .tabs-wrap {
  background: #ffffff;
}
:global(html.light-mode) .main {
  background: #f3f6fc;
}
:global(html.light-mode) .admin-shell :deep(.el-tabs__item.is-active) {
  color: #0b7fcf;
}
</style>
