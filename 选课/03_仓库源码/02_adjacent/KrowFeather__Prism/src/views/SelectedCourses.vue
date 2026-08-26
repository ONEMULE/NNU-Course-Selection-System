<template>
  <div class="selected-courses-page">
    <div class="page-header">
      <h2 class="page-title">已选课程</h2>
      <el-button
        type="primary"
        :icon="Refresh"
        @click="loadSelectedCourses"
        :loading="isLoading"
        circle
        title="刷新已选课程列表"
      />
    </div>
    
    <div class="page-content">
      <el-tabs v-model="activeTab" class="course-tabs">
        <!-- 已选课程列表 Tab -->
        <el-tab-pane label="已选课程" name="courses">
          <div class="tab-content">
            <!-- 空状态 -->
            <el-empty
              v-if="!isLoading && selectedCourses.length === 0"
              description="暂无已选课程"
            />
            
            <!-- 已选课程列表 -->
            <el-table
              v-else
              :data="selectedCourses"
              stripe
              style="width: 100%"
              v-loading="isLoading"
            >
        <el-table-column prop="courseName" label="课程名称" width="180" />
        <el-table-column prop="teacherName" label="教师" width="120" />
        <el-table-column prop="teachingClassID" label="教学班ID" width="250" />
        <el-table-column prop="credit" label="学分" width="80" />
        <el-table-column prop="teachingPlace" label="上课时间" show-overflow-tooltip min-width="150"/>
        <el-table-column label="课程类型" width="140">
          <template #default="scope">
            <el-tag size="small">
              {{ getCourseTypeName(scope.row.courseTypeName) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button
              type="danger"
              size="small"
              @click="handleDropCourse(scope.row)"
              :loading="droppingCourseId === scope.row.teachingClassID"
            >
              退课
            </el-button>
          </template>
        </el-table-column>
      </el-table>
          </div>
        </el-tab-pane>
        
        <!-- 课程表 Tab -->
        <el-tab-pane label="课程表" name="schedule">
          <div class="tab-content schedule-tab-content">
            <div v-if="Object.keys(scheduleData).length === 0" class="schedule-empty">
              <p>暂无课程安排</p>
            </div>
            <div v-else class="schedule-table">
            <table class="schedule-grid">
              <thead>
                <tr>
                  <th class="time-col">节次</th>
                  <th v-for="day in weekDays" :key="day" class="day-col">{{ day }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="timeSlot in timeSlots" :key="timeSlot.time">
                  <td class="time-cell">{{ timeSlot.time }}节</td>
                  <td
                    v-for="day in weekDays"
                    :key="day"
                    class="course-cell"
                    :class="{ 'has-course': getCourseAtTimeSlot(day, timeSlot.time) !== null }"
                  >
                    <div
                      v-if="getCourseAtTimeSlot(day, timeSlot.time)"
                      class="course-item"
                      :style="{ backgroundColor: getCourseColor(getCourseAtTimeSlot(day, timeSlot.time)) }"
                    >
                      <div class="course-name">{{ getCourseAtTimeSlot(day, timeSlot.time)?.courseName }}</div>
                      <div class="course-place">{{ getCourseAtTimeSlot(day, timeSlot.time)?.teachingPlace }}</div>
                      <div class="course-teacher">{{ getCourseAtTimeSlot(day, timeSlot.time)?.teacherName }}</div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const router = useRouter()

// 从 localStorage 获取 API 地址
const getApiUrl = () => {
  return localStorage.getItem('apiUrl') || 'http://localhost:5000'
}

const selectedCourses = ref<any[]>([])
const isLoading = ref(false)
const droppingCourseId = ref('')
const activeTab = ref('courses')

// 星期数组
const weekDays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

// 时间段配置
const timeSlots = [
  { time: '1-2', label: '1-2节' },
  { time: '3-4', label: '3-4节' },
  { time: '5-6', label: '5-6节' },
  { time: '7-8', label: '7-8节' },
  { time: '9-10', label: '9-10节' },
  { time: '11-12', label: '11-12节' }
]

// 解析课程时间并生成课程表数据
const scheduleData = computed(() => {
  const schedule: Record<string, Record<string, any>> = {}
  
  selectedCourses.value.forEach((course: any) => {
    const timeStr = course.teachingPlace || ''
    // 解析时间字符串，例如："2-4周(双) 星期五 5-8节"
    // 或者："星期一 1-2节"
    
    if (!timeStr) return
    
    // 提取星期和节次信息
    const dayMatch = timeStr.match(/(周[一二三四五六日天]|星期[一二三四五六日天])/)
    const periodMatch = timeStr.match(/(\d+)[-~](\d+)节/)
    
    if (dayMatch && periodMatch) {
      const dayStr = dayMatch[0]
      const startPeriod = parseInt(periodMatch[1])
      const endPeriod = parseInt(periodMatch[2])
      
      // 转换为星期索引 (0-6)
      const dayIndex = getDayIndex(dayStr)
      if (dayIndex === -1) return
      
      const dayKey = weekDays[dayIndex]
      
      // 为每个时间段添加课程
      for (let period = startPeriod; period <= endPeriod; period += 2) {
        const timeKey = getTimeSlotKey(period)
        if (timeKey && dayKey) {
          if (!schedule[dayKey]) {
            schedule[dayKey] = {}
          }
          // 如果该时间段已有课程，合并显示
          if (!schedule[dayKey][timeKey]) {
            schedule[dayKey][timeKey] = course
          }
        }
      }
    }
  })
  
  return schedule
})

// 获取星期索引
function getDayIndex(dayStr: string): number {
  const dayMap: Record<string, number> = {
    '周一': 0, '周二': 1, '周三': 2, '周四': 3, '周五': 4, '周六': 5, '周日': 6,
    '星期一': 0, '星期二': 1, '星期三': 2, '星期四': 3, '星期五': 4, '星期六': 5, '星期日': 6,
    '周天': 6, '星期天': 6
  }
  return dayMap[dayStr] ?? -1
}

// 根据节次获取时间段key
function getTimeSlotKey(period: number): string | null {
  if (period >= 1 && period <= 2) return '1-2'
  if (period >= 3 && period <= 4) return '3-4'
  if (period >= 5 && period <= 6) return '5-6'
  if (period >= 7 && period <= 8) return '7-8'
  if (period >= 9 && period <= 10) return '9-10'
  if (period >= 11 && period <= 12) return '11-12'
  return null
}

// 获取指定时间段和星期的课程
function getCourseAtTimeSlot(day: string, timeSlot: string): any | null {
  const daySchedule = scheduleData.value[day]
  if (!daySchedule) return null
  return daySchedule[timeSlot] || null
}

// 获取课程颜色（根据课程名称生成）
function getCourseColor(course: any): string {
  if (!course || !course.courseName) return '#409eff'
  const colors = [
    '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
    '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399'
  ]
  const courseName: string = course.courseName || ''
  const hash = courseName.split('').reduce((acc: number, char: string) => {
    return acc + char.charCodeAt(0)
  }, 0)
  const index = hash % colors.length
  return colors[index] || '#409eff'
}

// 获取登录信息
const getLoginInfo = () => {
  const loginInfo = localStorage.getItem('loginInfo')
  if (!loginInfo) {
    router.push('/')
    return null
  }
  return JSON.parse(loginInfo)
}

// 获取选课批次代码
const getSelectedBatchCode = () => {
  return localStorage.getItem('selectedBatchCode') || ''
}

// 加载已选课程
async function loadSelectedCourses() {
  const loginInfo = getLoginInfo()
  if (!loginInfo) return

  const selectedBatchCode = getSelectedBatchCode()
  if (!selectedBatchCode) {
    ElMessage.warning('请先选择选课批次')
    return
  }

  isLoading.value = true
  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/get-selected-courses`, {
      username: loginInfo.username,
      password: loginInfo.password,
      electiveBatchCode: selectedBatchCode
    })

    if (response.data.success) {
      // 处理返回的课程数据
      const data = response.data
      console.log(data)
      if (data && Array.isArray(data)) {
        // 如果直接是数组
        selectedCourses.value = data
      } else if (data && data.result && Array.isArray(data.result)) {
        // 如果数据在 result 字段中
        selectedCourses.value = data.result
      } else if (data && data.data && Array.isArray(data.data)) {
        // 如果数据在 data.data 字段中
        selectedCourses.value = data.data
      } else if (data && typeof data === 'object') {
        // 尝试从对象中提取课程列表
        const keys = Object.keys(data)
        if (keys.length > 0) {
          const firstKey = keys[0]
          if (firstKey && Array.isArray(data[firstKey])) {
            selectedCourses.value = data[firstKey]
          } else {
            selectedCourses.value = []
          }
        } else {
          selectedCourses.value = []
        }
      } else {
        selectedCourses.value = []
      }
      
      // 如果返回的数据是嵌套结构（类似 get_courses 的格式），需要展开
      if (selectedCourses.value.length > 0 && selectedCourses.value[0].tcList) {
        // 展开嵌套的课程数据
        const expandedCourses: any[] = []
        selectedCourses.value.forEach((course: any) => {
          if (course.tcList && Array.isArray(course.tcList)) {
            course.tcList.forEach((tc: any) => {
              expandedCourses.push({
                ...tc,
                courseName: course.courseName || tc.courseName,
                courseNumber: course.courseNumber || tc.courseNumber,
                credit: course.credit || tc.credit,
                courseTypeName: course.typeName || tc.courseTypeName,
                departmentName: course.departmentName || tc.departmentName
              })
            })
          } else {
            expandedCourses.push(course)
          }
        })
        selectedCourses.value = expandedCourses
      }
      
      if (selectedCourses.value.length === 0) {
        ElMessage.info('暂无已选课程')
      } else {
        ElMessage.success(`已加载 ${selectedCourses.value.length} 门已选课程`)
      }
    } else {
      ElMessage.error(response.data.message || '获取已选课程失败')
      selectedCourses.value = []
    }
  } catch (error: any) {
    let errorMsg = '获取已选课程失败，请重试'
    if (error.response) {
      errorMsg = error.response.data?.message || errorMsg
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请确保服务正在运行'
    } else {
      errorMsg = error.message || errorMsg
    }
    ElMessage.error(errorMsg)
    selectedCourses.value = []
  } finally {
    isLoading.value = false
  }
}

// 退课
async function handleDropCourse(course: any) {
  try {
    await ElMessageBox.confirm(
      `确定要退选课程 "${course.courseName}" 吗？`,
      '确认退课',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  const loginInfo = getLoginInfo()
  if (!loginInfo) return

  droppingCourseId.value = course.teachingClassID

  try {
    const API_BASE_URL = getApiUrl()
    const selectedBatchCode = getSelectedBatchCode()
    
    const response = await axios.post(`${API_BASE_URL}/drop-class`, {
      username: loginInfo.username,
      password: loginInfo.password,
      electiveBatchCode: selectedBatchCode,
      teachingClassId: course.teachingClassID,
      teachingClassType: course.teachingClassType || 'XGXK',
      campus: course.campus || '02',
      isMajor: course.isMajor || '1'
    })

    if (response.data.success) {
      ElMessage.success('退课成功！')
      // 重新加载已选课程列表
      await loadSelectedCourses()
    } else {
      ElMessage.error(response.data.message || '退课失败')
    }
  } catch (error: any) {
    let errorMsg = '退课失败，请重试'
    if (error.response) {
      errorMsg = error.response.data?.message || errorMsg
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请确保服务正在运行'
    } else {
      errorMsg = error.message || errorMsg
    }
    ElMessage.error(errorMsg)
  } finally {
    droppingCourseId.value = ''
  }
}

// 获取课程类型名称
function getCourseTypeName(type: string): string {
  if (!type) return '未知'
  const typeMap: Record<string, string> = {
    'TJKC': '推荐课程',
    'FANKC': '主修课程',
    'XGXK': '通识教育选修课程'
  }
  return typeMap[type] || type
}

onMounted(() => {
  loadSelectedCourses()
})
</script>

<style scoped>
.selected-courses-page {
  padding: 20px;
  min-height: 100%;
  box-sizing: border-box;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.page-content {
  background: #ffffff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  min-height: calc(100vh - 120px);
}

.course-tabs {
  height: 100%;
}

.tab-content {
  padding-top: 20px;
  min-height: calc(100vh - 200px);
}

.schedule-tab-content {
  overflow-x: auto;
  padding: 20px;
}

.schedule-empty {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.schedule-table {
  width: 100%;
}

.schedule-grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.schedule-grid th,
.schedule-grid td {
  border: 1px solid #ebeef5;
  padding: 8px;
  text-align: center;
}

.schedule-grid th {
  background: #f5f7fa;
  font-weight: 600;
  color: #606266;
}

.time-col {
  width: 80px;
}

.day-col {
  width: calc((100% - 80px) / 7);
}

.time-cell {
  background: #f5f7fa;
  font-weight: 500;
  color: #606266;
  text-align: center;
}

.course-cell {
  height: 80px;
  vertical-align: top;
  position: relative;
}

.course-cell.has-course {
  padding: 0;
}

.course-item {
  padding: 6px;
  border-radius: 4px;
  color: #ffffff;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s;
}

.course-item:hover {
  opacity: 0.9;
}

.course-name {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.course-place {
  font-size: 11px;
  opacity: 0.95;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.course-teacher {
  font-size: 11px;
  opacity: 0.9;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style>
/* 暗色模式样式 */
.dark-theme .selected-courses-page {
  background: transparent;
}

.dark-theme .page-title {
  color: #e0e0e0 !important;
}

.dark-theme .page-content {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .schedule-empty {
  color: #a0a0a0;
}

.dark-theme .schedule-grid th,
.dark-theme .schedule-grid td {
  border-color: #2a2a2a;
}

.dark-theme .schedule-grid th {
  background: #0f0f0f;
  color: #d0d0d0;
}

.dark-theme .time-cell {
  background: #0f0f0f;
  color: #d0d0d0;
}

</style>

