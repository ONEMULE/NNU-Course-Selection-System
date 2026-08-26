import { ref, watch } from 'vue'

export interface SavedAccount {
  username: string
  password: string
  savedAt: number // 保存时间戳
}

const STORAGE_KEY = 'savedAccounts'

// 从 localStorage 加载账户列表
function loadAccounts(): SavedAccount[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch (error) {
    console.error('Failed to load accounts:', error)
    return []
  }
}

// 保存账户列表到 localStorage
function saveAccounts(accounts: SavedAccount[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(accounts))
  } catch (error) {
    console.error('Failed to save accounts:', error)
  }
}

// 响应式账户列表
export const savedAccounts = ref<SavedAccount[]>(loadAccounts())

// 监听变化并保存
watch(savedAccounts, (newAccounts) => {
  saveAccounts(newAccounts)
}, { deep: true })

// 添加或更新账户
export function saveAccount(username: string, password: string) {
  // 检查是否已存在
  const existingIndex = savedAccounts.value.findIndex(
    account => account.username === username
  )
  
  const account: SavedAccount = {
    username,
    password,
    savedAt: Date.now()
  }
  
  if (existingIndex > -1) {
    // 更新现有账户
    savedAccounts.value[existingIndex] = account
  } else {
    // 添加新账户
    savedAccounts.value.push(account)
  }
}

// 删除账户
export function removeAccount(username: string) {
  const index = savedAccounts.value.findIndex(
    account => account.username === username
  )
  if (index > -1) {
    savedAccounts.value.splice(index, 1)
    return true
  }
  return false
}

// 获取账户
export function getAccount(username: string): SavedAccount | undefined {
  return savedAccounts.value.find(account => account.username === username)
}

// 初始化
export function initAccounts() {
  savedAccounts.value = loadAccounts()
}

