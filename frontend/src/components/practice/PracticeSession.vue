<template>
  <div class="page-card">
    <div class="question-section">
      <div class="question-header">
        <el-tag v-if="question?.category" type="info">
          {{ question.category }}
        </el-tag>
        <el-button text @click="handleBack">
          <el-icon><Back /></el-icon>
          返回选题
        </el-button>
      </div>
      <div class="question-content">
        {{ question?.content }}
      </div>
    </div>

    <!-- 计时器 -->
    <div class="timer-section">
      <span class="timer-label">作答时长</span>
      <span class="timer-display" :class="{ recording: isRecording }">
        {{ formattedTime }}
      </span>
    </div>

    <div class="video-record-section">
      <div class="video-preview-wrapper">
        <video
          v-if="videoRecorder.previewStream.value"
          ref="videoPreviewRef"
          class="video-preview"
          autoplay
          muted
          playsinline
        />
        <div v-else class="video-placeholder">
          {{ videoRecorder.error.value || '点击开始作答后自动开启视频录制' }}
        </div>
      </div>
      <div class="video-actions">
        <el-tag :type="videoRecorder.isRecording.value ? 'danger' : (lastVideoBlob ? 'success' : 'info')">
          {{ videoRecorder.isRecording.value ? '视频录制中' : (lastVideoBlob ? '视频已保存' : '等待录制') }}
        </el-tag>
        <el-button
          v-if="videoRecorder.isRecording.value"
          size="small"
          type="danger"
          plain
          @click="stopVideoRecording(true)"
        >
          停止并保存视频
        </el-button>
        <el-button
          v-else-if="lastVideoBlob"
          size="small"
          type="primary"
          plain
          @click="handleDownloadVideo"
        >
          下载视频
        </el-button>
      </div>
      <p class="video-hint">视频只保存在本机，不会上传服务器。</p>
    </div>

    <!-- 录音控制 -->
    <div class="record-section">
      <button
        type="button"
        class="record-btn"
        :class="{ idle: !isRecording && !recorder.isTranscribing.value, recording: isRecording, transcribing: recorder.isTranscribing.value }"
        :aria-label="isRecording ? '结束录音' : '开始录音'"
        :aria-pressed="isRecording"
        :disabled="recorder.isTranscribing.value"
        @click="toggleRecording"
      >
        <el-icon :size="32">
          <Loading v-if="recorder.isTranscribing.value" class="spin-icon" />
          <Microphone v-else-if="!isRecording" />
          <VideoPause v-else />
        </el-icon>
      </button>
      <p class="record-hint">
        {{ recorder.isTranscribing.value ? '正在转写...' : (isRecording ? '点击结束作答' : '点击开始作答') }}
      </p>
    </div>

    <!-- 转写文本 -->
    <div class="transcript-section">
      <h4>作答内容</h4>
      <div v-if="recorder.isTranscribing.value" class="transcribing-hint">
        正在转写语音，请稍候...
      </div>
      <!-- 转写错误提示与重试 -->
      <div v-if="recorder.error.value && !recorder.isTranscribing.value" class="transcribe-error">
        <span class="error-text">{{ recorder.error.value }}</span>
        <el-button
          v-if="recorder.canRetryTranscribe.value"
          type="warning"
          size="small"
          :loading="recorder.isTranscribing.value"
          @click="handleRetryTranscribe"
        >
          重新转写
        </el-button>
      </div>
      <div v-if="lastRecordingBlob && !isRecording" class="audio-actions">
        <el-button
          type="primary"
          plain
          size="small"
          :disabled="recorder.isTranscribing.value"
          @click="handleDownloadRecording"
        >
          下载录音
        </el-button>
      </div>
      <el-input
        v-model="transcript"
        type="textarea"
        :rows="6"
        placeholder="录音转写内容将显示在这里，您也可以手动编辑..."
      />
    </div>

    <!-- 操作按钮 -->
    <div class="action-buttons">
      <el-button @click="handleBack">取消</el-button>
      <el-button
        type="primary"
        @click="submitAnswer"
        :disabled="!transcript.trim()"
      >
        面试结束，提交分析
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, VideoPause, Back, Loading } from '@element-plus/icons-vue'
import { useTimer } from '@/composables/useTimer'
import { useRecorder } from '@/composables/useRecorder'
import { useVideoRecorder } from '@/composables/useVideoRecorder'
import { useAppStore } from '@/store/app'

export interface Question {
  id: number
  content: string
  category?: string
}

const props = defineProps<{
  question: Question
}>()

const emit = defineEmits<{
  back: []
  complete: [data: {
    transcript: string
    duration: number
    audioBlob: Blob | null
    audioFileName: string
    videoBlob: Blob | null
    videoFileName: string
  }]
}>()

const appStore = useAppStore()
const timer = useTimer('countup')
const recorder = useRecorder()
const videoRecorder = useVideoRecorder()

const isRecording = ref(false)
const transcript = ref('')
const lastRecordingBlob = ref<Blob | null>(null)
const lastRecordingFileName = ref('')
const lastVideoBlob = ref<Blob | null>(null)
const lastVideoFileName = ref('')
const videoPreviewRef = ref<HTMLVideoElement | null>(null)

const formattedTime = computed(() => timer.formatted.value)

