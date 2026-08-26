<template>
  <div class="login-container">
    <div class="login-wrapper">
      <!-- 已保存的账户卡片 -->
      <div v-if="savedAccounts.length > 0" class="accounts-section">
        <div class="section-header">
          <h2 class="section-title">已保存的账户</h2>
          <p class="section-subtitle">点击账户卡片快速登录</p>
        </div>
        <div class="accounts-grid">
          <div
            v-for="account in savedAccounts"
            :key="account.username"
            class="account-card"
            @click="handleQuickLogin(account)"
            :class="{ 
              'logging-in': quickLoginUsername === account.username && isLoggingIn,
              'disabled': isLoggingIn && quickLoginUsername !== account.username
            }"
          >
            <div class="account-card-content">
              <div class="account-info">
                <div class="account-avatar">{{ account.username.charAt(account.username.length - 1) }}</div>
                <div class="account-details">
                  <div class="account-username">{{ account.username }}</div>
                  <div class="account-time">{{ formatTime(account.savedAt) }}</div>
                </div>
              </div>
              <el-button
                type="danger"
                size="small"
                text
                @click.stop="handleRemoveAccount(account.username)"
                class="delete-btn"
                :disabled="isLoggingIn"
              >
                删除
              </el-button>
            </div>
            <div v-if="quickLoginUsername === account.username && isLoggingIn" class="loading-overlay">
              <div class="loading-spinner"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 登录表单 -->
      <el-card class="login-card" shadow="hover">
        <template #header>
          <div class="login-header">
            <h1 class="login-title">{{ savedAccounts.length > 0 ? '添加新账户' : '账户选择' }}</h1>
            <p class="login-subtitle">请输入您的学号和密码</p>
          </div>
        </template>
        <el-form @submit.prevent="handleLogin" class="login-form">
          <el-form-item label="学号">
            <el-input
              v-model="studentId"
              placeholder="请输入学号"
              :disabled="isLoggingIn"
              clearable
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="password"
              type="password"
              placeholder="请输入密码"
              :disabled="isLoggingIn"
              show-password
              size="large"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-alert
            v-if="errorMessage"
            :title="errorMessage"
            type="error"
            :closable="false"
            show-icon
          />
          <el-form-item>
            <el-button
              type="primary"
              :loading="isLoggingIn"
              @click="handleLogin"
              size="large"
              style="width: 100%"
            >
              {{ isLoggingIn ? '登录中...' : '登录' }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- 批次选择对话框 -->
    <el-dialog
      v-model="showBatchDialog"
      title="请选择选课批次（必选）"
      width="400px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-select
        v-model="selectedBatchCode"
        placeholder="请选择选课批次"
        style="width: 100%"
        filterable
        :loading="isLoadingBatches"
      >
        <el-option
          v-for="batch in batches"
          :key="batch.electiveBatchCode"
          :label="batch.electiveBatchName || batch.electiveBatchCode"
          :value="batch.electiveBatchCode"
        />
      </el-select>
      <template #footer>
        <el-button type="primary" @click="confirmBatchSelection" :loading="isLoadingBatches">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
// 注意：如果项目中没有安装 @element-plus/icons-vue，可以移除图标
// import { Delete, Loading } from '@element-plus/icons-vue'
import { connectionStatus } from '../composables/useConnectionStatus'
import { savedAccounts, saveAccount, removeAccount, initAccounts } from '../composables/useAccounts'

const router = useRouter()

// 从 localStorage 获取 API 地址，默认为 5000
const getApiUrl = () => {
  return localStorage.getItem('apiUrl') || 'http://localhost:5000'
}

const studentId = ref('')
const password = ref('')
const isLoggingIn = ref(false)
const errorMessage = ref('')
const batches = ref<any[]>([])
const isLoadingBatches = ref(false)
const showBatchDialog = ref(false)
const selectedBatchCode = ref('')
const loginSuccessInfo = ref<any>(null) // 保存登录成功的信息，等待批次选择后再跳转
const quickLoginUsername = ref('') // 当前快速登录的用户名

// 执行登录逻辑（提取公共部分）
async function performLogin(username: string, pwd: string) {
  isLoggingIn.value = true
  errorMessage.value = ''
  
  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/login`, {
      username: username,
      password: pwd
    })
    
    if (response.data.success) {
      // 保存账户信息
      saveAccount(username, pwd)
      
      // 保存登录成功的信息
      loginSuccessInfo.value = {
        username: username,
        password: pwd,
        token: response.data.token,
        WEU: response.data.WEU,
        JSESSIONID: response.data.JSESSIONID
      }
      
      // 更新连接状态
      connectionStatus.value = 'connected'
      
      errorMessage.value = ''
      
      // 加载批次列表并显示选择对话框
      await loadBatches()
    } else {
      errorMessage.value = response.data.message || '登录失败，请检查学号和密码'
      ElMessage.error(errorMessage.value)
    }
  } catch (error: any) {
    if (error.response) {
      errorMessage.value = error.response.data?.message || error.response.data?.detail || '登录失败，请重试'
    } else if (error.request) {
      errorMessage.value = '无法连接到服务器，请确保服务正在运行'
    } else {
      errorMessage.value = error.message || '登录失败，请重试'
    }
    ElMessage.error(errorMessage.value)
  } finally {
    isLoggingIn.value = false
    quickLoginUsername.value = ''
  }
}

// 表单登录
async function handleLogin() {
  if (!studentId.value.trim()) {
    errorMessage.value = '请输入学号'
    return
  }
  if (!password.value.trim()) {
    errorMessage.value = '请输入密码'
    return
  }
  
  await performLogin(studentId.value, password.value)
}

// 快速登录（点击账户卡片）
async function handleQuickLogin(account: { username: string; password: string }) {
  if (isLoggingIn.value) return
  
  studentId.value = account.username
  password.value = account.password
  quickLoginUsername.value = account.username
  
  // 调用登录逻辑
  await performLogin(account.username, account.password)
}

// 加载批次列表
async function loadBatches() {
  if (!loginSuccessInfo.value) return

  if (isLoadingBatches.value) return
  isLoadingBatches.value = true

  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/get-batches`, {
      username: loginSuccessInfo.value.username,
      password: loginSuccessInfo.value.password
    })

    if (response.data.success) {
      batches.value = response.data.data.map((item: any) => ({
        electiveBatchName: item.name,
        electiveBatchCode: item.code,
        displayFields: item  // 保存完整的批次信息，包含 display* 字段
      }))

      if (batches.value.length === 0) {
        ElMessage.warning('暂无可用批次')
        // 即使没有批次，也保存登录信息并跳转
        localStorage.setItem('loginInfo', JSON.stringify(loginSuccessInfo.value))
        router.push('/select-class')
      } else {
        // 打开批次选择对话框
        showBatchDialog.value = true
      }
    } else {
      ElMessage.error(response.data.message || '获取批次列表失败')
      // 获取批次失败，仍保存登录信息并跳转
      localStorage.setItem('loginInfo', JSON.stringify(loginSuccessInfo.value))
      router.push('/select-class')
    }
  } catch (error: any) {
    if (error.response) {
      ElMessage.error(error.response.data?.message || '获取批次列表失败')
    } else if (error.request) {
      ElMessage.error('无法连接到服务器，请确保服务正在运行')
    } else {
      ElMessage.error(error.message || '获取批次列表失败')
    }
    // 出错时也保存登录信息并跳转
    if (loginSuccessInfo.value) {
      localStorage.setItem('loginInfo', JSON.stringify(loginSuccessInfo.value))
      router.push('/select-class')
    }
  } finally {
    isLoadingBatches.value = false
  }
}

