<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue'
import { useRoute } from 'vue-router'
import { connectionStatus, initConnectionStatus } from './composables/useConnectionStatus'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh, Document, Search, List, Setting } from '@element-plus/icons-vue'

declare global {
  interface Window {
    windowControls: {
      minimize: () => void
      maximize: () => Promise<boolean>
      isMaximized: () => Promise<boolean>
      close: () => void
      onMaximized: (callback: () => void) => void
      onUnmaximized: (callback: () => void) => void
      onWindowWillClose: (callback: () => void) => void
      removeMaximizedListeners: () => void
      removeWindowWillCloseListener: () => void
    }
  }
}

const route = useRoute()

// 检查是否已登录
const isLoggedIn = computed(() => {
  return !!localStorage.getItem('loginInfo')
})

// 检查是否在登录页面
const isLoginPage = computed(() => {
  return route.path === '/'
})

// 状态文本
const statusText = computed(() => {
  if (connectionStatus.value === 'reconnecting') {
    return 'reconnecting...'
  }
  return connectionStatus.value
})

// 状态颜色类
const statusClass = computed(() => {
  if (connectionStatus.value === 'connected') {
    return 'status-connected'
  } else if (connectionStatus.value === 'reconnecting') {
    return 'status-reconnecting'
  } else {
    return 'status-disconnected'
  }
})

// 监听登录状态变化
watch(isLoggedIn, (newVal) => {
  if (newVal) {
    initConnectionStatus()
  } else {
    connectionStatus.value = 'disconnected'
  }
})

const isMaximized = ref(false)
const isRelogging = ref(false)

// 检查是否有登录信息
const hasLoginInfo = computed(() => {
  const loginInfo = localStorage.getItem('loginInfo')
  if (!loginInfo) return false
  try {
    const info = JSON.parse(loginInfo)
    return !!(info.username && info.password)
  } catch {
    return false
  }
})

// 获取 API URL
function getApiUrl() {
  const stored = localStorage.getItem('apiUrl')
  return stored || 'http://localhost:5000'
}

