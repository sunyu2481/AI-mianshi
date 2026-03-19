<template>
  <div class="paper-practice">
    <h2 class="page-title">套卷练习</h2>

    <!-- 步骤1: 选择套卷 -->
    <div v-if="step === 'select'" v-loading="loadingPapers" class="page-card">
      <h3>选择练习套卷</h3>

      <el-input
        v-if="papers.length > 0 || paperSearchKeyword"
        v-model="paperSearchKeyword"
        class="paper-search"
        placeholder="搜索套题试卷，支持多词空格筛选"
        clearable
        @input="schedulePaperSearch"
        @clear="handlePaperSearch"
        @keyup.enter="handlePaperSearch"
      >
        <template #append>
          <el-button @click="handlePaperSearch">搜索</el-button>
        </template>
      </el-input>

      <!-- 从题库选择 -->
      <div class="paper-list" v-if="papers.length > 0">
        <div
          v-for="paper in papers"
          :key="paper.id"
          class="paper-item"
          @click="selectPaper(paper)"
        >
          <div class="paper-info">
            <span class="paper-title">{{ paper.title }}</span>
            <span class="paper-meta">{{ paper.items.length }} 道题 | 默认 {{ formatTime(paper.time_limit_seconds) }}</span>
          </div>
          <div class="paper-actions">
            <el-button text type="danger" size="small" @click.stop="deletePaper(paper)">
              删除
            </el-button>
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>

      <el-pagination
        v-if="totalPapers > 0"
        v-model:current-page="paperCurrentPage"
        class="paper-pagination"
        :page-size="paperPageSize"
        :total="totalPapers"
        layout="prev, pager, next"
        @current-change="loadPapers"
      />

      <el-empty
        v-else
        :description="paperSearchKeyword ? '未找到匹配的套题试卷' : '暂无套卷，请先在题库中创建'"
      />

      <!-- 自定义套卷 -->
      <el-divider>或</el-divider>

      <el-button @click="showCustomPaper = true">
        <el-icon><Plus /></el-icon>
        自定义套卷
      </el-button>

      <!-- 自定义套卷弹窗 -->
      <el-dialog v-model="showCustomPaper" title="自定义套卷" width="90%" style="max-width: 700px">
        <el-form label-position="top">
          <el-form-item label="套卷标题">
            <el-input v-model="customPaperTitle" placeholder="请输入套卷标题" />
          </el-form-item>
          <el-form-item label="总时限（分钟）">
            <el-input-number v-model="customTimeLimit" :min="5" :max="60" />
          </el-form-item>
          <el-form-item label="题目（每行一道）">
            <el-input
              v-model="customQuestions"
              type="textarea"
              :rows="8"
              placeholder="请输入题目，每行一道题..."
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showCustomPaper = false">取消</el-button>
          <el-button type="primary" @click="startCustomPaper" :disabled="!customQuestions.trim() || !customPaperTitle.trim()">
            开始练习
          </el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="showStartPracticeConfig" title="开始套卷练习" width="90%" style="max-width: 520px">
        <div class="start-config-summary">
          <div class="start-config-title">{{ pendingPaperTitle }}</div>
          <div class="start-config-meta">
            {{ pendingQuestions.length }} 道题 | 默认 {{ formatTime(pendingTimeLimitSeconds) }}
          </div>
        </div>
        <el-form label-position="top">
          <el-form-item label="本次练习时长（分钟）">
            <el-input-number v-model="practiceTimeLimitMinutes" :min="1" :max="180" />
          </el-form-item>
        </el-form>
        <div v-if="pendingQuestions.length > 0" class="start-config-questions">
          <div class="start-config-questions-title">本套题题目</div>
          <el-scrollbar max-height="240px">
            <div
              v-for="(question, index) in pendingQuestions"
              :key="question.id"
              class="start-config-question-item"
            >
              <span class="start-config-question-index">{{ index + 1 }}.</span>
              <span class="start-config-question-content">{{ question.content }}</span>
            </div>
          </el-scrollbar>
        </div>
        <template #footer>
          <el-button @click="showStartPracticeConfig = false">取消</el-button>
          <el-button type="primary" @click="confirmStartPractice">
            开始练习
          </el-button>
        </template>
      </el-dialog>
    </div>

    <!-- 步骤2: 练习中 -->
    <div v-if="step === 'practice'" class="page-card">
      <!-- 总计时 -->
      <div class="paper-timer">
        <span class="timer-label">剩余时间</span>
        <span
          class="timer-display"
          :class="{ warning: paperTimer.isWarning.value, danger: paperTimer.seconds.value <= 10 }"
        >
          {{ paperTimer.formatted.value }}
        </span>
        <div v-if="recorder.isTranscribing.value" class="timer-status">
          转写中，已暂停总倒计时
        </div>
      </div>

      <!-- 题目导航 -->
      <div class="question-nav">
        <div
          v-for="(q, index) in practiceStore.paperQuestions"
          :key="index"
          class="nav-item"
          :class="{
            active: practiceStore.currentQuestionIndex === index,
            answered: isQuestionAnswered(index),
            disabled: practiceStore.isRecording || recorder.isTranscribing.value
          }"
          @click="switchQuestion(index)"
        >
          {{ index + 1 }}
        </div>
      </div>

      <!-- 当前题目 -->
      <div class="question-section">
        <div class="question-header">
          <span class="question-number">第 {{ practiceStore.currentQuestionIndex + 1 }} 题</span>
          <el-tag v-if="getCurrentQuestion()?.category" type="info">
            {{ getCurrentQuestion()?.category }}
          </el-tag>
        </div>
        <div class="question-content">
          {{ getCurrentQuestion()?.content }}
        </div>
      </div>

      <!-- 单题计时 -->
      <div class="answer-timer">
        <span class="timer-label">本题用时</span>
        <span class="timer-display small" :class="{ recording: practiceStore.isRecording }">
          {{ questionTimer.formatted.value }}
        </span>
      </div>

      <!-- 录音控制 -->
      <div class="record-section">
        <button
          type="button"
          class="record-btn"
          :class="{ idle: !practiceStore.isRecording && !recorder.isTranscribing.value, recording: practiceStore.isRecording, transcribing: recorder.isTranscribing.value }"
          :aria-label="practiceStore.isRecording ? '结束录音' : '开始录音'"
          :aria-pressed="practiceStore.isRecording"
          :disabled="recorder.isTranscribing.value"
          @click="toggleRecording"
        >
          <el-icon :size="28">
            <Loading v-if="recorder.isTranscribing.value" class="spin-icon" />
            <Microphone v-else-if="!practiceStore.isRecording" />
            <VideoPause v-else />
          </el-icon>
        </button>
        <p class="record-hint">
          {{ recorder.isTranscribing.value ? '正在转写...' : (practiceStore.isRecording ? '点击结束本题' : '点击开始作答') }}
        </p>
      </div>

      <!-- 转写文本 -->
      <div class="transcript-section">
        <el-input
          v-model="currentTranscript"
          type="textarea"
          :rows="4"
          placeholder="作答内容..."
        />
        <!-- 转写错误提示与重试 -->
        <div v-if="recorder.error.value && !recorder.isTranscribing.value" class="transcribe-error">
          <span class="error-text">{{ recorder.error.value }}</span>
          <el-button
            v-if="recorder.lastAudioBlob.value"
            type="warning"
            size="small"
            :loading="recorder.isTranscribing.value"
            @click="handleRetryTranscribe"
          >
            重新转写
          </el-button>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <el-button :disabled="recorder.isTranscribing.value" @click="confirmEnd">面试结束</el-button>
      </div>
    </div>

    <!-- 步骤3: 分析结果 -->
    <div v-if="step === 'result'" class="page-card">
      <h3>套卷分析结果</h3>

      <!-- 流式输出中 -->
      <div v-if="isStreaming && streamContent" class="analysis-content markdown-content streaming">
        <div v-html="streamHtml"></div>
        <span class="cursor">▌</span>
      </div>

      <el-skeleton v-else-if="isAnalyzing" :rows="10" animated />

      <div v-else class="result-content">
        <!-- 各题得分概览 -->
        <div class="score-overview">
          <div
            v-for="(answer, index) in paperAnswers"
            :key="index"
            class="score-item"
          >
            <span class="score-label">第 {{ index + 1 }} 题</span>
            <span class="score-value">{{ answer.score ?? '-' }}</span>
          </div>
        </div>

        <!-- 详细分析 -->
        <div v-if="paperAnalysis" class="analysis-content markdown-content">
          <div v-html="safeAnalysisHtml"></div>
        </div>
      </div>

      <div class="result-actions">
        <el-button @click="handleRegeneratePaperAnalysis" :disabled="isAnalyzing || isStreaming">重新生成</el-button>
        <el-button @click="handleRetry" :disabled="isStreaming">再次练习</el-button>
        <el-button @click="reset" :disabled="isStreaming">换题练习</el-button>
        <el-button type="primary" @click="$router.push('/history')" :disabled="isStreaming">查看历史</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Plus, Microphone, VideoPause, Loading } from '@element-plus/icons-vue'
