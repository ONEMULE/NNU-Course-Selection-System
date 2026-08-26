import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

export interface QueuedCourse {
  id: string // 唯一ID，使用 teachingClassId + timestamp
  teachingClassId: string
  courseName: string
  teacherName: string
  electiveBatchCode: string
  teachingClassType: string
  campus: string
  isMajor: string
  teachingPlace?: string
  capacity?: string
  selectedCount?: string
  addedAt: number // 添加时间戳
}

const STORAGE_KEY = 'courseQueue'

// 从 localStorage 加载抢课列表
function loadQueue(): QueuedCourse[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch (error) {
    console.error('Failed to load course queue:', error)
    return []
  }
}

// 保存抢课列表到 localStorage
function saveQueue(queue: QueuedCourse[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue))
  } catch (error) {
    console.error('Failed to save course queue:', error)
  }
}

// 响应式抢课列表
export const courseQueue = ref<QueuedCourse[]>(loadQueue())

// 监听变化并保存
watch(courseQueue, (newQueue) => {
  saveQueue(newQueue)
}, { deep: true })

// 添加课程到抢课列表
export function addToQueue(course: Omit<QueuedCourse, 'id' | 'addedAt'>): boolean {
  // 检查是否已存在
  const exists = courseQueue.value.find(
    item => item.teachingClassId === course.teachingClassId &&
            item.electiveBatchCode === course.electiveBatchCode
  )
  
  if (exists) {
    ElMessage.warning('该课程已在抢课列表中')
    return false
  }

  const queuedCourse: QueuedCourse = {
    ...course,
    id: `${course.teachingClassId}_${Date.now()}`,
    addedAt: Date.now()
  }
  
  courseQueue.value.push(queuedCourse)
  ElMessage.success('已添加到抢课列表')
  return true
}

// 从抢课列表移除
export function removeFromQueue(id: string) {
  const index = courseQueue.value.findIndex(item => item.id === id)
  if (index > -1) {
    courseQueue.value.splice(index, 1)
    ElMessage.success('已从抢课列表移除')
    return true
  }
  return false
}

// 清空抢课列表
export function clearQueue() {
  courseQueue.value = []
  ElMessage.success('抢课列表已清空')
}

// 获取抢课列表
export function getQueue(): QueuedCourse[] {
  return courseQueue.value
}

// 初始化：从 localStorage 加载
export function initQueue() {
  courseQueue.value = loadQueue()
}

