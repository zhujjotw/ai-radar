import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { layout: 'auth', public: true },
    },
    {
      path: '/',
      redirect: '/chat',
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { title: 'AI 助手', icon: 'ChatDotRound' },
    },
    {
      path: '/radar',
      name: 'radar',
      component: () => import('@/views/RadarView.vue'),
      meta: { title: 'Radar', icon: 'Position' },
    },
    {
      path: '/trials',
      name: 'trials',
      component: () => import('@/views/TrialsView.vue'),
      meta: { title: 'Trials', icon: 'Trophy' },
    },
    {
      path: '/shares',
      name: 'shares',
      component: () => import('@/views/SharesView.vue'),
      meta: { title: 'Shares', icon: 'Share' },
    },
    {
      path: '/knowledge-graph',
      name: 'knowledge-graph',
      component: () => import('@/views/KnowledgeGraphView.vue'),
      meta: { title: 'Knowledge Graph', icon: 'Connection' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: 'Settings', icon: 'Setting' },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.meta.public && auth.isAuthenticated && to.name === 'login') {
    return { name: 'chat' }
  }
})

export default router
