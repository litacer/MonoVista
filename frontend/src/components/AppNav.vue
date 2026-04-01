<template>
  <nav class="nav">
    <div class="nav-inner">
      <RouterLink to="/" class="logo">
        <span class="logo-mark">◆</span>
        MonoVista
      </RouterLink>
      <div class="nav-links">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink v-if="auth.isLoggedIn" to="/workspace">工作台</RouterLink>
        <RouterLink v-if="auth.isLoggedIn" to="/profile">个人中心</RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin/dashboard">管理端</RouterLink>
        <RouterLink v-if="!auth.isLoggedIn" to="/auth/login">登录</RouterLink>
        <RouterLink v-if="!auth.isLoggedIn" to="/auth/register">注册</RouterLink>
        <a v-if="auth.isLoggedIn" href="#" @click.prevent="logout">退出</a>
        <ThemeToggle />
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/auth/login')
}
</script>

<style scoped>
.nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  height: 64px;
  background: var(--nav-bg);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
}
.nav-inner {
  max-width: 1280px;
  margin: 0 auto;
  height: 100%;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-pri);
  letter-spacing: -0.5px;
}
.logo-mark { color: var(--accent); font-size: 1rem; }
.nav-links { display: flex; gap: 24px; align-items: center; }
.nav-links a {
  color: var(--text-sec);
  font-weight: 600;
  font-size: 0.95rem;
  transition: color 0.2s;
}
.nav-links a:hover,
.nav-links a.router-link-active { color: var(--accent); }
</style>
