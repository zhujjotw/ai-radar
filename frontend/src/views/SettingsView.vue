<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'
import { ElMessage } from 'element-plus'

const form = ref({
  llm_api_key: '',
  llm_base_url: '',
  llm_model: '',
  github_token: '',
})
const status = ref({ llm_api_key_set: false, llm_base_url: '', llm_model: '', github_token_set: false })
const loading = ref(false)

async function loadSettings() {
  const { data } = await api.get('/settings')
  status.value = data
  form.value.llm_base_url = data.llm_base_url
  form.value.llm_model = data.llm_model
}

async function handleSave() {
  loading.value = true
  try {
    await api.put('/settings', form.value)
    ElMessage.success('配置已保存，下次启动生效')
    loadSettings()
  } finally {
    loading.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div style="max-width: 600px;">
    <h2 style="margin: 0 0 16px;">Settings</h2>

    <!-- LLM Config -->
    <el-card style="margin-bottom: 16px;">
      <template #header><strong>LLM 配置</strong></template>
      <el-form label-width="100px">
        <el-form-item label="API Key">
          <el-input v-model="form.llm_api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.llm_base_url" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="form.llm_model" />
        </el-form-item>
        <el-form-item>
          <el-tag v-if="status.llm_api_key_set" type="success">LLM 已配置</el-tag>
          <el-tag v-else type="warning">LLM 未配置</el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- GitHub Config -->
    <el-card style="margin-bottom: 16px;">
      <template #header><strong>GitHub 配置</strong></template>
      <el-form label-width="100px">
        <el-form-item label="Token">
          <el-input v-model="form.github_token" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-tag v-if="status.github_token_set" type="success">Token 已配置</el-tag>
          <el-tag v-else type="info">未配置 Token</el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <el-button type="primary" :loading="loading" @click="handleSave">保存配置</el-button>
  </div>
</template>
