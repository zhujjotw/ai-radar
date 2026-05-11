<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  ChatDotRound, Position, Trophy, Share, Connection, Setting, SwitchButton,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const isCollapse = ref(false)

const menuItems = [
  { path: '/chat', title: 'Chat', icon: ChatDotRound },
  { path: '/radar', title: 'Radar', icon: Position },
  { path: '/trials', title: 'Trials', icon: Trophy },
  { path: '/shares', title: 'Shares', icon: Share },
  { path: '/knowledge-graph', title: 'Knowledge Graph', icon: Connection },
  { path: '/settings', title: 'Settings', icon: Setting },
]

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '200px'" style="border-right: 1px solid #e6e6e6; transition: width 0.3s;">
      <div
        style="padding: 16px; display: flex; align-items: center; justify-content: center; gap: 10px; white-space: nowrap;"
      >
        <img
          src="/logo.jpg"
          alt="AI Radar"
          style="width: 32px; height: 32px; border-radius: 8px; object-fit: cover; flex-shrink: 0;"
        />
        <span v-if="!isCollapse" style="font-size: 18px; font-weight: bold;">AI Radar</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        :collapse="isCollapse"
        style="border-right: none;"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
      <div style="position: absolute; bottom: 0; width: 100%; padding: 12px; border-top: 1px solid #e6e6e6;">
        <div v-if="!isCollapse" style="margin-bottom: 8px; font-size: 12px; color: #999;">
          {{ auth.user?.username }}
        </div>
        <el-button text @click="isCollapse = !isCollapse" style="width: 100%;">
          {{ isCollapse ? '>' : '<' }}
        </el-button>
        <el-button text type="danger" @click="handleLogout" style="width: 100%;">
          <el-icon><SwitchButton /></el-icon>
          <span v-if="!isCollapse">Sign Out</span>
        </el-button>
      </div>
    </el-aside>
    <el-main style="padding: 20px; overflow-y: auto; background: #f5f7fa;">
      <slot />
    </el-main>
  </el-container>
</template>
