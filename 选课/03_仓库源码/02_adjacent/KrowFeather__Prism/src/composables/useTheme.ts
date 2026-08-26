import { ref } from 'vue'

const THEME_KEY = 'theme'
const DARK_THEME_CLASS = 'dark-theme'

const isDarkMode = ref<boolean>(false)

// 初始化主题
export function initTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'dark') {
    isDarkMode.value = true
    document.documentElement.classList.add(DARK_THEME_CLASS)
    document.body.classList.add(DARK_THEME_CLASS)
    // 设置 Element Plus 暗色模式
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    isDarkMode.value = false
    document.documentElement.classList.remove(DARK_THEME_CLASS)
    document.body.classList.remove(DARK_THEME_CLASS)
    document.documentElement.removeAttribute('data-theme')
  }
}

// 切换主题
export function toggleTheme() {
  isDarkMode.value = !isDarkMode.value
  if (isDarkMode.value) {
    document.documentElement.classList.add(DARK_THEME_CLASS)
    document.body.classList.add(DARK_THEME_CLASS)
    document.documentElement.setAttribute('data-theme', 'dark')
    localStorage.setItem(THEME_KEY, 'dark')
  } else {
    document.documentElement.classList.remove(DARK_THEME_CLASS)
    document.body.classList.remove(DARK_THEME_CLASS)
    document.documentElement.removeAttribute('data-theme')
    localStorage.setItem(THEME_KEY, 'light')
  }
}

// 设置主题
export function setTheme(dark: boolean) {
  isDarkMode.value = dark
  if (dark) {
    document.documentElement.classList.add(DARK_THEME_CLASS)
    document.body.classList.add(DARK_THEME_CLASS)
    document.documentElement.setAttribute('data-theme', 'dark')
    localStorage.setItem(THEME_KEY, 'dark')
  } else {
    document.documentElement.classList.remove(DARK_THEME_CLASS)
    document.body.classList.remove(DARK_THEME_CLASS)
    document.documentElement.removeAttribute('data-theme')
    localStorage.setItem(THEME_KEY, 'light')
  }
}

export { isDarkMode }

