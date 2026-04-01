<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2>{{ title }}</h2>
      <p class="subtitle">{{ subtitle }}</p>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          用户名
          <input v-model.trim="form.username" required minlength="3" placeholder="请输入用户名" />
        </label>

        <label v-if="mode !== 'login'">
          邮箱
          <input v-model.trim="form.email" type="email" :required="mode === 'register' || mode === 'forgot'" placeholder="name@example.com" />
        </label>

        <label>
          {{ mode === 'forgot' ? '新密码' : '密码' }}
          <input v-model="form.password" type="password" required minlength="6" placeholder="至少 6 位" />
        </label>

        <!-- 验证码区域（仅登录模式显示） -->
        <div v-if="mode === 'login'" class="captcha-row">
          <label class="captcha-label">
            验证码
            <input
              v-model.trim="form.captchaCode"
              placeholder="请输入图中字符"
              maxlength="4"
              autocomplete="off"
              class="captcha-input"
            />
          </label>
          <!--
            点击图片调用 auth.loadCaptcha() 无感刷新验证码。
            auth.captchaImage 是后端返回的 Base64 data URI，
            直接作为 img src 使用，无需额外请求。
          -->
          <img
            v-if="auth.captchaImage"
            :src="auth.captchaImage"
            class="captcha-img"
            title="点击刷新验证码"
            @click="auth.loadCaptcha()"
            alt="验证码"
          />
          <div v-else class="captcha-placeholder" @click="auth.loadCaptcha()">
            点击获取验证码
          </div>
        </div>

        <button class="btn btn-primary" :disabled="auth.loading" type="submit">
          {{ auth.loading ? '处理中...' : submitText }}
        </button>

        <p v-if="auth.error" class="error">{{ auth.error }}</p>
      </form>

      <div class="links">
        <RouterLink to="/auth/login">登录</RouterLink>
        <RouterLink to="/auth/register">注册</RouterLink>
        <RouterLink to="/auth/forgot">找回密码</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()

const mode = computed(() => route.meta.authMode || 'login')

const form = reactive({ username: '', email: '', password: '', captchaCode: '' })

const title      = computed(() => ({ login: '账号登录', register: '创建账号', forgot: '找回密码' }[mode.value]))
const subtitle   = computed(() => ({ login: '登录后可访问核心转换功能', register: '注册后自动登录', forgot: '通过用户名 + 邮箱重置密码' }[mode.value]))
const submitText = computed(() => ({ login: '登录', register: '注册', forgot: '重置密码' }[mode.value]))

// 进入登录页时自动加载验证码
onMounted(() => {
  if (mode.value === 'login') auth.loadCaptcha()
})

// 切换到登录模式时也加载验证码（路由复用同一组件时触发）
watch(mode, (val) => {
  if (val === 'login') {
    form.captchaCode = ''
    auth.loadCaptcha()
  }
})

async function onSubmit() {
  if (mode.value === 'login') {
    const ok = await auth.login({
      username:     form.username,
      password:     form.password,
      // 将 UUID 和用户输入一起提交给后端
      // 后端从 Redis 检索 UUID 对应的文本进行比对，
      // 验证通过后立即删除 Key 防止重放攻击
      captcha_uuid: auth.captchaUuid,
      captcha_code: form.captchaCode,
    })
    if (ok) router.push(auth.isAdmin ? '/admin/dashboard' : '/workspace')
    return
  }
  if (mode.value === 'register') {
    const ok = await auth.register({ username: form.username, password: form.password, email: form.email })
    if (ok) router.push('/workspace')
    return
  }
  const ok = await auth.resetPassword({
    username:     form.username,
    email:        form.email,
    new_password: form.password,
  })
  if (ok) router.push('/auth/login')
}
</script>

<style scoped>
.auth-page { min-height: calc(100vh - 64px); display: grid; place-items: center; padding: 24px; }
.auth-card { width: 100%; max-width: 460px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; }
.auth-card h2 { margin-bottom: 6px; }
.subtitle { color: var(--text-dim); margin-bottom: 18px; font-size: 0.9rem; }
.form { display: grid; gap: 12px; }
label { display: grid; gap: 6px; color: var(--text-sec); font-size: 0.9rem; }
input {
  background: var(--bg-deep); border: 1px solid var(--border); color: var(--text-pri);
  border-radius: 10px; padding: 10px 12px; outline: none;
}
input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(0,212,255,0.12); }
.error { color: var(--accent3); font-size: 0.85rem; }
.links { display: flex; justify-content: space-between; margin-top: 16px; font-size: 0.9rem; }

/* ── 验证码区域 ── */
.captcha-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.captcha-label {
  flex: 1;
  display: grid;
  gap: 6px;
  color: var(--text-sec);
  font-size: 0.9rem;
}
.captcha-input {
  background: var(--bg-deep);
  border: 1px solid var(--border);
  color: var(--text-pri);
  border-radius: 10px;
  padding: 10px 12px;
  outline: none;
  letter-spacing: 0.2em;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
}
.captcha-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(0,212,255,0.12); }

/* 验证码图片：点击即刷新，鼠标悬停有提示 */
.captcha-img {
  height: 44px;
  width: 120px;
  border-radius: 8px;
  border: 1px solid var(--border);
  cursor: pointer;
  object-fit: cover;
  transition: opacity 0.15s ease, border-color 0.15s ease;
  flex-shrink: 0;
}
.captcha-img:hover {
  opacity: 0.82;
  border-color: var(--accent);
}

/* 验证码未加载时的占位块 */
.captcha-placeholder {
  height: 44px;
  width: 120px;
  border-radius: 8px;
  border: 1px dashed var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  color: var(--text-dim);
  cursor: pointer;
  flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace;
  transition: border-color 0.15s;
}
.captcha-placeholder:hover { border-color: var(--accent); color: var(--accent); }
</style>