// 实时同步识别文本（useRecorder 已经处理了追加逻辑）
watch(() => recorder.transcript.value, (val) => {
  if (val !== undefined && isRecording.value) {
    transcript.value = val
  }
})

watch(() => videoRecorder.previewStream.value, async (stream) => {
  await nextTick()
  if (videoPreviewRef.value) {
    videoPreviewRef.value.srcObject = stream
  }
}, { immediate: true })

// 监听录音错误
watch(() => recorder.error.value, (err) => {
  if (err) {
    ElMessage.error(err)
  }
})

async function startVideoRecording() {
  if (videoRecorder.isRecording.value) {
    return true
  }

  try {
    await videoRecorder.start()
    return true
  } catch {
    ElMessage.warning('无法启动视频录制，仍可继续作答')
    return false
  }
}

async function stopVideoRecording(download = true) {
  if (!videoRecorder.isRecording.value) {
    return
  }

  const result = await videoRecorder.stop(download)
  lastVideoBlob.value = result.videoBlob
  lastVideoFileName.value = result.videoFileName

  if (download && result.videoBlob) {
    ElMessage.success('已开始下载视频')
  }
}

async function toggleRecording() {
  if (!isRecording.value) {
    let videoStarted = false
    try {
      lastRecordingBlob.value = null
      lastRecordingFileName.value = ''
      lastVideoBlob.value = null
      lastVideoFileName.value = ''
      videoStarted = await startVideoRecording()
      await recorder.start()
      isRecording.value = true
      timer.start()
    } catch (e) {
      if (videoStarted) {
        await stopVideoRecording(false)
      }
      ElMessage.error('无法启动录音，请检查麦克风权限')
    }
  } else {
    isRecording.value = false
    timer.stop()
    const result = await recorder.stop()
    lastRecordingBlob.value = result.audioBlob
    lastRecordingFileName.value = result.audioFileName
    transcript.value = recorder.transcript.value
    await stopVideoRecording(true)
  }
}

async function submitAnswer() {
  if (!transcript.value.trim()) {
    ElMessage.warning('请先进行作答')
    return
  }

  if (isRecording.value) {
    isRecording.value = false
    timer.stop()
    const result = await recorder.stop()
    lastRecordingBlob.value = result.audioBlob
    lastRecordingFileName.value = result.audioFileName
    transcript.value = recorder.transcript.value
  }

  await stopVideoRecording(true)

  emit('complete', {
    transcript: transcript.value,
    duration: timer.seconds.value,
    audioBlob: lastRecordingBlob.value,
    audioFileName: lastRecordingFileName.value,
    videoBlob: lastVideoBlob.value,
    videoFileName: lastVideoFileName.value
  })
}

async function handleRetryTranscribe() {
  const result = await recorder.retryTranscribe()
  if (result) {
    transcript.value = recorder.transcript.value
  }
}

function handleDownloadRecording() {
  if (!lastRecordingBlob.value) {
    ElMessage.warning('暂无可下载的录音')
    return
  }

  const url = URL.createObjectURL(lastRecordingBlob.value)
  const link = document.createElement('a')
  link.href = url
  link.download = lastRecordingFileName.value || 'recording.webm'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
  ElMessage.success('已开始下载录音')
}

function handleDownloadVideo() {
  if (videoRecorder.downloadLastVideo()) {
    ElMessage.success('已开始下载视频')
  } else {
    ElMessage.warning(videoRecorder.error.value || '暂无可下载的视频')
  }
}

async function handleBack() {
  timer.stop()
  await stopVideoRecording(false)
  emit('back')
}

onMounted(() => {
  appStore.loadSpeechConfig()
})
</script>

<style scoped>
.question-section {
  margin-bottom: 20px;
}

.question-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.question-content {
  font-size: 16px;
  line-height: 1.8;
  color: #303133;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.timer-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  margin: 20px 0;
}

.timer-label {
  color: #909399;
}

.timer-display {
  font-size: 36px;
  font-weight: bold;
  font-family: 'Courier New', monospace;
}

.timer-display.recording {
  color: #f56c6c;
}

.video-record-section {
  margin: 24px 0;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #fafafa;
}

.video-preview-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  overflow: hidden;
  border-radius: 8px;
  background: #1f2d3d;
}

.video-preview {
  width: 100%;
  max-height: 320px;
  object-fit: cover;
}

.video-placeholder {
  color: #c0c4cc;
  font-size: 14px;
}

.video-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 12px;
}

.video-hint {
  margin: 8px 0 0;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.record-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 30px 0;
}

.record-btn {
  width: 100px;
  height: 100px;
  border: none;
  border-radius: 50%;
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

.record-btn.idle:hover {
  background: #66b1ff;
}

.record-btn.recording {
  background: #f56c6c;
  color: #fff;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.7); }
  70% { box-shadow: 0 0 0 25px rgba(245, 108, 108, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0); }
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

.transcribe-error {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
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

.audio-actions {
  margin-bottom: 8px;
}

.record-hint {
  margin-top: 10px;
  color: #909399;
}

.transcript-section {
  margin: 20px 0;
}

.transcript-section h4 {
  margin-bottom: 10px;
  color: #606266;
}

.transcribing-hint {
  color: #e6a23c;
  font-size: 14px;
  margin-bottom: 8px;
  animation: blink 1.5s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .timer-display {
    font-size: 28px;
  }

  .record-btn {
    width: 80px;
    height: 80px;
  }
}
</style>
