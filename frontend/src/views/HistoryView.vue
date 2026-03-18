<template>
  <div class="history">
    <h2 class="page-title">历史记录</h2>

    <div class="page-card">
      <el-radio-group v-model="activeTab" @change="loadHistory">
        <el-radio-button label="single">单题练习</el-radio-button>
        <el-radio-button label="paper">套卷练习</el-radio-button>
      </el-radio-group>
    </div>

    <div class="page-card">
      <h3>分数趋势</h3>
      <div ref="chartRef" class="trend-chart"></div>
    </div>

    <div class="page-card">
      <div class="history-header">
        <h3>练习记录</h3>
        <el-button
          v-if="selectedIds.length > 0"
          type="primary"
          @click="analyzeSelected"
          :loading="analyzing"
        >
          AI 综合分析 ({{ selectedIds.length }})
        </el-button>
      </div>

      <el-skeleton v-if="loading" :rows="5" animated />

      <template v-else>
        <el-empty v-if="isHistoryEmpty" description="暂无练习记录" />

        <div v-else class="history-list">
          <template v-if="activeTab === 'single'">
            <div v-for="(records, date) in singleHistoryData" :key="date" class="date-group">
              <div class="date-header">{{ date }}</div>
              <div class="records">
                <div v-for="record in records" :key="record.id" class="record-item">
                  <el-checkbox
                    :model-value="selectedIds.includes(String(record.id))"
                    @change="toggleSelect(record.id)"
                  />
                  <div class="record-content" @click="viewSingleRecord(record)">
                    <div class="record-question">{{ truncate(record.question_content, 60) }}</div>
                    <div class="record-meta">
                      <span>用时: {{ formatDuration(record.duration_seconds) }}</span>
                    </div>
                  </div>
                  <div class="record-score" :class="getScoreClass(record.analysis?.score)">
                    {{ record.analysis?.score ?? '-' }}
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template v-else>
            <div v-for="(records, date) in paperHistoryData" :key="date" class="date-group">
              <div class="date-header">{{ date }}</div>
              <div class="records">
                <div v-for="record in records" :key="record.paper_session_id" class="record-item">
                  <el-checkbox
                    :model-value="selectedIds.includes(record.paper_session_id)"
                    @change="toggleSelect(record.paper_session_id)"
                  />
                  <div class="record-content" @click="viewPaperRecord(record)">
                    <div class="record-question">{{ record.paper_title }}</div>
                    <div class="record-meta">
                      <span>{{ record.question_count }} 道题</span>
                      <span>总用时: {{ formatDuration(record.total_duration_seconds) }}</span>
                      <span v-if="record.time_limit_seconds">限时: {{ formatDuration(record.time_limit_seconds) }}</span>
                    </div>
                    <div class="paper-preview">{{ formatPaperPreview(record) }}</div>
                  </div>
                  <div class="record-score" :class="getScoreClass(record.analysis_score)">
                    {{ record.analysis_score ?? '-' }}
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </template>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadHistory"
        style="margin-top: 20px; justify-content: center"
      />
    </div>

    <el-dialog
      v-model="showDetailDialog"
      :title="activeTab === 'single' ? '练习详情' : '套题详情'"
      width="90%"
      style="max-width: 800px"
    >
      <template v-if="activeTab === 'single' && selectedSingleRecord">
        <div class="detail-section">
          <h4>题目</h4>
          <p>{{ selectedSingleRecord.question_content }}</p>
        </div>
        <div class="detail-section">
          <h4>我的作答</h4>
          <p>{{ selectedSingleRecord.transcript }}</p>
        </div>
        <div class="detail-section">
          <h4>用时</h4>
          <p>{{ formatDuration(selectedSingleRecord.duration_seconds) }}</p>
        </div>
        <div v-if="selectedSingleRecord.analysis" class="detail-section">
          <h4>AI 分析 (得分: {{ selectedSingleRecord.analysis.score }})</h4>
          <div
            class="analysis-content markdown-content"
            v-html="formatMarkdown(selectedSingleRecord.analysis.feedback || '')"
          ></div>
        </div>
      </template>

      <template v-else-if="activeTab === 'paper' && selectedPaperRecord">
        <div class="detail-section">
          <h4>套题信息</h4>
          <p>{{ selectedPaperRecord.paper_title }}</p>
        </div>
        <div class="detail-section">
          <h4>练习概况</h4>
          <p>
            {{ selectedPaperRecord.question_count }} 道题 |
            总用时 {{ formatDuration(selectedPaperRecord.total_duration_seconds) }}
            <span v-if="selectedPaperRecord.time_limit_seconds">
              | 限时 {{ formatDuration(selectedPaperRecord.time_limit_seconds) }}
            </span>
          </p>
        </div>
        <div
          v-for="(answer, index) in selectedPaperRecord.answers"
          :key="answer.id"
          class="detail-section"
        >
          <h4>第 {{ index + 1 }} 题</h4>
          <p class="detail-question">{{ answer.question_content }}</p>
          <p>{{ answer.transcript || '未作答' }}</p>
          <p class="detail-answer-meta">用时: {{ formatDuration(answer.duration_seconds) }}</p>
        </div>
        <div v-if="selectedPaperRecord.analysis_feedback" class="detail-section">
          <h4>
            AI 整套分析
            <span v-if="selectedPaperRecord.analysis_score !== undefined">
              (得分: {{ selectedPaperRecord.analysis_score }})
            </span>
          </h4>
          <div
            class="analysis-content markdown-content"
            v-html="formatMarkdown(selectedPaperRecord.analysis_feedback)"
          ></div>
        </div>
        <div v-else class="detail-section">
          <h4>AI 整套分析</h4>
          <p>该套题暂无整体 AI 分析。</p>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showAnalysisDialog" title="AI 综合分析" width="90%" style="max-width: 800px">
      <el-skeleton v-if="analyzing" :rows="10" animated />
      <div v-else class="analysis-content markdown-content" v-html="formatMarkdown(analysisResult)"></div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { historyApi, answerApi, type AnswerWithAnalysis, type PaperSessionHistoryRecord } from '@/api/answers'

