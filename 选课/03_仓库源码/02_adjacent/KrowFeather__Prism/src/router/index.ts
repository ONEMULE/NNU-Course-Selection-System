import { createRouter, createWebHistory } from 'vue-router'
import SelectClass from '../views/SelectClass.vue'
import Browse from '../views/Browse.vue'
import Settings from '../views/Settings.vue'
import SelectedCourses from '../views/SelectedCourses.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Login',
      component: () => import('../views/Login.vue')
    },
    {
      path: '/select-class',
      name: 'SelectClass',
      component: SelectClass,
      meta: { requiresAuth: true }
    },
    {
      path: '/browse',
      name: 'Browse',
      component: Browse,
      meta: { requiresAuth: true }
    },
    {
      path: '/selected-courses',
      name: 'SelectedCourses',
      component: SelectedCourses,
      meta: { requiresAuth: true }
    },
    {
      path: '/settings',
      name: 'Settings',
      component: Settings,
      meta: { requiresAuth: true }
    }
  ]
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const isLoggedIn = !!localStorage.getItem('loginInfo')
  
  if (to.meta.requiresAuth && !isLoggedIn) {
    // 需要登录但未登录，重定向到登录页
    next('/')
  } else if (to.path === '/' && isLoggedIn) {
    // 已登录访问登录页，重定向到主页面
    next('/select-class')
  } else {
    next()
  }
})

export default router

