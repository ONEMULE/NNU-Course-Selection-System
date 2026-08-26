<template>
  <div class="settings-page">
    <h2 class="page-title">设置</h2>
    <div class="page-content">
      <el-card class="settings-card" shadow="hover">
        <el-divider content-position="left">
          <h3 class="section-title">账户信息</h3>
        </el-divider>
        <div class="info-item">
          <span class="info-label">学号：</span>
          <el-tag type="info">{{ loginInfo?.username || '未登录' }}</el-tag>
        </div>

        <el-divider content-position="left">
          <h3 class="section-title">服务器配置</h3>
        </el-divider>
        <el-form>
          <el-form-item label="API 地址">
            <el-input
              v-model="apiUrl"
              placeholder="http://localhost:5000"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveSettings">保存设置</el-button>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">
          <h3 class="section-title">邮件提醒</h3>
        </el-divider>
        <el-form>
          <el-form-item label="启用邮件提醒">
            <el-switch
              v-model="emailEnabled"
              active-text="开启"
              inactive-text="关闭"
            />
          </el-form-item>
          <el-form-item v-if="emailEnabled" label="发件邮箱">
            <el-input
              v-model="emailUser"
              placeholder="your-email@example.com"
              clearable
            />
          </el-form-item>
          <el-form-item v-if="emailEnabled" label="邮箱授权码">
            <el-input
              v-model="emailAuth"
              type="password"
              placeholder="请输入邮箱授权码"
              show-password
              clearable
            />
          </el-form-item>
          <el-form-item v-if="emailEnabled">
            <el-button type="primary" @click="saveEmailSettings">保存邮件设置</el-button>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">
          <h3 class="section-title">外观设置</h3>
        </el-divider>
        <el-form>
          <el-form-item label="暗色模式">
            <el-switch
              v-model="isDarkMode"
              @change="handleThemeChange"
              active-text="开启"
              inactive-text="关闭"
            />
          </el-form-item>
        </el-form>

        <el-divider content-position="left">
          <h3 class="section-title">关于</h3>
        </el-divider>
        <div class="about-section">
          <div class="about-item">
            <span class="about-label">应用名称：</span>
            <span class="about-value">Prism</span>
          </div>
          <div class="about-item">
            <span class="about-label">版本：</span>
            <span class="about-value">1.0.0b</span>
          </div>
          <div class="about-item">
            <span class="about-label">作者：</span>
            <span class="about-value">KrowFeather</span>
          </div>
          <div class="about-item">
            <span class="about-label">描述：</span>
            <span class="about-value">YNU智能选课抢课助手</span>
          </div>
        </div>

        <el-divider content-position="left">
          <h3 class="section-title">操作</h3>
        </el-divider>
        <el-button type="danger" @click="handleLogout">退出登录</el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { connectionStatus } from '../composables/useConnectionStatus'
import { isDarkMode, setTheme } from '../composables/useTheme'

const router = useRouter()
const loginInfo = ref<any>(null)
const apiUrl = ref('http://localhost:5000')
const emailEnabled = ref(false)
const emailUser = ref('')
const emailAuth = ref('')

onMounted(() => {
  const stored = localStorage.getItem('loginInfo')
  if (stored) {
    loginInfo.value = JSON.parse(stored)
  }
  
  const storedApiUrl = localStorage.getItem('apiUrl')
  if (storedApiUrl) {
    apiUrl.value = storedApiUrl
  }
  
  // 加载邮件设置
  const storedEmailEnabled = localStorage.getItem('emailEnabled')
  if (storedEmailEnabled !== null) {
    emailEnabled.value = storedEmailEnabled === 'true'
  }
  
  const storedEmailUser = localStorage.getItem('emailUser')
  if (storedEmailUser) {
    emailUser.value = storedEmailUser
  }
  
  const storedEmailAuth = localStorage.getItem('emailAuth')
  if (storedEmailAuth) {
    emailAuth.value = storedEmailAuth
  }
  
  // 初始化暗色模式状态（从 useTheme 中读取）
  // isDarkMode 是响应式的，会自动同步
})

function saveSettings() {
  localStorage.setItem('apiUrl', apiUrl.value)
  // 同时保存邮件设置
  saveEmailSettings()
}

function saveEmailSettings() {
  localStorage.setItem('emailEnabled', String(emailEnabled.value))
  localStorage.setItem('emailUser', emailUser.value)
  localStorage.setItem('emailAuth', emailAuth.value)
  ElMessage.success('邮件设置已保存')
}

function handleThemeChange(value: boolean) {
  setTheme(value)
  ElMessage.success(value ? '已切换到暗色模式' : '已切换到亮色模式')
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    localStorage.removeItem('loginInfo')
    connectionStatus.value = 'disconnected'
    ElMessage.success('已退出登录')
    router.push('/')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.settings-page {
  padding: 20px;
  min-height: 100%;
  box-sizing: border-box;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 24px 0;
}

.page-content {
  max-width: 600px;
  margin: 0 auto;
}

.settings-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e40af;
  margin: 0;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
}

.info-label {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

.about-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 0;
}

.about-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.about-label {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
  min-width: 80px;
}

.about-value {
  font-size: 14px;
  color: #1e293b;
  font-weight: 400;
}

</style>

<style>
/* 暗色模式样式 - 纯黑色系 */
.dark-theme .page-title {
  background: linear-gradient(135deg, #ffffff, #e0e0e0);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.dark-theme .settings-card {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .section-title {
  color: #e0e0e0 !important;
}

.dark-theme .info-label {
  color: #d0d0d0 !important;
}

.dark-theme .about-label {
  color: #d0d0d0 !important;
}

.dark-theme .about-value {
  color: #e0e0e0 !important;
}
</style>

