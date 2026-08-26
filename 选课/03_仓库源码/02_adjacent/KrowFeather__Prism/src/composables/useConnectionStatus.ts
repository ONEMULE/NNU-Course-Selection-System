import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 全局连接状态
export const connectionStatus = ref<'connected' | 'disconnected' | 'reconnecting'>('disconnected')
export const isReconnecting = ref(false)

// 从 localStorage 获取 API 地址
const getApiUrl = () => {
  return localStorage.getItem('apiUrl') || 'http://localhost:5000'
}

// 自动重新登录
async function autoReLogin(): Promise<boolean> {
  const loginInfo = localStorage.getItem('loginInfo')
  if (!loginInfo) {
    return false
  }

  try {
    const loginData = JSON.parse(loginInfo)
    const API_BASE_URL = getApiUrl()
    
    const response = await axios.post(`${API_BASE_URL}/login`, {
      username: loginData.username,
      password: loginData.password
    })

    if (response.data.success) {
      // 更新登录信息
      localStorage.setItem('loginInfo', JSON.stringify({
        username: loginData.username,
        password: loginData.password,
        token: response.data.token,
        WEU: response.data.WEU,
        JSESSIONID: response.data.JSESSIONID
      }))
      
      connectionStatus.value = 'connected'
      isReconnecting.value = false
      ElMessage.success('已自动重新登录')
      return true
    }
  } catch (error) {
    console.error('自动重新登录失败:', error)
  }
  
  connectionStatus.value = 'disconnected'
  isReconnecting.value = false
  return false
}

// 设置 axios 拦截器
export function setupAxiosInterceptors() {
  // 请求拦截器
  axios.interceptors.request.use(
    (config) => {
      // 如果有登录信息，添加 token（如果需要）
      const loginInfo = localStorage.getItem('loginInfo')
      if (loginInfo) {
        // 如果后端需要 token，可以在这里添加
        // const loginData = JSON.parse(loginInfo)
        // config.headers.Authorization = `Bearer ${loginData.token}`
      }
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // 响应拦截器
  axios.interceptors.response.use(
    (response) => {
      // 请求成功，更新连接状态
      if (connectionStatus.value !== 'connected') {
        connectionStatus.value = 'connected'
        isReconnecting.value = false
      }
      return response
    },
    async (error) => {
      // 处理 401 错误
      if (error.response && error.response.status === 401) {
        connectionStatus.value = 'disconnected'
        
        // 如果正在重连，避免重复请求
        if (isReconnecting.value) {
          return Promise.reject(error)
        }
        
        // 尝试自动重新登录
        isReconnecting.value = true
        connectionStatus.value = 'reconnecting'
        
        const reLoginSuccess = await autoReLogin()
        
        if (reLoginSuccess) {
          // 重新登录成功，重试原始请求
          const originalRequest = error.config
          return axios(originalRequest)
        } else {
          // 重新登录失败
          ElMessage.error('登录已过期，请重新登录')
          // 清除登录信息
          localStorage.removeItem('loginInfo')
          // 可以在这里跳转到登录页
          // router.push('/')
        }
      } else if (error.response) {
        // 其他错误，但请求已发送，说明连接正常
        connectionStatus.value = 'connected'
      } else if (error.request) {
        // 请求已发出但没有收到响应，可能是网络问题
        connectionStatus.value = 'disconnected'
      }
      
      return Promise.reject(error)
    }
  )
}

// 初始化连接状态
export function initConnectionStatus() {
  const loginInfo = localStorage.getItem('loginInfo')
  if (loginInfo) {
    connectionStatus.value = 'connected'
  } else {
    connectionStatus.value = 'disconnected'
  }
}

