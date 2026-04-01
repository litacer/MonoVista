<template>
  <div class="admin-page">

    <!-- ══ 图表行 ══ -->
    <el-row :gutter="14" style="margin-bottom:14px">
      <el-col :xs="24" :lg="12">
        <el-card><div ref="lineRef" class="chart"></div></el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card><div ref="pieRef" class="chart"></div></el-card>
      </el-col>
    </el-row>

    <!-- ══ 实时系统动态 ══ -->
    <el-card class="feed-card">
      <template #header>
        <div class="feed-header">
          <span class="feed-title">
            <span class="feed-dot"></span>实时系统动态
          </span>
          <span class="feed-hint">每 20 秒自动刷新</span>
        </div>
      </template>

      <!-- 无数据时展示 el-empty -->
      <el-empty v-if="!feed.length && !feedLoading" description="暂无操作记录" :image-size="80" />

      <!-- 首次加载骨架屏 -->
      <div v-else-if="feedLoading && !feed.length" class="feed-skeleton">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 时间轴流水线 -->
      <div v-else class="feed-scroll">
        <el-timeline>
          <el-timeline-item
            v-for="item in feed"
            :key="item.id"
            :color="actionColor(item.action)"
            :timestamp="item.created_at"
            placement="top"
          >
            <div class="feed-item">
              <span class="feed-user">{{ item.username }}</span>
              <el-tag
                size="small"
                :type="moduleTagType(item.module)"
                class="feed-module"
              >{{ item.module }}</el-tag>
              <span class="feed-action">{{ actionLabel(item.action) }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-card>

  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { fetchAdminDashboard, fetchAdminActivityFeed } from '@/api'

// ── 图表 ────────────────────────────────────────────────────────
const lineRef = ref(null)
const pieRef  = ref(null)

onMounted(async () => {
  const { data } = await fetchAdminDashboard()
  await nextTick()

  const line = echarts.init(lineRef.value)
  line.setOption({
    title: { text: '近七日转换趋势', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.seven_day.map(i => i.date.slice(5)) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, areaStyle: {}, data: data.seven_day.map(i => i.count) }],
  })

  const pie = echarts.init(pieRef.value)
  pie.setOption({
    title: { text: '模型使用占比', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item' },
    series: [{ type: 'pie', radius: ['46%', '70%'], data: data.model_dist || [] }],
  })

  // 首次加载流水线
  loadFeed()
  // 每 20 秒轮询一次
  pollTimer = setInterval(loadFeed, 20000)
})

// ── 实时操作流水线 ────────────────────────────────────────────────
const feed        = ref([])    // 当前展示的日志列表
const feedLoading = ref(false) // 首次加载标志
let   pollTimer   = null       // 轮询定时器句柄

/**
 * loadFeed — 拉取最新 15 条操作日志并平滑替换列表。
 * 首次加载（feed 为空）时显示骨架屏；
 * 后续轮询直接替换 feed.value，Element Plus timeline 响应式更新，无抖动。
 */
async function loadFeed() {
  if (!feed.value.length) feedLoading.value = true
  try {
    const { data } = await fetchAdminActivityFeed()
    feed.value = data.feed || []
  } catch (e) {
    console.warn('[activity-feed] poll failed', e)
  } finally {
    feedLoading.value = false
  }
}

onUnmounted(() => {
  // 组件卸载时清除定时器，防止内存泄漏和后台无效请求
  if (pollTimer) clearInterval(pollTimer)
})

// ── 视觉映射 ────────────────────────────────────────────────────

/**
 * actionColor — 根据操作类型返回时间轴节点颜色
 *   login/register → 蓝色（认证类）
 *   delete/remove  → 红色（危险类）
 *   update/edit    → 橙色（修改类）
 *   upload/convert → 绿色（转换类）
 *   其他           → 灰色
 */
function actionColor(action) {
  const a = (action || '').toLowerCase()
  if (a.includes('login') || a.includes('register')) return '#409eff'
  if (a.includes('delete') || a.includes('remove'))  return '#f56c6c'
  if (a.includes('update') || a.includes('edit') || a.includes('profile')) return '#e6a23c'
  if (a.includes('upload') || a.includes('convert') || a.includes('depth')) return '#67c23a'
  return '#909399'
}

/** moduleTagType — el-tag type 按模块映射 */
function moduleTagType(module) {
  const map = { '认证': '', '用户': 'info', '转换': 'success', '模型': 'warning', '公告': 'info', '系统': 'info' }
  return map[module] || 'info'
}

/** actionLabel — 操作描述友好化 */
const LABELS = {
  upload_image:  '上传图像',
  update_avatar: '更换头像',
  save_depth:    '保存深度图',
  login:         '登录',
  register:      '注册',
  logout:        '退出登录',
}
function actionLabel(action) { return LABELS[action] || action }
</script>

<style scoped>
.chart { height: 360px; }

/* ══ 流水线卡片 ══ */
.feed-card { margin-top: 0; }

.feed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.feed-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text-pri);
}
/* 实时呼吸点 */
.feed-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #67c23a;
  animation: pulse 2s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse {
  0%, 100% { opacity: 1;   transform: scale(1);   }
  50%       { opacity: 0.4; transform: scale(0.7); }
}
.feed-hint {
  font-size: 0.72rem;
  color: var(--text-dim, #999);
  font-family: 'JetBrains Mono', monospace;
}

/* 固定高度可滚动区域 */
.feed-scroll {
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

/* 美化 Webkit 滚动条 */
.feed-scroll::-webkit-scrollbar       { width: 4px; }
.feed-scroll::-webkit-scrollbar-track { background: transparent; }
.feed-scroll::-webkit-scrollbar-thumb {
  background: rgba(0, 212, 255, 0.25);
  border-radius: 4px;
}
.feed-scroll::-webkit-scrollbar-thumb:hover { background: rgba(0, 212, 255, 0.5); }

/* 每条日志行 */
.feed-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.feed-user   { font-weight: 600; font-size: 0.88rem; color: var(--text-pri); }
.feed-module { flex-shrink: 0; }
.feed-action { font-size: 0.84rem; color: var(--text-sec); }
.feed-skeleton { padding: 12px 0; }
</style>
