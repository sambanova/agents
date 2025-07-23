import { createRouter, createWebHistory } from 'vue-router'

// Lazy load components for better performance
const MainLayout = () => import('../views/MainLayout.vue')
const LoginPage = () => import('../views/LoginPage.vue')
const TermsOfService = () => import('../views/TermsOfService.vue')

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
  },
  {
    path: '/callback',
    name: 'callback',
    component: MainLayout
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