import { usePracticeStore } from '@/store/practice'
import { useAppStore } from '@/store/app'
import { useTimer } from '@/composables/useTimer'
import { useRecorder } from '@/composables/useRecorder'
import { paperApi, type Paper } from '@/api/papers'
import { questionApi, type Question } from '@/api/questions'
import { answerApi } from '@/api/answers'
import { v4 as uuidv4 } from 'uuid'

const route = useRoute()
const practiceStore = usePracticeStore()
const appStore = useAppStore()
const paperTimer = useTimer('countdown', 0)
const questionTimer = useTimer('countup')
const recorder = useRecorder()

interface PracticePaperAnswer {
  questionId: number
  transcript: string
  duration: number
  score?: number
  answerId?: number
}

const step = ref<'select' | 'practice' | 'result'>('select')
const papers = ref<Paper[]>([])
const paperSearchKeyword = ref('')
const loadingPapers = ref(false)
const paperCurrentPage = ref(1)
const paperPageSize = ref(12)
const totalPapers = ref(0)
const showCustomPaper = ref(false)
const showStartPracticeConfig = ref(false)
const customPaperTitle = ref('自定义练习套卷')
const customTimeLimit = ref(15)
const customQuestions = ref('')
const currentTranscript = ref('')
const isAnalyzing = ref(false)
const isStreaming = ref(false)
const streamContent = ref('')
const paperAnalysis = ref('')
const paperAnswers = ref<PracticePaperAnswer[]>([])
const pendingQuestions = ref<Question[]>([])
const pendingPaperId = ref<number>()
const pendingPaperTitle = ref('套卷练习')
const pendingTimeLimitSeconds = ref(900)
const practiceTimeLimitMinutes = ref(15)
const activePaperId = ref<number>()
const activePaperTitle = ref('套卷练习')
const practiceStartedAt = ref('')
const resumePaperTimerAfterTranscription = ref(false)
let paperSearchTimer: number | undefined

