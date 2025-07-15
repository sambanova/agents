import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../views/MainLayout.vue'
import LoginPage from '../views/LoginPage.vue'
import TermsOfService from '../views/TermsOfService.vue'
const routes = [
  {
    path: '/terms-of-service',
    name: 'TermsOfService',
    component: TermsOfService,
    meta: { requiresAuth: false }
  },
  {
    path: '/share/:shareToken',
    name: 'SharedConversation',
    component: MainLayout,
    meta: { requiresAuth: false }
  },
  {
    path: '/:id?',
    name: 'home',
    component: MainLayout,
    meta: { requiresAuth: true } // Optionally mark this route as protected and require authentication

  },
  {
    path: '/login',
    name: 'LoginPage',
    component: LoginPage
  }
  
]


const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard to handle authentication
router.beforeEach((to, from, next) => {
  // Allow share routes without authentication
  if (to.path.startsWith('/share/')) {
    return next()
  }
  
  // Allow terms of service without authentication
  if (to.path === '/terms-of-service') {
    return next()
  }
  
  // For all other routes, continue with normal authentication flow
  next()
})

export default router
