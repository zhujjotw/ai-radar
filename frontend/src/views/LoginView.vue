<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card style="width: 400px;" shadow="hover">
    <template #header>
      <div style="text-align: center;">
        <h2 style="margin: 0;">AI Radar</h2>
        <p style="color: #999; margin: 8px 0 0;">使用公司账号登录</p>
      </div>
    </template>
    <el-form @submit.prevent="handleLogin">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="zhang.san" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password @keyup.enter="handleLogin" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%;">
          登录
        </el-button>
      </el-form-item>
    </el-form>
    <div style="color: #999; font-size: 12px;">
      使用公司 LDAP 账号登录，登录后可访问 AI Radar 所有功能
    </div>
  </el-card>
</template>