// 确认批次选择
async function confirmBatchSelection() {
  if (!selectedBatchCode.value) {
    ElMessage.warning('请选择批次')
    return
  }
  
  if (!loginSuccessInfo.value) {
    ElMessage.error('登录信息丢失，请重新登录')
    return
  }
  
  // 保存登录信息
  localStorage.setItem('loginInfo', JSON.stringify(loginSuccessInfo.value))
  
  // 保存批次代码
  localStorage.setItem('selectedBatchCode', selectedBatchCode.value)
  
  // 提取并保存 display 字段信息
  const selectedBatch = batches.value.find(b => b.electiveBatchCode === selectedBatchCode.value)
  if (selectedBatch && selectedBatch.displayFields) {
    const displayFields = selectedBatch.displayFields
    const enabledTabs: string[] = []
    
    // 提取所有 display* 字段，值为 "1" 的
    const tabMapping: Record<string, string> = {
      'BYKC': 'BYKC',
      'TJKC': 'TJKC',
      'FANKC': 'FANKC',
      'FAWKC': 'FAWKC',
      'CXKC': 'CXKC',
      'TYKC': 'TYKC',
      'XGXK': 'XGXK'
    }
    
    for (const [key, value] of Object.entries(tabMapping)) {
      const displayKey = `display${key}`
      if (displayFields[displayKey] === '1' || displayFields[displayKey] === 1) {
        enabledTabs.push(value)
      }
    }
    
    // 保存启用的 Tab 列表
    localStorage.setItem('enabledTabs', JSON.stringify(enabledTabs))
  }
  
  // 获取系统参数（课程类型名称）
  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/get-sys-params`, {
      username: loginSuccessInfo.value.username,
      password: loginSuccessInfo.value.password
    })
    
    if (response.data.success && response.data.data) {
      // 保存课程类型名称映射
      localStorage.setItem('tabNames', JSON.stringify(response.data.data))
    }
  } catch (error) {
    console.error('获取系统参数失败:', error)
    // 即使获取失败也继续，使用默认名称
  }
  
  showBatchDialog.value = false
  ElMessage.success('批次选择成功')
  
  // 跳转到主页面
  router.push('/select-class')
}

// 删除账户
async function handleRemoveAccount(username: string) {
  try {
    await ElMessageBox.confirm(`确定要删除账户 ${username} 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    removeAccount(username)
    ElMessage.success('账户已删除')
  } catch {
    // 用户取消
  }
}