// 安全的 HTML 输出 (防 XSS)
const safeAnalysisHtml = computed(() => {
  const text = paperAnalysis.value || ''
  // 先转义 HTML 特殊字符
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  // 再应用简单 markdown 格式化
  return escaped
    .replace(/###\s*(.*)/g, '<h4>$1</h4>')
    .replace(/##\s*(.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
})

// 流式内容 HTML
const streamHtml = computed(() => {
  const text = streamContent.value || ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  return escaped
    .replace(/###\s*(.*)/g, '<h4>$1</h4>')
    .replace(/##\s*(.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
})

// 格式化时间
function formatTime(seconds: number | undefined): string {
  if (!seconds) return '无限制'
  const mins = Math.floor(seconds / 60)
  return `${mins} 分钟`
}

function getDefaultPracticeMinutes(seconds?: number): number {
  if (!seconds) return 15
  return Math.max(1, Math.ceil(seconds / 60))
}

function getTotalDurationSeconds(): number {
  return paperAnswers.value.reduce((total, answer) => total + (answer.duration || 0), 0)
}

function preparePracticeStart(
  questions: Question[],
  timeLimitSeconds: number,
  options?: { paperId?: number; paperTitle?: string }
) {
  pendingQuestions.value = questions
  pendingPaperId.value = options?.paperId
  pendingPaperTitle.value = options?.paperTitle || '套卷练习'
  pendingTimeLimitSeconds.value = timeLimitSeconds
  practiceTimeLimitMinutes.value = getDefaultPracticeMinutes(timeLimitSeconds)
  showStartPracticeConfig.value = true
}

function confirmStartPractice() {
  if (pendingQuestions.value.length === 0) {
    ElMessage.warning('题目加载失败，请重新选择')
    return
  }

  showStartPracticeConfig.value = false
  startPractice(pendingQuestions.value, practiceTimeLimitMinutes.value * 60, {
    paperId: pendingPaperId.value,
    paperTitle: pendingPaperTitle.value
  })
}

// 加载套卷列表
async function loadPapers() {
  loadingPapers.value = true
  try {
    const data = await paperApi.list({
      page: paperCurrentPage.value,
      page_size: paperPageSize.value,
      keyword: paperSearchKeyword.value.trim() || undefined
    })
    papers.value = data.items
    totalPapers.value = data.total
  } catch (e) {
    console.error('加载套卷失败', e)
  } finally {
    loadingPapers.value = false
  }
}

function handlePaperSearch() {
  window.clearTimeout(paperSearchTimer)
  paperCurrentPage.value = 1
  loadPapers()
}

function schedulePaperSearch() {
  window.clearTimeout(paperSearchTimer)
  paperSearchTimer = window.setTimeout(() => {
    handlePaperSearch()
  }, 300)
}

// 选择套卷
async function selectPaper(paper: Paper) {
  const sortedItems = [...paper.items].sort((a, b) => a.sort_order - b.sort_order)
  const results = await Promise.all(
    sortedItems.map(async (item) => {
      try {
        return await questionApi.get(item.question_id)
      } catch (e) {
        console.error('加载题目失败', e)
        return null
      }
    })
  )
  const questions = results.filter((question): question is Question => question !== null)

  if (questions.length === 0) {
    ElMessage.warning('套卷中没有题目')
    return
  }

  preparePracticeStart(questions, paper.time_limit_seconds || 900, {
    paperId: paper.id,
    paperTitle: paper.title
  })
}

async function deletePaper(paper: Paper) {
  try {
    await ElMessageBox.confirm(
      `确定删除试卷「${paper.title}」吗？将同步删除试卷题目及相关练习记录，且不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await paperApi.delete(paper.id)
    ElMessage.success('试卷及关联数据已删除')

    if (papers.value.length === 1 && paperCurrentPage.value > 1) {
      paperCurrentPage.value -= 1
    }

    await loadPapers()
  } catch (e) {
    if (e === 'cancel' || e === 'close') {
      return
    }
    console.error('删除试卷失败', e)
  }
}

// 开始自定义套卷
async function startCustomPaper() {
  const lines = customQuestions.value.split('\n').filter(l => l.trim())
  if (lines.length < 1) {
    ElMessage.warning('请至少输入一道题目')
    return
  }

  // 先将自定义题目保存到数据库，获取真实 ID
  const questions: Question[] = []
  const questionIds: number[] = []
  for (const content of lines) {
    try {
      const savedQuestion = await questionApi.create({
        content: content.trim(),
        category: '自定义'
      })
      questions.push(savedQuestion)
      questionIds.push(savedQuestion.id)
    } catch (e) {
      console.error('保存自定义题目失败', e)
      ElMessage.error('保存题目失败，请重试')
      return
    }
  }

  // 保存套卷到数据库
  let createdPaper: Paper | null = null
  try {
    createdPaper = await paperApi.create({
      title: customPaperTitle.value,
      time_limit_seconds: customTimeLimit.value * 60,
      question_ids: questionIds
    })
  } catch (e) {
    console.error('保存套卷失败', e)
    // 继续练习，不阻塞用户
  }

  showCustomPaper.value = false
  startPractice(questions, customTimeLimit.value * 60, {
    paperId: createdPaper?.id,
    paperTitle: customPaperTitle.value.trim() || '自定义练习套卷'
  })
}

// 开始练习
function startPractice(
  questions: Question[],
  timeLimit: number,
  options?: { paperId?: number; paperTitle?: string }
) {
  practiceStore.resetPaper()
  practiceStore.mode = 'paper'
  practiceStore.paperSessionId = uuidv4()
  practiceStore.paperQuestions = questions
  practiceStore.paperTimeLimit = timeLimit
  practiceStore.currentQuestionIndex = 0
  practiceStartedAt.value = new Date().toISOString()
  activePaperId.value = options?.paperId
  activePaperTitle.value = options?.paperTitle || '套卷练习'
  currentTranscript.value = ''
  streamContent.value = ''
  paperAnalysis.value = ''
  isAnalyzing.value = false
  isStreaming.value = false
  resumePaperTimerAfterTranscription.value = false

  // 初始化每题答案
  paperAnswers.value = questions.map(q => ({
    questionId: q.id,
    transcript: '',
    duration: 0
  }))

  // 设置倒计时
  paperTimer.reset(timeLimit)
  paperTimer.start()
  questionTimer.reset()

  step.value = 'practice'
}

// 获取当前题目
function getCurrentQuestion(): Question | undefined {
  return practiceStore.paperQuestions[practiceStore.currentQuestionIndex]
}

// 检查题目是否已作答
function isQuestionAnswered(index: number): boolean {
  return !!paperAnswers.value[index]?.transcript
}

function pausePaperTimerForTranscription() {
  resumePaperTimerAfterTranscription.value = step.value === 'practice' && paperTimer.isRunning.value
  if (resumePaperTimerAfterTranscription.value) {
    paperTimer.pause()
  }
}

function resumePaperTimerIfNeeded() {
  if (
    resumePaperTimerAfterTranscription.value
    && step.value === 'practice'
    && !practiceStore.isRecording
    && paperTimer.seconds.value > 0
  ) {
    paperTimer.start()
  }
  resumePaperTimerAfterTranscription.value = false
}

// 切换题目
function switchQuestion(index: number) {
  if (practiceStore.isRecording) {
    ElMessage.warning('请先结束当前录音')
    return
  }
  if (recorder.isTranscribing.value) {
    ElMessage.warning('转写中，请稍候')
    return
  }

  // 保存当前题目的答案
  saveCurrentAnswer()

  practiceStore.currentQuestionIndex = index
  currentTranscript.value = paperAnswers.value[index]?.transcript || ''
  questionTimer.reset()
}

// 保存当前题目答案
function saveCurrentAnswer() {
  const index = practiceStore.currentQuestionIndex
  if (paperAnswers.value[index]) {
    paperAnswers.value[index].transcript = currentTranscript.value
    paperAnswers.value[index].duration += questionTimer.seconds.value
  }
}

// 切换录音
async function toggleRecording() {
  if (!practiceStore.isRecording) {
    try {
      await recorder.start()
      practiceStore.isRecording = true
      questionTimer.start()
    } catch (e) {
      ElMessage.error('无法启动录音')
    }
  } else {
    // 先停止计时器，确保时长准确
    practiceStore.isRecording = false
    questionTimer.pause()
    pausePaperTimerForTranscription()
    try {
      const result = await recorder.stop()

      if (result.transcript) {
        currentTranscript.value += result.transcript
      }
    } finally {
      resumePaperTimerIfNeeded()
    }
  }
}

// 重试转写
async function handleRetryTranscribe() {
  pausePaperTimerForTranscription()
  try {
    const result = await recorder.retryTranscribe()
    if (result) {
      currentTranscript.value += result
    }
  } finally {
    resumePaperTimerIfNeeded()
  }
}

// 确认结束
async function confirmEnd() {
  if (recorder.isTranscribing.value) {
    ElMessage.warning('正在转写，请稍候再结束')
    return
  }

  try {
    await ElMessageBox.confirm('确定结束本次面试吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    finishPractice()
  } catch {
    // 取消
  }
}

// 完成练习
async function finishPractice() {
  if (recorder.isTranscribing.value) {
    ElMessage.warning('正在转写，请稍候')
    return
  }

  // 停止录音
  if (practiceStore.isRecording) {
    practiceStore.isRecording = false
    questionTimer.pause()
    paperTimer.pause()
    const result = await recorder.stop()
    if (result.transcript) {
      currentTranscript.value += result.transcript
    }
  }

  // 保存当前答案
  saveCurrentAnswer()
  paperTimer.stop()
  questionTimer.stop()

  step.value = 'result'
  streamContent.value = ''
  paperAnalysis.value = ''

  const finishedAt = new Date().toISOString()
  const answeredQuestions = paperAnswers.value.filter(answer => answer.transcript.trim())
  if (answeredQuestions.length === 0) {
    isAnalyzing.value = false
    isStreaming.value = false
    paperAnalysis.value = '本次套题未检测到有效作答，未生成 AI 分析。'
    return
  }

  isAnalyzing.value = true
  isStreaming.value = true

  try {
    // 提交每道题的作答
    for (let i = 0; i < paperAnswers.value.length; i++) {
      const ans = paperAnswers.value[i]
      const question = practiceStore.paperQuestions[i]

      if (ans.transcript.trim()) {
        const answer = await answerApi.create({
          mode: 'paper',
          question_id: question.id,
          paper_id: activePaperId.value,
          paper_session_id: practiceStore.paperSessionId,
          transcript: ans.transcript,
          duration_seconds: ans.duration,
          started_at: practiceStartedAt.value || finishedAt,
          finished_at: finishedAt
        })

        paperAnswers.value[i].answerId = answer.id
      }
    }

    await answerApi.savePaperSession({
      paper_session_id: practiceStore.paperSessionId,
      paper_id: activePaperId.value,
      paper_title: activePaperTitle.value,
      time_limit_seconds: practiceStore.paperTimeLimit,
      total_duration_seconds: getTotalDurationSeconds(),
      question_count: practiceStore.paperQuestions.length,
      started_at: practiceStartedAt.value || finishedAt,
      finished_at: finishedAt
    })

    // 调用套卷流式分析 API
    if (practiceStore.paperSessionId) {
      await startPaperStreamAnalysis(practiceStore.paperSessionId)
    } else {
      paperAnalysis.value = '套卷分析已提交，可在历史记录中查看。'
      isAnalyzing.value = false
      isStreaming.value = false
    }
  } catch (e) {
    console.error('提交失败', e)
    ElMessage.error('提交失败')
    paperAnalysis.value = '分析失败，请稍后重试。'
    isAnalyzing.value = false
    isStreaming.value = false
  }
}

// 流式分析套卷
async function startPaperStreamAnalysis(sessionId: string) {
  try {
    const response = await fetch(`/api/v1/answers/paper-analyze/stream/${sessionId}`)

    if (response.status === 409) {
      ElMessage.warning('分析正在进行中，请稍候')
      isStreaming.value = false
      return
    }

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.content) {
              streamContent.value += data.content
            }
            if (data.full_content !== undefined) {
              paperAnalysis.value = data.full_content
              isStreaming.value = false
              isAnalyzing.value = false
            }
            if (data.message) {
              ElMessage.error(data.message)
              isStreaming.value = false
              isAnalyzing.value = false
            }
          } catch {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (e) {
    console.error('流式分析失败', e)
    ElMessage.error('分析请求失败')
    isStreaming.value = false
    isAnalyzing.value = false
  }
}

// 重置
function reset() {
  practiceStore.resetPaper()
  paperTimer.reset()
  questionTimer.reset()
  step.value = 'select'
  paperAnalysis.value = ''
  streamContent.value = ''
  paperAnswers.value = []
  currentTranscript.value = ''
  activePaperId.value = undefined
  activePaperTitle.value = '套卷练习'
  practiceStartedAt.value = ''
  resumePaperTimerAfterTranscription.value = false
}

// 再次练习（保留题目，重置状态）
function handleRetry() {
  const questions = [...practiceStore.paperQuestions]

  if (questions.length === 0) {
    ElMessage.warning('无法重试，题目信息丢失')
    reset()
    return
  }

  startPractice(questions, practiceStore.paperTimeLimit, {
    paperId: activePaperId.value,
    paperTitle: activePaperTitle.value
  })
}

// 重新生成套卷分析
async function handleRegeneratePaperAnalysis() {
  if (!practiceStore.paperSessionId) {
    ElMessage.warning('无法重新生成，请重新作答')
    return
  }

  isAnalyzing.value = true
  isStreaming.value = true
  streamContent.value = ''
  paperAnalysis.value = ''

  await startPaperStreamAnalysis(practiceStore.paperSessionId)
}

onMounted(async () => {
  loadPapers()
  appStore.loadSpeechConfig()

  // 处理从题库进入的情况
  const questionIdsParam = route.query.questionIds as string
  const timeLimitParam = route.query.timeLimit as string

  if (questionIdsParam) {
    const ids = questionIdsParam.split(',').map(Number)
    const timeLimit = Number(timeLimitParam) || 900

    const results = await Promise.all(
      ids.map(async (id) => {
        try {
          return await questionApi.get(id)
        } catch (e) {
          console.error('加载题目失败', e)
          return null
        }
      })
    )
    const questions = results.filter((question): question is Question => question !== null)

    if (questions.length > 0) {
      preparePracticeStart(questions, timeLimit, {
        paperTitle: '题库选题练习'
      })
    } else {
      ElMessage.error('题目加载失败')
    }
  }
})

onUnmounted(() => {
  window.clearTimeout(paperSearchTimer)
})
</script>

<style scoped>
.paper-practice {
  max-width: 800px;
  margin: 0 auto;
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.paper-search {
  margin-bottom: 16px;
}

.paper-pagination {
  justify-content: center;
  margin-top: 20px;
}

.paper-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.paper-item:hover {
  background: #e6f0ff;
}

.paper-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.paper-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.paper-title {
  font-size: 16px;
  font-weight: 500;
}

.paper-meta {
  font-size: 13px;
  color: #909399;
}

.paper-timer {
  text-align: center;
  margin-bottom: 20px;
}

.timer-status {
  margin-top: 8px;
  font-size: 13px;
  color: #e6a23c;
}

.start-config-summary {
  margin-bottom: 16px;
}

.start-config-title {
  font-size: 18px;
  font-weight: 600;
}

.start-config-meta {
  margin-top: 6px;
  font-size: 13px;
  color: #909399;
}

.start-config-questions {
  margin-top: 8px;
}

.start-config-questions-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.start-config-question-item {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 8px;
  line-height: 1.7;
}

.start-config-question-index {
  flex: 0 0 auto;
  font-weight: 600;
  color: #409eff;
}

.start-config-question-content {
  color: #303133;
  white-space: pre-wrap;
}

.question-nav {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 20px;
}

.nav-item {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  cursor: pointer;
  font-size: 14px;
}

.nav-item.active {
  background: #409eff;
  color: #fff;
}

.nav-item.answered {
  background: #67c23a;
  color: #fff;
}

.nav-item.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.question-section {
  margin-bottom: 20px;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.question-number {
  font-weight: 500;
}

.question-content {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  line-height: 1.8;
}

.answer-timer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 15px 0;
}

.timer-display.small {
  font-size: 24px;
}

.record-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 20px 0;
}

.record-btn {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
}

.record-btn.idle {
  background: #409eff;
  color: #fff;
}

.record-btn.recording {
  background: #f56c6c;
  color: #fff;
  animation: pulse 1.5s infinite;
}

.record-btn.transcribing {
  background: #e6a23c;
  color: #fff;
  cursor: wait;
}

.record-btn:disabled {
  cursor: wait;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.record-hint {
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

.transcript-section {
  margin: 15px 0;
}

.action-buttons {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.score-overview {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.score-label {
  font-size: 12px;
  color: #909399;
}

.score-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.analysis-content {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.result-actions {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.7); }
  70% { box-shadow: 0 0 0 20px rgba(245, 108, 108, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0); }
}

.transcribe-error {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding: 8px 12px;
  background: #fef0f0;
  border-radius: 4px;
  border: 1px solid #fde2e2;
}

.transcribe-error .error-text {
  color: #f56c6c;
  font-size: 14px;
  flex: 1;
}
</style>
