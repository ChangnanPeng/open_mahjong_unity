<template>
  <div class="platform-data">
    <p v-if="meta.as_of_date" class="as-of-tip">
      数据截止至 <strong>{{ meta.as_of_date }}</strong> 统计日（北京时间 04:00 切日，每日 04:00 更新）
    </p>

    <section class="section-card">
      <h3 class="section-title">天梯场次历史总计</h3>
      <div v-loading="loading">
        <el-tabs v-model="totalsTierTab" class="totals-tabs">
          <el-tab-pane
            v-for="t in TIER_OPTIONS"
            :key="t.value"
            :label="t.label"
            :name="t.value"
          >
            <div v-if="activeTierTotals" class="stats-grid">
              <div v-for="row in buildStatsRows(activeTierTotals)" :key="row.label" class="stats-cell">
                <span class="stats-label">{{ row.label }}</span>
                <span class="stats-value">{{ row.value }}</span>
              </div>
            </div>
            <p v-else class="empty-hint">暂无该场次累计数据</p>
            <el-collapse class="fan-collapse">
              <el-collapse-item :title="`番种出现次数（${fanDictSize}）`" name="fan">
                <div class="fan-grid">
                  <div
                    v-for="item in tierFanEntries"
                    :key="item.key"
                    class="fan-item"
                    :class="{ 'fan-item--zero': item.count === 0 }"
                  >
                    <span class="fan-name">{{ item.label }}</span>
                    <span class="fan-count">{{ item.count }}</span>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>
        </el-tabs>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h3 class="section-title">天梯场次每日对局数</h3>
        <div class="filter-row">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            size="small"
            value-format="YYYY-MM-DD"
            class="filter-daterange"
            @change="loadStats"
          />
          <el-button size="small" @click="setQuickRange(7)">近7天</el-button>
          <el-button size="small" @click="setQuickRange(30)">近30天</el-button>
          <el-button size="small" @click="setQuickRange(90)">近90天</el-button>
        </div>
      </div>
      <div v-loading="loading" class="chart-wrap">
        <div ref="sceneChartRef" class="chart-box"></div>
      </div>
      <el-table :data="dailyTable" size="small" empty-text="暂无数据" max-height="360" class="detail-table">
        <el-table-column label="日期" prop="stat_date" width="120" />
        <el-table-column
          v-for="t in TIER_OPTIONS"
          :key="t.value"
          :label="t.label"
          :prop="t.value"
          width="100"
        />
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'
import { GUOBIAO_FAN_DICT } from '@/constants/guobiaoFanDict'
import {
  buildStatsRows,
  buildAllFanEntries,
  buildSceneDailyChartOption,
  buildSceneDailyTable,
} from '@/utils/statsDisplay'

const TIER_OPTIONS = [
  { value: 'beginner', label: '初级场' },
  { value: 'intermediate', label: '中级场' },
  { value: 'advanced', label: '高级场' },
  { value: 'mcrpl', label: 'mcrpl' },
]
const TIER_LABEL = Object.fromEntries(TIER_OPTIONS.map((t) => [t.value, t.label]))
const fanDictSize = Object.keys(GUOBIAO_FAN_DICT).length

const formatLocalDate = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const makeRange = (days, endDateStr) => {
  const to = endDateStr ? new Date(`${endDateStr}T12:00:00`) : new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - (days - 1))
  return [formatLocalDate(from), formatLocalDate(to)]
}

const loading = ref(false)
const meta = ref({})
const sceneTotals = ref([])
const sceneTierFans = ref({})
const sceneDaily = ref([])
const totalsTierTab = ref('beginner')
const dateRange = ref(makeRange(30))

const sceneChartRef = ref(null)
let sceneChart = null

const activeTierTotals = computed(() =>
  sceneTotals.value.find((r) => r.match_tier === totalsTierTab.value) || null
)

const tierFanEntries = computed(() =>
  buildAllFanEntries(sceneTierFans.value[totalsTierTab.value], GUOBIAO_FAN_DICT)
)

const dailyTable = computed(() =>
  buildSceneDailyTable(sceneDaily.value, TIER_OPTIONS, TIER_LABEL)
)

const renderSceneChart = () => {
  if (!sceneChartRef.value) return
  const opt = buildSceneDailyChartOption(sceneDaily.value, {
    tierOptions: TIER_OPTIONS,
    tierLabel: TIER_LABEL,
  })
  if (!sceneChart) sceneChart = echarts.init(sceneChartRef.value)
  sceneChart.setOption(opt, true)
}

const handleResize = () => sceneChart?.resize()

const setQuickRange = (days) => {
  dateRange.value = makeRange(days, meta.value.as_of_date)
  loadStats()
}

const loadStats = async () => {
  loading.value = true
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    } else {
      params.days = 30
    }
    const res = await axios.get('/api/platform/stats', { params })
    const payload = res.data?.data || {}
    sceneTotals.value = payload.totals || []
    sceneTierFans.value = payload.fans || {}
    sceneDaily.value = payload.daily || []
    meta.value = res.data?.meta || {}
    if (meta.value.as_of_date && dateRange.value?.[1] > meta.value.as_of_date) {
      dateRange.value = makeRange(30, meta.value.as_of_date)
    }
    await nextTick()
    renderSceneChart()
  } catch (e) {
    ElMessage.error('获取平台数据失败')
    sceneTotals.value = []
    sceneTierFans.value = {}
    sceneDaily.value = []
  } finally {
    loading.value = false
  }
}

watch(sceneDaily, () => nextTick(() => renderSceneChart()))

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  sceneChart?.dispose()
})
</script>

<style scoped>
.platform-data { color: #1f2329; }
.as-of-tip {
  margin: 0 0 14px;
  font-size: 13px;
  color: #606266;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.section-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.filter-daterange { width: 240px; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px 16px;
  margin-bottom: 12px;
}
.stats-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  background: #f4f5f7;
  border-radius: 6px;
}
.stats-label { font-size: 12px; color: #909399; }
.stats-value { font-size: 15px; font-weight: 600; }
.empty-hint { font-size: 13px; color: #909399; margin: 8px 0; }
.fan-collapse { margin-top: 8px; }
.fan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 6px 12px;
}
.fan-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 4px 0;
  border-bottom: 1px dashed #ebeef5;
}
.fan-item--zero .fan-name,
.fan-item--zero .fan-count { color: #c0c4cc; }
.fan-name { color: #606266; }
.fan-count { font-weight: 600; color: #409eff; }
.chart-wrap { margin-bottom: 12px; }
.chart-box { width: 100%; height: 320px; min-width: 0; }
.detail-table { margin-top: 8px; }
</style>
