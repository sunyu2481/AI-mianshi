import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

// 扩展 AxiosRequestConfig 支持静默模式
declare module 'axios' {
  interface AxiosRequestConfig {
    _silent?: boolean
  }
}

// 动态获取 API 基础地址
function getBaseURL(): string {
  // 优先使用环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  // 默认使用同源 API，适用于：
  // 1. Vite 开发代理
  // 2. Nginx / Docker 反向代理
  // 3. Windows EXE 内置本地服务
  return '/api/v1'
}

const request = axios.create({
  baseURL: getBaseURL(),
  timeout: 60000 // AI 分析可能需要较长时间
})

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 静默模式不显示错误提示
    if (error.config?._silent) {
      return Promise.reject(error)
    }
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default request
