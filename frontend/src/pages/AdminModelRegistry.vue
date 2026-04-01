<template>
  <div class="lab-page">
    <el-card class="runtime-card">
      <template #header>
        <div class="runtime-head">配置中心</div>
      </template>

      <div class="runtime-grid">
        <div class="field">
          <label>推理精度</label>
          <el-select v-model="runtimeForm.precision" style="width: 160px">
            <el-option label="FP32" value="fp32" />
            <el-option label="FP16" value="fp16" />
          </el-select>
        </div>
        <div class="field">
          <label>推理设备</label>
          <el-select v-model="runtimeForm.device" style="width: 180px">
            <el-option label="CPU" value="cpu" />
            <el-option label="GPU/CUDA" value="cuda" />
          </el-select>
        </div>
        <el-button type="primary" @click="saveRuntime" :loading="savingRuntime">保存配置</el-button>
      </div>

      <div class="runtime-status">
        当前激活：<b>{{ runtime.active_model_key || '-' }}</b>
        ｜设备：<b>{{ runtime.device || '-' }}</b>
        ｜精度：<b>{{ (runtime.precision || '-').toUpperCase() }}</b>
        <span v-if="runtime.loading" class="loading">（加载中）</span>
      </div>
    </el-card>

    <div class="model-grid">
      <el-card v-for="m in models" :key="m.model_key" class="model-card" shadow="hover">
        <div class="top-row">
          <div>
            <h3>{{ m.display_name || m.name }}</h3>
            <p class="sub">{{ m.framework }} · {{ m.version }} · {{ m.model_key }}</p>
          </div>
          <el-tag :type="m.status === 'Active' ? 'success' : 'info'" effect="plain">
            {{ m.status }}
          </el-tag>
        </div>

        <div class="meta">权重：{{ m.oss_weight_path }}</div>

        <div class="editor-grid">
          <div class="editor-item">
            <label>显示名称</label>
            <el-input v-model="m.display_name" placeholder="用户端展示名称" @blur="saveMeta(m)" />
          </div>
          <div class="editor-item">
            <label>模型描述（用户端 Tooltip）</label>
            <el-input
              v-model="m.description"
              type="textarea"
              :rows="2"
              placeholder="例如：Monodepth2 适合复杂室外"
              @blur="saveMeta(m)"
            />
          </div>
          <div class="editor-switch">
            <span>用户端可见</span>
            <el-switch
              v-model="m.is_visible"
              inline-prompt
              active-text="开"
              inactive-text="关"
              @change="toggleVisible(m)"
            />
          </div>
        </div>

        <div class="metric-row">
          <div class="metric">
            <span>平均耗时</span>
            <b>{{ Number(m.infer_latency_ms || 0).toFixed(1) }} ms</b>
            <div :id="`lat-${m.id}`" class="mini-chart"></div>
          </div>
          <div class="metric">
            <span>显存占用</span>
            <b>{{ Number(m.vram_mb || 0).toFixed(0) }} MB</b>
            <div :id="`mem-${m.id}`" class="mini-chart"></div>
          </div>
        </div>

        <div class="actions">
          <el-button
            type="primary"
            plain
            :disabled="m.status === 'Active'"
            :loading="activatingKey === m.model_key"
            @click="activateModel(m.model_key)"
          >
            激活模型
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  fetchAdminModelRegistry,
  activateAdminModel,
  updateAdminRuntime,
  updateAdminModelVisibility,
  updateAdminModelMeta,
} from '@/api'

const models = ref([])
const runtime = ref({})
const activatingKey = ref('')
const savingRuntime = ref(false)
const runtimeForm = reactive({ precision: 'fp32', device: 'cpu' })
const savingMetaMap = ref({})

