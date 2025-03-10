import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../views/MainLayout.vue'
import LoginPage from '../views/LoginPage.vue'

const routes = [
  {
    path: '/:id?',
    name: 'home',
    component: MainLayout,
    meta: { requiresAuth: true } // Optionally mark this route as protected

  },
  {
    path: '/login',
    name: 'LoginPage',
    component: LoginPage
  }
  // Add other routes here
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
