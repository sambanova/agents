import { createRouter, createWebHistory } from 'vue-router';
import MainLayout from '../views/MainLayout.vue';
import LoginPage from '../views/LoginPage.vue';
import TermsOfService from '../views/TermsOfService.vue';

const routes = [
  {
    path: '/terms-of-service',
    name: 'TermsOfService',
    component: TermsOfService,
    meta: { requiresAuth: false },
  },
  {
    path: '/:id?',
    name: 'home',
    component: MainLayout,
    meta: { requiresAuth: true }, // Optionally mark this route as protected and require authentication
  },
  {
    path: '/login',
    name: 'LoginPage',
    component: LoginPage,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
