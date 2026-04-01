<template>
  <div class="home">

    <!--
      ══ 系统公告滚动栏 ══
      渲染流程：
        1. onMounted → GET /api/announcements → 返回 is_active=True 列表
        2. 多条公告：scrollList 复制一份构成无缝循环，CSS marquee 动画驱动
        3. 点击标题 → openAnnouncement(rec) → el-dialog 用 v-html 渲染 HTML
        4. HTML 已由后端 bleach 过滤 XSS，.rich-content CSS 保证排版样式正确
    -->
    <div v-if="announcements.length" class="ann-bar">
      <span class="ann-badge">公告</span>
      <div class="ann-track-wrap">
        <div
          class="ann-track"
          :class="{ marquee: announcements.length > 1 }"
          :style="announcements.length > 1 ? `--duration: ${scrollDuration}s` : ''"
        >
          <span
            v-for="rec in scrollList"
            :key="rec.id + '_' + rec._copy"
            class="ann-item"
            :class="rec.type"
            @click="openAnnouncement(rec)"
          >{{ rec.title }}</span>
        </div>
      </div>
    </div>

    <!-- 公告详情弹窗 -->
    <el-dialog v-model="annDialog.visible" :title="annDialog.title" width="620px">
      <!--
        v-html 直接渲染后端返回的 HTML 字符串。
        安全保证：内容已在写入时经 _sanitize_html()（bleach 白名单）过滤。
        .rich-content 作用域 CSS 确保 strong/ul/blockquote 等标签样式正确显示。
      -->
      <div class="rich-content" v-html="annDialog.content"></div>
      <template #footer>
        <el-button @click="annDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content fade-up">
        <span class="tag">毕业设计 · 深度估计 · 立体视觉</span>
        <h1>Mono<span class="accent">Vista</span></h1>
        <p class="hero-sub">
          基于单目深度估计的图像动态立体转换工具<br/>
          上传一张普通照片，即可生成深度图与3D立体视差图像
        </p>
        <div class="hero-actions">
          <RouterLink to="/workspace" class="btn btn-primary">开始使用 →</RouterLink>
        </div>
      </div>
    </section>

    <section class="features">
      <div class="features-grid">
        <div class="feature-card" v-for="f in features" :key="f.title">
          <div class="feature-icon">{{ f.icon }}</div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <section class="pipeline">
      <h2>处理流水线</h2>
      <div class="steps">
        <div class="step" v-for="(s, i) in steps" :key="i">
          <div class="step-num">{{ i + 1 }}</div>
          <div class="step-info">
            <h4>{{ s.title }}</h4>
            <p>{{ s.desc }}</p>
          </div>
          <div v-if="i < steps.length - 1" class="step-arrow">→</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { fetchAnnouncements } from '@/api'

// ── 公告数据 ────────────────────────────────────────────────────
const announcements = ref([])

/**
 * scrollList：多条公告时复制一份追加到尾部，
 * 配合 CSS translateX(-50%) 实现视觉上的无缝循环滚动。
 */
const scrollList = computed(() => {
  if (announcements.value.length <= 1) return announcements.value
  return [
    ...announcements.value.map(r => ({ ...r, _copy: 0 })),
    ...announcements.value.map(r => ({ ...r, _copy: 1 })),
  ]
})

/** scrollDuration：每条公告约 4 秒，最短 8 秒 */
const scrollDuration = computed(() => Math.max(8, announcements.value.length * 4))

onMounted(async () => {
  try {
    const { data } = await fetchAnnouncements()
    announcements.value = data.announcements || []
  } catch (e) {
    console.warn('[announcements] fetch failed', e)
  }
})

// ── 弹窗状态 ────────────────────────────────────────────────────
const annDialog = reactive({ visible: false, title: '', content: '' })

function openAnnouncement(rec) {
  annDialog.title   = rec.title
  annDialog.content = rec.content
  annDialog.visible = true
}

// ── 静态数据 ────────────────────────────────────────────────────
const features = [
  { icon: '🔍', title: '单目深度估计', desc: '基于 Depth Anything V2 / MiDaS / Monodepth2，从单张 RGB 图像精准预测像素级深度，无需双目相机。' },
  { icon: '🎬', title: 'DIBR 视角合成', desc: '深度图像渲染技术，利用深度图和相机位移参数，实时合成任意水平视角的虚拟图像。' },
  { icon: '🥽', title: '多种立体格式', desc: '支持红青 Anaglyph、左右并排 SBS 及多视角动画序列输出，满足不同展示需求。' },
  { icon: '⚡', title: '实时交互', desc: '拖动滑块即时生成新视角，浏览器内流畅预览，多模型自由切换。' },
]
const steps = [
  { title: '选择模型', desc: 'DA V2 / MiDaS / Mono2' },
  { title: '上传图像', desc: 'JPG / PNG / WebP' },
  { title: '深度估计', desc: '像素级深度预测' },
  { title: 'DIBR 合成', desc: '多视角渲染' },
  { title: '立体输出', desc: 'Anaglyph / SBS' },
]
</script>

<style scoped>
.home { overflow: hidden; }