const activeTab = ref<'single' | 'paper'>('single')
const loading = ref(false)
const analyzing = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const singleHistoryData = ref<Record<string, AnswerWithAnalysis[]>>({})
const paperHistoryData = ref<Record<string, PaperSessionHistoryRecord[]>>({})
const selectedIds = ref<string[]>([])
const selectedSingleRecord = ref<AnswerWithAnalysis | null>(null)
const selectedPaperRecord = ref<PaperSessionHistoryRecord | null>(null)
const showDetailDialog = ref(false)
const showAnalysisDialog = ref(false)
const analysisResult = ref('')
const chartRef = ref<HTMLElement | null>(null)

let chartInstance: echarts.ECharts | null = null

const isHistoryEmpty = computed(() => {
  const source = activeTab.value === 'single' ? singleHistoryData.value : paperHistoryData.value
  return Object.keys(source).length === 0
})

function truncate(text: string | undefined, length: number): string {
  if (!text) return ''
  return text.length > length ? text.slice(0, length) + '...' : text
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return '0秒'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins > 0) {
    return `${mins}分${secs}秒`
  }
  return `${secs}秒`
}

function getScoreClass(score: number | undefined): string {
  if (score === undefined) return ''
  if (score >= 80) return 'good'
  if (score >= 60) return 'medium'
  return 'poor'
}

function formatMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  return escaped
    .replace(/###\s*(.*)/g, '<h4>$1</h4>')
    .replace(/##\s*(.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^-\s+(.*)/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
}

function formatPaperPreview(record: PaperSessionHistoryRecord): string {
  return record.answers
    .slice(0, 2)
    .map((answer, index) => `第 ${index + 1} 题：${truncate(answer.question_content, 24)}`)
    .join(' | ')
}

async function loadHistory() {
  loading.value = true
  selectedIds.value = []
  selectedSingleRecord.value = null
  selectedPaperRecord.value = null

  try {
    if (activeTab.value === 'single') {
      const data = await historyApi.getSingle({ page: currentPage.value, page_size: pageSize.value })
      singleHistoryData.value = data.items
      paperHistoryData.value = {}
      total.value = data.total
    } else {
      const data = await historyApi.getPaper({ page: currentPage.value, page_size: pageSize.value })
      paperHistoryData.value = data.items
      singleHistoryData.value = {}
      total.value = data.total
    }

    await loadTrends()
  } catch (e) {
    console.error('加载历史失败', e)
  } finally {
    loading.value = false
  }
}

async function loadTrends() {
  try {
    const data = await historyApi.getTrends(activeTab.value, 30)
    updateChart(data.trends)
  } catch (e) {
    console.error('加载趋势失败', e)
  }
}

function updateChart(trends: Array<{ date: string; avg_score: number; count: number }>) {
  if (!chartRef.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: trends.map(t => t.date.slice(5))
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100
    },
    series: [{
      type: 'line',
      data: trends.map(t => t.avg_score),
      smooth: true,
      lineStyle: { color: '#409eff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      }
    }],
    grid: { left: 40, right: 20, top: 20, bottom: 30 }
  }

  chartInstance.setOption(option)
}

function toggleSelect(id: number | string) {
  const key = String(id)
  const index = selectedIds.value.indexOf(key)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(key)
  }
}

function viewSingleRecord(record: AnswerWithAnalysis) {
  selectedSingleRecord.value = record
  showDetailDialog.value = true
}

function viewPaperRecord(record: PaperSessionHistoryRecord) {
  selectedPaperRecord.value = record
  showDetailDialog.value = true
}

async function analyzeSelected() {
  if (selectedIds.value.length === 0) return

  analyzing.value = true
  showAnalysisDialog.value = true

  try {
    if (activeTab.value === 'single') {
      const result = await answerApi.historyAnalyze(
        selectedIds.value.map(id => Number(id)),
        'history_single_analyze'
      )
      analysisResult.value = result.feedback
    } else {
      const result = await answerApi.historyAnalyzePaper(
        selectedIds.value,
        'history_paper_analyze'
      )
      analysisResult.value = result.feedback
    }
  } catch (e) {
    analysisResult.value = '分析失败，请稍后重试'
  } finally {
    analyzing.value = false
  }
}

const handleResize = () => chartInstance?.resize()

onMounted(() => {
  loadHistory()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.history {
  max-width: 900px;
  margin: 0 auto;
}

.trend-chart {
  height: 200px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.history-header h3 {
  margin: 0;
}

.date-group {
  margin-bottom: 20px;
}

.date-header {
  font-size: 14px;
  color: #909399;
  margin-bottom: 10px;
  padding-left: 5px;
}

.records {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.record-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.record-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.record-content {
  flex: 1;
  cursor: pointer;
}

.record-question {
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 6px;
}

.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: #909399;
}

.paper-preview {
  margin-top: 8px;
  font-size: 13px;
  color: #606266;
}

.record-score {
  min-width: 56px;
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  color: #909399;
}

.record-score.good {
  color: #67c23a;
}

.record-score.medium {
  color: #e6a23c;
}

.record-score.poor {
  color: #f56c6c;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  margin: 0 0 10px;
}

.detail-section p {
  margin: 0;
  line-height: 1.8;
  white-space: pre-wrap;
}

.detail-question {
  font-weight: 500;
  margin-bottom: 8px;
}

.detail-answer-meta {
  margin-top: 8px !important;
  color: #909399;
  font-size: 13px;
}

.analysis-content {
  padding: 18px;
  background: #f5f7fa;
  border-radius: 8px;
  line-height: 1.8;
}
</style>
