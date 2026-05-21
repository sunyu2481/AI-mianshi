import { ref, onUnmounted } from 'vue'

export interface VideoRecorderResult {
  duration: number
  videoBlob: Blob | null
  videoFileName: string
}

export function useVideoRecorder() {
  const isSupported = ref(
    typeof navigator !== 'undefined'
    && !!navigator.mediaDevices?.getUserMedia
    && typeof MediaRecorder !== 'undefined'
  )
  const isRecording = ref(false)
  const previewStream = ref<MediaStream | null>(null)
  const error = ref<string | null>(null)
  const lastVideoBlob = ref<Blob | null>(null)
  const lastVideoFileName = ref('')

  let mediaRecorder: MediaRecorder | null = null
  let videoChunks: Blob[] = []
  let startTime = 0

  function createVideoFileName() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    return `interview-recording-${timestamp}.webm`
  }

  function getSupportedMimeType() {
    const candidates = [
      'video/webm;codecs=vp9,opus',
      'video/webm;codecs=vp8,opus',
      'video/webm;codecs=h264,opus',
      'video/webm'
    ]

    return candidates.find(type => MediaRecorder.isTypeSupported(type)) || ''
  }

  function downloadBlob(blob: Blob, fileName: string) {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  async function start() {
    if (!isSupported.value) {
      error.value = '当前浏览器不支持视频录制'
      throw new Error(error.value)
    }

    if (isRecording.value) {
      return
    }

    let stream: MediaStream | null = null
    try {
      error.value = null
      lastVideoBlob.value = null
      lastVideoFileName.value = ''
      videoChunks = []

      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      previewStream.value = stream

      const mimeType = getSupportedMimeType()
      mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          videoChunks.push(event.data)
        }
      }

      mediaRecorder.start(1000)
      startTime = Date.now()
      isRecording.value = true
    } catch (e) {
      stream?.getTracks().forEach(track => track.stop())
      previewStream.value = null
      mediaRecorder = null
      error.value = '无法访问摄像头或麦克风'
      throw e
    }
  }

  function stop(download = true): Promise<VideoRecorderResult> {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      return Promise.resolve({
        duration: 0,
        videoBlob: lastVideoBlob.value,
        videoFileName: lastVideoFileName.value
      })
    }

    const recorder = mediaRecorder
    const duration = Math.floor((Date.now() - startTime) / 1000)

    return new Promise((resolve) => {
      recorder.onstop = () => {
        const videoBlob = new Blob(videoChunks, { type: recorder.mimeType || 'video/webm' })
        recorder.stream.getTracks().forEach(track => track.stop())
        previewStream.value = null
        mediaRecorder = null
        isRecording.value = false

        const savedVideoBlob = videoBlob.size > 0 ? videoBlob : null
        const videoFileName = savedVideoBlob ? createVideoFileName() : ''

        if (savedVideoBlob) {
          lastVideoBlob.value = savedVideoBlob
          lastVideoFileName.value = videoFileName
          if (download) {
            downloadBlob(savedVideoBlob, videoFileName)
          }
        }

        resolve({ duration, videoBlob: savedVideoBlob, videoFileName })
      }

      recorder.stop()
    })
  }

  function downloadLastVideo() {
    if (!lastVideoBlob.value) {
      error.value = '没有可下载的视频数据'
      return false
    }

    downloadBlob(lastVideoBlob.value, lastVideoFileName.value || createVideoFileName())
    return true
  }

  onUnmounted(() => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stream.getTracks().forEach(track => track.stop())
      mediaRecorder.stop()
    }
    previewStream.value = null
    mediaRecorder = null
    isRecording.value = false
  })

  return {
    isSupported,
    isRecording,
    previewStream,
    error,
    lastVideoBlob,
    lastVideoFileName,
    start,
    stop,
    downloadLastVideo
  }
}
