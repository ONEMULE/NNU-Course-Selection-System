import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import { setupAxiosInterceptors, initConnectionStatus } from './composables/useConnectionStatus'
import { initTheme } from './composables/useTheme'

// 初始化主题（必须在应用创建之前）
initTheme()

// 设置 axios 拦截器
setupAxiosInterceptors()
// 初始化连接状态
initConnectionStatus()

const app = createApp(App)

app.use(router)
app.use(ElementPlus)
app.mount('#app')