// 格式化时间
function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) {
    return '今天'
  } else if (days === 1) {
    return '昨天'
  } else if (days < 7) {
    return `${days}天前`
  } else {
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
  }
}

// 页面加载时初始化账户列表
onMounted(() => {
  initAccounts()
})
</script>

<style scoped>
.login-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  min-height: 100vh;
  box-sizing: border-box;
}

.login-wrapper {
  width: 100%;
  max-width: 1200px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  align-items: center;
}

/* 账户卡片区域 */
.accounts-section {
  width: 100%;
  max-width: 900px;
}

.section-header {
  text-align: center;
  margin-bottom: 24px;
}

.section-title {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 8px 0;
}

.section-subtitle {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.accounts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}

.account-card {
  position: relative;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.account-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #3b82f6, #1e40af);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.account-card:hover::before {
  transform: scaleX(1);
}

.account-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}

.account-card.logging-in {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.account-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.account-card.disabled:hover {
  transform: none;
}

.account-card-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  z-index: 1;
}

.account-info {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
}

.account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1e40af);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.account-details {
  flex: 1;
  min-width: 0;
}

.account-username {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-time {
  font-size: 13px;
  color: #94a3b8;
}

.delete-btn {
  opacity: 0;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.account-card:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444 !important;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 登录表单卡片 */
.login-card {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(12px);
  border-radius: 20px;
  border: 1px solid rgba(59, 130, 246, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.login-header {
  text-align: center;
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
  margin-top: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-container {
    padding: 20px 16px;
  }

  .accounts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .login-wrapper {
    gap: 24px;
  }

  .section-title {
    font-size: 20px;
  }
}

</style>

<style>
/* 暗色模式样式 - 纯黑色系 */
.dark-theme .account-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .account-card:hover {
  border-color: #3a3a3a;
  box-shadow: 0 8px 24px rgba(255, 255, 255, 0.1);
}

.dark-theme .account-username {
  color: #e0e0e0 !important;
}

.dark-theme .account-time {
  color: #a0a0a0 !important;
}

.dark-theme .login-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .section-title {
  color: #e0e0e0 !important;
}

.dark-theme .empty-text {
  color: #d0d0d0 !important;
}

.dark-theme .empty-subtext {
  color: #a0a0a0 !important;
}
</style>

