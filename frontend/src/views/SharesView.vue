<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchShares, fetchReadyTrials, createShare, fetchShareMarkdown } from '@/api/shares'
import { useAuthStore } from '@/stores/auth'
import type { ShareItem } from '@/api/shares'

const auth = useAuthStore()
const activeTab = ref('ready')
const readyTrials = ref<{ trial_id: number; project_name: string; owner: string; result_summary: string | null }[]>([])
const shares = ref<ShareItem[]>([])
const loading = ref(false)
const createDialogVisible = ref(false)
const creatingShare = ref({
  trial_id: 0,
  title: '',
  summary: '',
  key_findings: '',
  reusable_patterns: '',
  applicable_scenarios: '',
  knowledge_doc_url: '',
})
const markdownPreview = ref('')
const markdownDialogVisible = ref(false)

async function loadReadyTrials() {
  loading.value = true
  try {
    readyTrials.value = await fetchReadyTrials()
  } finally {
    loading.value = false
  }
}

async function loadShares() {
  loading.value = true
  try {
    shares.value = await fetchShares()
  } finally {
    loading.value = false
  }
}

function openCreateDialog(trial: { trial_id: number; project_name: string; owner: string; result_summary: string | null }) {
  creatingShare.value = {
    trial_id: trial.trial_id,
    title: `${trial.project_name} - Trial Report`,
    summary: trial.result_summary || '',
    key_findings: '',
    reusable_patterns: '',
    applicable_scenarios: '',
    knowledge_doc_url: '',
  }
  createDialogVisible.value = true
}

async function handleCreate() {
  try {
    await createShare({
      trial_id: creatingShare.value.trial_id,
      title: creatingShare.value.title,
      summary: creatingShare.value.summary,
      key_findings: creatingShare.value.key_findings,
      reusable_patterns: creatingShare.value.reusable_patterns,
      applicable_scenarios: creatingShare.value.applicable_scenarios,
      knowledge_doc_url: creatingShare.value.knowledge_doc_url,
      shared_by: auth.user?.username,
    })
    ElMessage.success('分享已创建')
    createDialogVisible.value = false
    loadReadyTrials()
    loadShares()
  } catch {
    // handled by interceptor
  }
}

async function handleExport(shareId: number) {
  try {
    markdownPreview.value = await fetchShareMarkdown(shareId)
    markdownDialogVisible.value = true
  } catch {
    // handled by interceptor
  }
}

onMounted(() => {
  loadReadyTrials()
  loadShares()
})
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px;">Shares</h2>
    <p style="color: #999; margin: 0 0 16px;">Create share archives from completed trials and export Markdown</p>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Trials Ready for Sharing" name="ready">
        <el-table :data="readyTrials" v-loading="loading" stripe>
          <el-table-column prop="project_name" label="Project" min-width="200" />
          <el-table-column prop="owner" label="Owner" width="120" />
          <el-table-column prop="result_summary" label="Result" min-width="200" />
          <el-table-column label="Actions" width="120">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openCreateDialog(row)">Create Share</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && readyTrials.length === 0" description="No demo_done trials ready for sharing" />
      </el-tab-pane>

      <el-tab-pane label="Share Archives" name="archives">
        <el-table :data="shares" v-loading="loading" stripe>
          <el-table-column prop="title" label="Title" min-width="200" />
          <el-table-column prop="project_name" label="Project" width="180" />
          <el-table-column prop="shared_by" label="Shared by" width="120" />
          <el-table-column prop="shared_at" label="Date" width="160">
            <template #default="{ row }">
              {{ row.shared_at?.split(' ')[0] }}
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="handleExport(row.id)">Export MD</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Create Share Dialog -->
    <el-dialog v-model="createDialogVisible" title="Create Share Record" width="500px">
      <el-form label-width="100px">
        <el-form-item label="Title">
          <el-input v-model="creatingShare.title" />
        </el-form-item>
        <el-form-item label="Summary">
          <el-input v-model="creatingShare.summary" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="Key Findings">
          <el-input v-model="creatingShare.key_findings" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="Reusable Patterns">
          <el-input v-model="creatingShare.reusable_patterns" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Scenarios">
          <el-input v-model="creatingShare.applicable_scenarios" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Doc URL">
          <el-input v-model="creatingShare.knowledge_doc_url" placeholder="Optional" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="handleCreate">Create</el-button>
      </template>
    </el-dialog>

    <!-- Markdown Preview Dialog -->
    <el-dialog v-model="markdownDialogVisible" title="Markdown Export" width="600px">
      <el-input type="textarea" :rows="20" :model-value="markdownPreview" readonly />
    </el-dialog>
  </div>
</template>
