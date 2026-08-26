<template>
  <div class="select-class-page">
    <div class="page-header">
      <h2 class="page-title">开始选课</h2>
      <el-button
        type="primary"
        :icon="Refresh"
        @click="handleRefresh"
        :loading="isLoadingCourses"
        circle
        title="刷新课程列表"
      />
    </div>
    
    <!-- 课程类型 Tab -->
    <el-tabs v-if="enabledTabs.length > 0" v-model="activeTab" @tab-change="handleTabChange" class="course-tabs">
      <el-tab-pane
        v-for="tab in enabledTabs"
        :key="tab.code"
        :label="tab.label"
        :name="tab.code"
      ></el-tab-pane>
    </el-tabs>
    
    <!-- 如果没有 Tab，显示提示 -->
    <div v-else class="course-tabs">
      <el-alert
        title="未找到可用的课程类型，请重新登录并选择批次"
        type="warning"
        :closable="false"
        show-icon
      />
    </div>
    
    <!-- 搜索框 -->
    <div class="search-container">
      <el-input
        v-model="searchQuery"
        placeholder="搜索课程名称、教师、课程编号等..."
        clearable
        @clear="handleSearch"
        @keyup.enter="handleSearch"
        class="search-input"
      >
        <template #append>
          <el-button @click="handleSearch" :loading="isLoadingCourses">搜索</el-button>
        </template>
      </el-input>
    </div>
    
    <!-- 课程列表 -->
    <div v-if="courses.length > 0" class="courses-container">
      <el-table :data="courses" stripe style="width: 100%">
        <el-table-column prop="courseName" label="课程名称" width="200" />
        <el-table-column prop="teacherName" label="教师" width="120" />
        <el-table-column prop="teachingClassId" label="教学班ID" width="250" />
        <el-table-column label="容量/已选" width="100">
          <template #default="scope">
            {{ scope.row.selectedCount }}/{{ scope.row.capacity }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.isChoose" type="success" size="small">已选</el-tag>
            <el-tag v-if="!scope.row.isChoose && scope.row.isFull==='1'" type="danger" size="small"  style="margin-right: 3px;">已满</el-tag>
            <el-tag v-if="!scope.row.isChoose && scope.row.isConflict==='1'" type="warning" size="small">冲突</el-tag>
            <el-tag v-if="!scope.row.isChoose && scope.row.isFull!=='1' && scope.row.isConflict!=='1'" type="info" size="small">可选</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="teachingPlace" label="上课地点" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button
              v-if="scope.row.isChoose"
              type="danger"
              size="small"
              @click="handleDropCourse(scope.row)"
              :loading="selectingCourseId === scope.row.teachingClassId"
            >
              退课
            </el-button>
            <el-button
              v-else-if="scope.row.isFull!=='1' && scope.row.isConflict!=='1'"
              type="primary"
              size="small"
              @click="handleSelectCourse(scope.row)"
              :loading="selectingCourseId === scope.row.teachingClassId"
            >
              选课
            </el-button>
            <el-button
              v-if="!scope.row.isChoose && scope.row.isConflict!=='1'"
              type="warning"
              size="small"
              @click="handleAddToQueue(scope.row)"
            >
              加入抢课
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 空状态 -->
    <div v-else class="courses-container">
      <el-empty 
        :description="isLoadingCourses ? '加载中...' : '暂无课程数据，请尝试搜索或切换课程类型'"
        :image-size="120"
      />
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { addToQueue } from '../composables/useCourseQueue'

const router = useRouter()

// 从 localStorage 获取 API 地址，默认为 5000
const getApiUrl = () => {
  return localStorage.getItem('apiUrl') || 'http://localhost:5000'
}

const courses = ref<any[]>([])
const isLoadingCourses = ref(false)
const currentBatchCode = ref('')
const selectingCourseId = ref('')
const searchQuery = ref('') // 搜索关键词

// Tab 代码到名称的映射（默认值，会被系统参数覆盖）
const tabNameMap = ref<Record<string, string>>({
  'BYKC': '补选课程',
  'TJKC': '推荐课程',
  'FANKC': '主修课程',
  'FAWKC': '方案外课程',
  'CXKC': '创新课程',
  'TYKC': '体育课程',
  'XGXK': '通识教育选修课程',
  'ALLKC': '全校课程查询',
  'FX': '辅修课程'
})

// 启用的 Tab 列表
const enabledTabs = ref<Array<{ code: string; label: string }>>([])
const activeTab = ref('') // 动态设置默认值

// 从 localStorage 获取登录信息
const getLoginInfo = () => {
  const loginInfo = localStorage.getItem('loginInfo')
  if (!loginInfo) {
    router.push('/')
    return null
  }
  return JSON.parse(loginInfo)
}

// 处理 Tab 切换
async function handleTabChange() {
  if (currentBatchCode.value) {
    await loadCourses()
  }
}

// 处理搜索
async function handleSearch() {
  if (currentBatchCode.value) {
    await loadCourses()
  }
}

// 强制刷新课程列表
async function handleRefresh() {
  if (!currentBatchCode.value) {
    ElMessage.warning('请先在登录页面选择批次')
    return
  }
  
  // 清空搜索框
  searchQuery.value = ''
  
  // 重新加载课程
  await loadCourses()
}

// 加载课程列表
async function loadCourses() {
  const loginInfo = getLoginInfo()
  if (!loginInfo || !currentBatchCode.value) return

  if (isLoadingCourses.value) return
  isLoadingCourses.value = true

  try {
    const API_BASE_URL = getApiUrl()
    const requestData: any = {
      username: loginInfo.username,
      password: loginInfo.password,
      electiveBatchCode: currentBatchCode.value,
      teachingClassType: activeTab.value, // 使用当前选中的 tab 类型
      campus: '02',
      isMajor: '1'
    }
    
    // 如果有搜索关键词，添加到请求中
    if (searchQuery.value && searchQuery.value.trim()) {
      requestData.queryContent = searchQuery.value.trim()
    }
    
    const response = await axios.post(`${API_BASE_URL}/get-courses`, requestData)
    if (response.data.success) {
      // 解析课程数据
      const result = response.data.data.dataList  
      console.log('课程数据:', result)
      
      if (result && Array.isArray(result)) {
        // 展开每门课程的教学班列表
        const allTeachingClasses: any[] = []
        
        result.forEach((course: any) => {
          const courseName = course.courseName || course.course_name || ''
          const courseNumber = course.courseNumber || course.course_number || ''
          const credit = course.credit || '0'
          const departmentName = course.departmentName || course.department_name || ''
          
          // 遍历该课程的所有教学班
          if (course.tcList && Array.isArray(course.tcList)) {
            course.tcList.forEach((tc: any) => {
              allTeachingClasses.push({
                teachingClassId: tc.teachingClassID || tc.teaching_class_id || '',
                courseName: courseName,
                courseNumber: courseNumber,
                credit: credit,
                departmentName: departmentName,
                teacherName: tc.teacherName || tc.teacher_name || '',
                capacity: tc.classCapacity || tc.class_capacity || '0',
                selectedCount: tc.numberOfSelected || tc.number_of_selected || '0',
                isFull: tc.isFull === '1' || tc.is_full === '1',
                isConflict: tc.isConflict === '1' || tc.is_conflict === '1',
                isChoose: tc.isChoose === '1' || tc.is_choose === '1',
                conflictDesc: tc.conflictDesc || tc.conflict_desc || '',
                teachingPlace: tc.teachingPlace || tc.teaching_place || '',
                teachingMethod: tc.teachingMethod || tc.teaching_method || '',
                courseIndex: tc.courseIndex || tc.course_index || '',
                recommendSchoolClass: tc.recommendSchoolClass || tc.recommend_school_class || '',
                ...tc
              })
            })
          }
        })
        
        courses.value = allTeachingClasses
        ElMessage.success(`已加载 ${courses.value.length} 个教学班`)
      } else {
        courses.value = []
        ElMessage.warning('暂无可用课程')
      }
    } else {
      ElMessage.error(response.data.message || '获取课程列表失败')
      courses.value = []
    }
  } catch (error: any) {
    if (error.response) {
      ElMessage.error(error.response.data?.message || '获取课程列表失败')
    } else if (error.request) {
      ElMessage.error('无法连接到服务器，请确保服务正在运行')
    } else {
      ElMessage.error(error.message || '获取课程列表失败')
    }
    courses.value = []
  } finally {
    isLoadingCourses.value = false
  }
}

// 选课
async function handleSelectCourse(course: any) {
  const loginInfo = getLoginInfo()
  if (!loginInfo) return

  selectingCourseId.value = course.teachingClassId

  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/select-class`, {
      username: loginInfo.username,
      password: loginInfo.password,
      electiveBatchCode: currentBatchCode.value,
      teachingClassId: course.teachingClassId,
      teachingClassType: activeTab.value, // 使用当前选中的 tab 类型
      campus: '02',
      isMajor: '1',
      operationType: '1'
    })

    if (response.data.success) {
      ElMessage.success(response.data.message || '选课成功！')
      // 刷新课程列表
      await loadCourses()
    } else {
      ElMessage.error(response.data.message || '选课失败')
    }
  } catch (error: any) {
    if (error.response) {
      ElMessage.error(error.response.data?.message || '选课失败，请重试')
    } else if (error.request) {
      ElMessage.error('无法连接到服务器，请确保服务正在运行')
    } else {
      ElMessage.error(error.message || '选课失败，请重试')
    }
  } finally {
    selectingCourseId.value = ''
  }
}

// 退课
async function handleDropCourse(course: any) {
  const loginInfo = getLoginInfo()
  if (!loginInfo || !currentBatchCode.value) return

  try {
    await ElMessageBox.confirm(
      `确定要退选课程"${course.courseName}"吗？`,
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

  selectingCourseId.value = course.teachingClassId

  try {
    const API_BASE_URL = getApiUrl()
    const response = await axios.post(`${API_BASE_URL}/drop-class`, {
      username: loginInfo.username,
      password: loginInfo.password,
      electiveBatchCode: currentBatchCode.value,
      teachingClassId: course.teachingClassId,
      isMajor: '1'
    })

    if (response.data.success) {
      ElMessage.success(response.data.message || '退课成功！')
      // 刷新课程列表
      await loadCourses()
    } else {
      ElMessage.error(response.data.message || '退课失败')
    }
  } catch (error: any) {
    if (error.response) {
      ElMessage.error(error.response.data?.message || '退课失败，请重试')
    } else if (error.request) {
      ElMessage.error('无法连接到服务器，请确保服务正在运行')
    } else {
      ElMessage.error(error.message || '退课失败，请重试')
    }
  } finally {
    selectingCourseId.value = ''
  }
}

// 加入抢课列表
function handleAddToQueue(course: any) {
  if (!currentBatchCode.value) {
    ElMessage.warning('请先选择批次')
    return
  }

  addToQueue({
    teachingClassId: course.teachingClassId,
    courseName: course.courseName,
    teacherName: course.teacherName,
    electiveBatchCode: currentBatchCode.value,
    teachingClassType: activeTab.value,
    campus: '02',
    isMajor: '1',
    teachingPlace: course.teachingPlace,
    capacity: course.capacity,
    selectedCount: course.selectedCount
  })
}

// 页面加载时从 localStorage 读取批次代码并加载课程
onMounted(() => {
  const savedBatchCode = localStorage.getItem('selectedBatchCode')
  if (savedBatchCode) {
    currentBatchCode.value = savedBatchCode
    
    // 读取系统参数中的课程类型名称
    const savedTabNames = localStorage.getItem('tabNames')
    if (savedTabNames) {
      try {
        const sysTabNames = JSON.parse(savedTabNames)
        // 更新 tabNameMap，使用系统返回的名称
        tabNameMap.value = { ...tabNameMap.value, ...sysTabNames }
      } catch (error) {
        console.error('解析 tabNames 失败:', error)
      }
    }
    
    // 读取启用的 Tab 列表
    const savedEnabledTabs = localStorage.getItem('enabledTabs')
    if (savedEnabledTabs) {
      try {
        const tabCodes: string[] = JSON.parse(savedEnabledTabs)
        enabledTabs.value = tabCodes
          .filter(code => tabNameMap.value[code]) // 过滤掉未知的代码
          .map(code => ({
            code,
            label: tabNameMap.value[code] || code // 使用系统参数中的名称
          }))
        
        // 设置默认选中的 Tab（第一个）
        if (enabledTabs.value.length > 0 && enabledTabs.value[0]) {
          activeTab.value = enabledTabs.value[0].code
        }
      } catch (error) {
        console.error('解析 enabledTabs 失败:', error)
        // 如果解析失败，使用默认的 Tab
        setDefaultTabs()
      }
    } else {
      // 如果没有保存的 enabledTabs，使用默认的 Tab
      setDefaultTabs()
    }
    
    // 加载课程
    if (activeTab.value) {
      loadCourses()
    }
  } else {
    ElMessage.warning('请先在登录页面选择批次')
    // 可以跳转到登录页面重新选择
    // router.push('/')
  }
})

// 设置默认的 Tab（兼容旧版本）
function setDefaultTabs() {
  enabledTabs.value = [
    { code: 'TJKC', label: tabNameMap.value['TJKC'] || '推荐课程' },
    { code: 'FANKC', label: tabNameMap.value['FANKC'] || '主修课程' },
    { code: 'XGXK', label: tabNameMap.value['XGXK'] || '通识教育选修课程' }
  ]
  activeTab.value = 'TJKC'
}
</script>

<style scoped>
.select-class-page {
  padding: 20px;
  min-height: 100%;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.course-tabs {
  margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  padding: 10px 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.search-container {
  margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  padding: 15px 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.search-input {
  max-width: 600px;
}

.courses-container {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
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

.dark-theme .course-tabs {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .search-container {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}

.dark-theme .courses-container {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
}
</style>