// 强制重新登录
async function handleRelogin() {
  if (isRelogging.value) return
  
  const loginInfo = localStorage.getItem('loginInfo')
  if (!loginInfo) {
    ElMessage.warning('未找到登录信息，请先登录')
    return
  }
  
  let username: string, password: string
  try {
    const info = JSON.parse(loginInfo)
    username = info.username
    password = info.password
    if (!username || !password) {
      ElMessage.warning('登录信息不完整，请重新登录')
      return
    }
  } catch {
    ElMessage.error('登录信息格式错误，请重新登录')
    return
  }
  
  isRelogging.value = true
  connectionStatus.value = 'reconnecting'
  
  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/login`, {
      username: username,
      password: password
    })
    
    if (response.data.success) {
      // 更新登录信息
      const newLoginInfo = {
        username: username,
        password: password,
        token: response.data.token,
        WEU: response.data.WEU,
        JSESSIONID: response.data.JSESSIONID
      }
      localStorage.setItem('loginInfo', JSON.stringify(newLoginInfo))
      
      // 更新连接状态
      connectionStatus.value = 'connected'
      ElMessage.success('重新登录成功')
    } else {
      connectionStatus.value = 'disconnected'
      ElMessage.error(response.data.message || '重新登录失败')
    }
  } catch (error: any) {
    connectionStatus.value = 'disconnected'
    let errorMsg = '重新登录失败，请重试'
    if (error.response) {
      errorMsg = error.response.data?.message || errorMsg
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请确保服务正在运行'
    } else {
      errorMsg = error.message || errorMsg
    }
    ElMessage.error(errorMsg)
  } finally {
    isRelogging.value = false
  }
}

// 清除登录状态
function clearLoginState() {
  // 清除登录信息
  localStorage.removeItem('loginInfo')
  localStorage.removeItem('selectedBatchCode')
  localStorage.removeItem('enabledTabs')
  localStorage.removeItem('tabNames')
  
  // 清除连接状态
  connectionStatus.value = 'disconnected'
  
  // 清除抢课任务状态（如果有的话）
  // 注意：这里只是清除前端状态，后端任务会继续运行直到完成或手动停止
}

onMounted(() => {
  initConnectionStatus()
  checkMaximizedState()
  
  // 监听窗口最大化/还原事件
  if (window.windowControls) {
    if (typeof window.windowControls.onMaximized === 'function') {
      window.windowControls.onMaximized(() => {
        isMaximized.value = true
      })
    }
    if (typeof window.windowControls.onUnmaximized === 'function') {
      window.windowControls.onUnmaximized(() => {
        isMaximized.value = false
      })
    }
    
    // 监听窗口关闭事件，清除登录状态
    // 注意：只在真正关闭窗口时清除，不要在其他时候触发
    if (typeof window.windowControls.onWindowWillClose === 'function') {
      window.windowControls.onWindowWillClose(() => {
        console.log('窗口即将关闭，清除登录状态')
        // 延迟清除，确保窗口已经关闭
        setTimeout(() => {
          clearLoginState()
        }, 100)
      })
    }
  }
})

// 组件卸载时清理监听器
onUnmounted(() => {
  if (window.windowControls) {
    if (typeof window.windowControls.removeMaximizedListeners === 'function') {
      window.windowControls.removeMaximizedListeners()
    }
    if (typeof window.windowControls.removeWindowWillCloseListener === 'function') {
      window.windowControls.removeWindowWillCloseListener()
    }
  }
})

// 检查窗口最大化状态
async function checkMaximizedState() {
  if (window.windowControls && typeof window.windowControls.isMaximized === 'function') {
    isMaximized.value = await window.windowControls.isMaximized()
  }
}

function onMinimize() {
  if (window.windowControls && typeof window.windowControls.minimize === 'function') {
    window.windowControls.minimize()
  }
}

async function onMaximize() {
  if (window.windowControls && typeof window.windowControls.maximize === 'function') {
    await window.windowControls.maximize()
    // 更新状态
    setTimeout(() => {
      checkMaximizedState()
    }, 100)
  }
}

function onClose() {
  if (window.windowControls && typeof window.windowControls.close === 'function') {
    window.windowControls.close()
  }
}
</script>

<template>
  <div class="app-container">
    <div class="titlebar">
      <div class="title">Prism</div>
      <div class="title-controls">
        <button class="control-btn" type="button" @click="onMinimize" title="最小化">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
        <button class="control-btn" type="button" @click="onMaximize" :title="isMaximized ? '还原' : '最大化'">
          <svg v-if="!isMaximized" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden>
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden>
            <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"></path>
          </svg>
        </button>
        <button class="control-btn close" type="button" @click="onClose" title="关闭">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden>
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    <div class="content">
      <!-- 登录页面 -->
      <div v-if="isLoginPage" class="login-wrapper">
        <router-view />
      </div>

      <!-- 主页面（已登录） -->
      <div v-else class="main-layout">
        <nav class="sidebar">
          <router-link to="/select-class" class="nav-item" active-class="active">
            <el-icon class="nav-icon"><Document /></el-icon>
            <span class="nav-text">开始选课</span>
          </router-link>
          <router-link to="/browse" class="nav-item" active-class="active">
            <el-icon class="nav-icon"><Search /></el-icon>
            <span class="nav-text">抢课</span>
          </router-link>
          <router-link to="/selected-courses" class="nav-item" active-class="active">
            <el-icon class="nav-icon"><List /></el-icon>
            <span class="nav-text">已选课程</span>
          </router-link>
          <router-link to="/settings" class="nav-item" active-class="active">
            <el-icon class="nav-icon"><Setting /></el-icon>
            <span class="nav-text">设置</span>
          </router-link>
          <div class="status" :class="statusClass">
            <span class="status-dot"></span>
            <span class="status-text">Status: {{ statusText }}</span>
          </div>
          <div class="relogin-section">
            <el-button
              type="warning"
              size="small"
              :loading="isRelogging"
              @click="handleRelogin"
              :disabled="!hasLoginInfo"
              style="width: 100%"
            >
              <el-icon v-if="!isRelogging"><Refresh /></el-icon>
              {{ isRelogging ? '重新登录中...' : '强制重新登录' }}
            </el-button>
          </div>
        </nav>
        <main class="main-view">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg,
      rgba(236, 246, 255, 0.7) 0%,
      rgba(230, 245, 255, 0.7) 20%,
      rgba(225, 240, 255, 0.7) 40%,
      rgba(220, 238, 255, 0.7) 60%,
      rgba(208, 235, 255, 0.7) 80%,
      rgba(200, 232, 255, 0.7) 100%);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
}

.titlebar {
  height: 36px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  padding: 0 16px;
  -webkit-app-region: drag;
  user-select: none;
  border-bottom: 1px solid rgba(200, 215, 235, 0.2);
  position: relative;
}

.titlebar::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 36px;
  background: linear-gradient(90deg,
      rgba(147, 197, 253, 0.05) 0%,
      rgba(186, 230, 253, 0.05) 50%,
      rgba(147, 197, 253, 0.05) 100%);
  pointer-events: none;
}

.title {
  position: relative;
  color: #1e40af;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.3px;
  opacity: 0.85;
  padding: 4px 0;
  background: linear-gradient(90deg, #1e40af, #3b82f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: none;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.main-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.sidebar {
  width: 200px;
  min-width: 200px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  border-right: 1px solid rgba(200, 215, 235, 0.3);
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  color: #64748b;
  text-decoration: none;
  transition: all 0.2s ease;
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.15);
  color: #1e40af;
  border-left-color: #3b82f6;
  font-weight: 600;
}

.nav-icon {
  font-size: 18px;
}

.nav-text {
  font-size: 14px;
}

.main-view {
  flex: 1;
  min-width: 0;
  overflow: auto;
  background: transparent;
  height: 100%;
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: 20px;
}

.login-card {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  padding: 40px 32px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 8px 0;
}

.login-subtitle {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #334155;
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.9);
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: rgba(255, 255, 255, 1);
}

.form-input::placeholder {
  color: #94a3b8;
}

.error-message {
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #dc2626;
  font-size: 13px;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #3b82f6, #1e40af);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  margin-top: 8px;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.title-controls {
  margin-left: auto;
  display: flex;
  gap: 6px;
  -webkit-app-region: no-drag;
  /* 使控件可点击 */
}

.control-btn {
  background: transparent;
  border: none;
  width: 34px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #0f172a;
  /* neutral dark */
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 120ms ease, color 120ms ease;
}

.control-btn:hover {
  background: rgba(15, 23, 42, 0.06);
}

.control-btn svg {
  display: block;
}

.control-btn.close {
  color: #374151;
  /* neutral gray */
}

.control-btn.close:hover {
  background: rgba(55, 65, 81, 0.06);
}

.status {
  margin-top: auto;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  border-top: 1px solid rgba(200, 215, 235, 0.3);
}

.relogin-section {
  padding: 12px 20px;
  border-top: 1px solid rgba(200, 215, 235, 0.3);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.status-text {
  font-weight: 500;
}

.status-connected .status-dot {
  background-color: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status-connected .status-text {
  color: #22c55e;
}

.status-disconnected .status-dot {
  background-color: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
}

.status-disconnected .status-text {
  color: #ef4444;
}

.status-reconnecting .status-dot {
  background-color: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-reconnecting .status-text {
  color: #f59e0b;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

</style>

<style>
/* 暗色模式全局样式 - 纯黑色系 */
.dark-theme .app-container {
  background: linear-gradient(135deg,
      #000000 0%,
      #0a0a0a 20%,
      #111111 40%,
      #0a0a0a 60%,
      #000000 80%,
      #000000 100%);
  border: 1px solid #1a1a1a;
}

.dark-theme .titlebar {
  background: #0a0a0a;
  border-bottom: 1px solid #1a1a1a;
}

.dark-theme .titlebar::after {
  background: linear-gradient(90deg,
      rgba(255, 255, 255, 0.05) 0%,
      rgba(255, 255, 255, 0.08) 50%,
      rgba(255, 255, 255, 0.05) 100%);
}

.dark-theme .title {
  background: linear-gradient(90deg, #ffffff, #e0e0e0);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.dark-theme .sidebar {
  background: #0a0a0a;
  border-right: 1px solid #1a1a1a;
}

.dark-theme .nav-item {
  color: #d0d0d0 !important;
}

.dark-theme .nav-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff !important;
}

.dark-theme .nav-item.active {
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff !important;
  border-left-color: #ffffff;
}

.dark-theme .control-btn {
  color: #e0e0e0 !important;
}

.dark-theme .control-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.dark-theme .control-btn.close:hover {
  background: rgba(239, 68, 68, 0.3);
}

.dark-theme .status {
  border-top: 1px solid #1a1a1a;
  color: #d0d0d0 !important;
}

.dark-theme .relogin-section {
  border-top: 1px solid #1a1a1a;
}

.dark-theme .login-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .login-subtitle {
  color: #a0a0a0 !important;
}

.dark-theme .form-label {
  color: #e0e0e0 !important;
}

.dark-theme .form-input {
  background: #0f0f0f;
  border: 1px solid #2a2a2a;
  color: #e0e0e0 !important;
}

.dark-theme .form-input:focus {
  border-color: #ffffff;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1);
  background: #1a1a1a;
}

.dark-theme .form-input::placeholder {
  color: #666666 !important;
}

/* Element Plus 暗色模式适配 - 纯黑色系 */
.dark-theme {
  --el-bg-color: #1a1a1a;
  --el-bg-color-page: #000000;
  --el-text-color-primary: #e0e0e0;
  --el-text-color-regular: #d0d0d0;
  --el-text-color-secondary: #a0a0a0;
  --el-text-color-placeholder: #666666;
  --el-border-color: #2a2a2a;
  --el-border-color-light: #1a1a1a;
  --el-border-color-lighter: #0f0f0f;
  --el-border-color-extra-light: #0a0a0a;
  --el-fill-color: #1a1a1a;
  --el-fill-color-light: #0f0f0f;
  --el-fill-color-lighter: #0a0a0a;
  --el-fill-color-extra-light: #050505;
  --el-fill-color-dark: #2a2a2a;
  --el-fill-color-darker: #3a3a3a;
  --el-fill-color-blank: transparent;
  --el-mask-color: rgba(0, 0, 0, 0.8);
  --el-mask-color-extra-light: rgba(0, 0, 0, 0.3);
}

.dark-theme .el-card {
  background-color: #1a1a1a !important;
  border-color: #2a2a2a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-table {
  background-color: #1a1a1a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-table th {
  background-color: #0f0f0f !important;
  color: #d0d0d0 !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-table td {
  background-color: #1a1a1a !important;
  color: #e0e0e0 !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-table--striped .el-table__body tr.el-table__row--striped td {
  background-color: #0f0f0f !important;
}

.dark-theme .el-table tr:hover > td {
  background-color: #2a2a2a !important;
}

.dark-theme .el-input__wrapper {
  background-color: #0f0f0f !important;
  box-shadow: 0 0 0 1px #2a2a2a inset !important;
}

.dark-theme .el-input__inner {
  background-color: transparent !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-input__inner::placeholder {
  color: #666666 !important;
}

.dark-theme .el-input.is-focus .el-input__wrapper {
  box-shadow: 0 0 0 1px #ffffff inset !important;
}

.dark-theme .el-textarea__inner {
  background-color: #0f0f0f !important;
  border-color: #2a2a2a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-textarea__inner:focus {
  border-color: #ffffff !important;
}

.dark-theme .el-tabs__header {
  background-color: #1a1a1a !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-tabs__item {
  color: #a0a0a0 !important;
}

.dark-theme .el-tabs__item:hover {
  color: #d0d0d0 !important;
}

.dark-theme .el-tabs__item.is-active {
  color: #ffffff !important;
}

.dark-theme .el-tabs__active-bar {
  background-color: #ffffff !important;
}

.dark-theme .el-tabs__nav-wrap::after {
  background-color: #2a2a2a !important;
}

.dark-theme .el-button {
  color: #e0e0e0 !important;
  background-color: #1a1a1a !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-button:hover {
  background-color: #2a2a2a !important;
  border-color: #3a3a3a !important;
}

.dark-theme .el-button--primary {
  background-color: #ffffff !important;
  border-color: #ffffff !important;
  color: #000000 !important;
}

.dark-theme .el-button--primary:hover {
  background-color: #e0e0e0 !important;
  border-color: #e0e0e0 !important;
}

.dark-theme .el-button--danger {
  background-color: #dc2626 !important;
  border-color: #dc2626 !important;
  color: #ffffff !important;
}

.dark-theme .el-button--danger:hover {
  background-color: #b91c1c !important;
  border-color: #b91c1c !important;
}

.dark-theme .el-button--warning {
  background-color: #f59e0b !important;
  border-color: #f59e0b !important;
  color: #000000 !important;
}

.dark-theme .el-button--info {
  background-color: #1a1a1a !important;
  border-color: #2a2a2a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-button--text {
  color: #e0e0e0 !important;
}

.dark-theme .el-button--text:hover {
  background-color: rgba(255, 255, 255, 0.1) !important;
}

.dark-theme .el-tag {
  background-color: #2a2a2a !important;
  border-color: #3a3a3a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-tag--success {
  background-color: #22c55e !important;
  border-color: #22c55e !important;
  color: #000000 !important;
}

.dark-theme .el-tag--danger {
  background-color: #dc2626 !important;
  border-color: #dc2626 !important;
  color: #ffffff !important;
}

.dark-theme .el-tag--warning {
  background-color: #f59e0b !important;
  border-color: #f59e0b !important;
  color: #000000 !important;
}

.dark-theme .el-tag--info {
  background-color: #3a3a3a !important;
  border-color: #4a4a4a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-empty {
  color: #a0a0a0 !important;
}

.dark-theme .el-empty__description {
  color: #a0a0a0 !important;
}

.dark-theme .el-divider {
  border-color: #2a2a2a !important;
}

.dark-theme .el-divider__text {
  background-color: #1a1a1a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-switch__core {
  background-color: #2a2a2a !important;
}

.dark-theme .el-switch.is-checked .el-switch__core {
  background-color: #ffffff !important;
}

.dark-theme .el-form-item__label {
  color: #e0e0e0 !important;
}

.dark-theme .el-select {
  --el-select-input-color: #e0e0e0;
  --el-select-multiple-input-color: #e0e0e0;
  --el-select-input-focus-border-color: #ffffff;
}

.dark-theme .el-select .el-input__wrapper {
  background-color: #0f0f0f !important;
  box-shadow: 0 0 0 1px #2a2a2a inset !important;
}

.dark-theme .el-select .el-input.is-focus .el-input__wrapper {
  box-shadow: 0 0 0 1px #ffffff inset !important;
}

.dark-theme .el-select-dropdown {
  background-color: #1a1a1a !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-select-dropdown__item {
  color: #e0e0e0 !important;
}

.dark-theme .el-select-dropdown__item:hover {
  background-color: #2a2a2a !important;
}

.dark-theme .el-select-dropdown__item.selected {
  background-color: #3a3a3a !important;
  color: #ffffff !important;
}

.dark-theme .el-dialog {
  background-color: #1a1a1a !important;
  border: 1px solid #2a2a2a !important;
}

.dark-theme .el-dialog__header {
  border-bottom: 1px solid #2a2a2a !important;
}

.dark-theme .el-dialog__title {
  color: #e0e0e0 !important;
}

.dark-theme .el-dialog__body {
  color: #e0e0e0 !important;
}

.dark-theme .el-message-box {
  background-color: #1a1a1a !important;
  border: 1px solid #2a2a2a !important;
}

.dark-theme .el-message-box__title {
  color: #e0e0e0 !important;
}

.dark-theme .el-message-box__message {
  color: #d0d0d0 !important;
}

.dark-theme .el-loading-mask {
  background-color: rgba(0, 0, 0, 0.8) !important;
}

.dark-theme .el-pagination {
  color: #e0e0e0 !important;
}

.dark-theme .el-pagination button {
  background-color: #1a1a1a !important;
  color: #e0e0e0 !important;
  border-color: #2a2a2a !important;
}

.dark-theme .el-pagination button:hover {
  background-color: #2a2a2a !important;
}

.dark-theme .el-pagination .el-pager li {
  background-color: #1a1a1a !important;
  color: #e0e0e0 !important;
}

.dark-theme .el-pagination .el-pager li.is-active {
  background-color: #ffffff !important;
  color: #000000 !important;
}
</style>