function tinyLine(domId, base) {
  const dom = document.getElementById(domId)
  if (!dom) return
  const chart = echarts.init(dom)
  const data = [0.95, 1.02, 1.0, 0.98, 1.03, 1.01, 1.0].map(v => Number((base * v).toFixed(2)))
  chart.setOption({
    grid: { left: 0, right: 0, top: 2, bottom: 0 },
    xAxis: { type: 'category', show: false, data: data.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    series: [{ type: 'line', smooth: true, symbol: 'none', data, areaStyle: { opacity: 0.12 } }],
    animation: false,
  })
}

function tinyBar(domId, base) {
  const dom = document.getElementById(domId)
  if (!dom) return
  const chart = echarts.init(dom)
  const data = [0.92, 1.0, 0.98, 1.05, 1.01].map(v => Number((base * v).toFixed(1)))
  chart.setOption({
    grid: { left: 0, right: 0, top: 2, bottom: 0 },
    xAxis: { type: 'category', show: false, data: data.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    series: [{ type: 'bar', barWidth: 6, data }],
    animation: false,
  })
}

async function drawMiniCharts() {
  await nextTick()
  for (const m of models.value) {
    tinyLine(`lat-${m.id}`, Number(m.infer_latency_ms || 0))
    tinyBar(`mem-${m.id}`, Number(m.vram_mb || 0))
  }
}

async function toggleVisible(model) {
  await updateAdminModelVisibility(model.id, Boolean(model.is_visible))
  ElMessage.success('可见性已更新')
}

async function saveMeta(model) {
  const key = String(model.id)
  if (savingMetaMap.value[key]) return
  savingMetaMap.value[key] = true
  try {
    await updateAdminModelMeta(model.id, {
      display_name: model.display_name,
      description: model.description,
    })
    ElMessage.success('模型文案已保存')
  } finally {
    savingMetaMap.value[key] = false
  }
}

async function loadData() {
  const { data } = await fetchAdminModelRegistry()
  models.value = data.models || []
  runtime.value = data.runtime || {}
  runtimeForm.precision = runtime.value.precision || 'fp32'
  runtimeForm.device = runtime.value.device || 'cpu'
  await drawMiniCharts()
}

async function activateModel(modelKey) {
  activatingKey.value = modelKey
  try {
    await activateAdminModel({
      model_key: modelKey,
      precision: runtimeForm.precision,
      device: runtimeForm.device,
    })
    ElMessage.success('模型已热切换')
    await loadData()
  } finally {
    activatingKey.value = ''
  }
}

async function saveRuntime() {
  savingRuntime.value = true
  try {
    const { data } = await updateAdminRuntime({
      precision: runtimeForm.precision,
      device: runtimeForm.device,
    })
    runtime.value = data.runtime || {}
    ElMessage.success('运行配置已更新')
  } finally {
    savingRuntime.value = false
  }
}

loadData()
</script>

<style scoped>
.lab-page { display: grid; gap: 14px; }
.runtime-card { border-radius: 14px; }
.runtime-head { font-weight: 700; letter-spacing: .02em; }
.runtime-grid { display: flex; flex-wrap: wrap; gap: 14px; align-items: end; }
.field { display: grid; gap: 6px; }
.field label { font-size: 12px; color: var(--text-sec); }
.runtime-status { margin-top: 10px; color: var(--text-sec); }
.runtime-status b { color: var(--text-pri); }
.loading { color: #d89b2f; }

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
.model-card { border-radius: 14px; }
.top-row { display: flex; justify-content: space-between; align-items: start; gap: 10px; }
.top-row h3 { margin: 0; font-size: 17px; font-weight: 700; color: var(--text-pri); }
.sub { margin: 4px 0 0; color: var(--text-sec); font-size: 12px; }
.meta {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-sec);
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--bg-raised) 76%, transparent);
  word-break: break-all;
}
.editor-grid { margin-top: 12px; display: grid; gap: 10px; }
.editor-item { display: grid; gap: 6px; }
.editor-item label, .editor-switch span { font-size: 12px; color: var(--text-sec); }
.editor-switch { display: flex; align-items: center; justify-content: space-between; border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; }
.metric-row { margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.metric {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px;
  background: color-mix(in srgb, var(--bg-card) 92%, transparent);
}
.metric span { display: block; font-size: 12px; color: var(--text-sec); }
.metric b { font-size: 15px; color: var(--text-pri); }
.mini-chart { height: 34px; margin-top: 4px; }
.actions { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