/* ══ 公告滚动栏 ══ */
.ann-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 24px;
  height: 38px;
  background: rgba(0, 212, 255, 0.05);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  overflow: hidden;
}
.ann-badge {
  flex-shrink: 0;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  font-family: 'JetBrains Mono', monospace;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.28);
  padding: 2px 8px;
  border-radius: 4px;
}
.ann-track-wrap {
  flex: 1;
  overflow: hidden;
}
/* 静态单条 */
.ann-track { display: flex; gap: 56px; white-space: nowrap; }

/*
  多条公告无缝循环滚动原理：
    - scrollList 将原列表复制一份追加（共 2N 条）
    - translateX(-50%) 恰好滚完第一份（N 条），CSS 动画结束时立即跳回 0
    - 由于视觉上内容完全相同，跳回瞬间无感知，形成无缝循环
    - --duration 变量由 Vue 动态注入，按公告数量缩放速度
*/
.ann-track.marquee {
  animation: marquee var(--duration, 16s) linear infinite;
}
.ann-track.marquee:hover {
  animation-play-state: paused;  /* 悬停暂停，方便阅读 */
}
@keyframes marquee {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}

.ann-item {
  font-size: 0.84rem;
  color: var(--text-sec);
  cursor: pointer;
  transition: color 0.15s;
  padding: 0 6px;
  border-radius: 3px;
}
.ann-item:hover { color: var(--accent); text-decoration: underline; }
.ann-item.warning { color: #e6a817; }
.ann-item.success { color: #4caf50; }
.hero {
  position: relative; min-height: 88vh;
  display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 80px 32px;
}
.hero-bg {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 50% 30%, rgba(0,212,255,0.08) 0%, transparent 70%),
    radial-gradient(ellipse 50% 40% at 80% 70%, rgba(123,94,167,0.08) 0%, transparent 60%);
  pointer-events: none;
}
.hero-content { position: relative; z-index: 1; max-width: 760px; }
.hero-content .tag { margin-bottom: 24px; display: inline-block; }
h1 { font-size: clamp(3.5rem, 8vw, 7rem); font-weight: 800; line-height: 1; letter-spacing: -3px; color: var(--text-pri); margin-bottom: 24px; }
.accent { color: var(--accent); }
.hero-sub { font-size: 1.15rem; color: var(--text-sec); line-height: 1.8; margin-bottom: 40px; }
.hero-actions { display: flex; gap: 16px; justify-content: center; }
.hero-actions .btn { font-size: 1.05rem; padding: 14px 32px; }
.features { padding: 80px 32px; max-width: 1200px; margin: 0 auto; }
.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; }
.feature-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; transition: border-color 0.2s, box-shadow 0.2s; }
.feature-card:hover { border-color: var(--accent); box-shadow: var(--glow); }
.feature-icon { font-size: 2rem; margin-bottom: 16px; }
.feature-card h3 { font-size: 1.05rem; font-weight: 700; margin-bottom: 10px; }
.feature-card p { font-size: 0.88rem; color: var(--text-sec); line-height: 1.7; }
.pipeline { padding: 60px 32px 100px; max-width: 1200px; margin: 0 auto; }
.pipeline h2 { font-size: 1.5rem; font-weight: 800; margin-bottom: 36px; text-align: center; }
.steps { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 8px; }
.step { display: flex; align-items: center; gap: 8px; }
.step-num { width: 36px; height: 36px; border-radius: 50%; background: rgba(0,212,255,0.12); border: 1px solid rgba(0,212,255,0.3); color: var(--accent); font-weight: 700; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step-info { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 16px; }
.step-info h4 { font-size: 0.9rem; font-weight: 700; margin-bottom: 2px; }
.step-info p { font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
.step-arrow { color: var(--text-dim); font-size: 1.2rem; }

/*
  富文本弹窗样式（.rich-content）
  因为 v-html 渲染的 HTML 标签不会被 scoped 属性选中，
  所以使用 :deep() 穿透 scoped，确保 strong/ul/ol/blockquote 等标签有正确样式。
*/
:deep(.rich-content) {
  line-height: 1.8;
  color: var(--text-pri);
  font-size: 0.95rem;
  word-break: break-word;
}
:deep(.rich-content) p     { margin-bottom: 10px; }
:deep(.rich-content) strong,
:deep(.rich-content) b     { font-weight: 700; }
:deep(.rich-content) em,
:deep(.rich-content) i     { font-style: italic; }
:deep(.rich-content) u     { text-decoration: underline; }
:deep(.rich-content) h1,:deep(.rich-content) h2,:deep(.rich-content) h3 { font-weight: 700; margin: 14px 0 8px; }
:deep(.rich-content) ul,
:deep(.rich-content) ol    { padding-left: 22px; margin-bottom: 10px; }
:deep(.rich-content) li    { margin-bottom: 4px; }
:deep(.rich-content) blockquote {
  border-left: 3px solid var(--accent);
  padding: 6px 14px;
  color: var(--text-sec);
  background: rgba(0,212,255,0.04);
  margin: 10px 0;
  border-radius: 0 6px 6px 0;
}
:deep(.rich-content) a     { color: var(--accent); text-decoration: underline; }
:deep(.rich-content) pre,
:deep(.rich-content) code  { font-family: 'JetBrains Mono', monospace; background: var(--bg-raised); padding: 2px 6px; border-radius: 4px; font-size: 0.88em; }
</style>
