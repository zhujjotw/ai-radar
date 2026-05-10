<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ProjectListItem } from '@/api/projects'
import { fetchProject, type ProjectDetail } from '@/api/projects'

const store = useProjectStore()
const auth = useAuthStore()

const drawerVisible = ref(false)
const selectedProject = ref<ProjectDetail | null>(null)
const loadingDetail = ref(false)

const statusColors: Record<string, string> = {
  needs_review: 'info',
  watch: '',
  try: 'warning',
  adopt: 'success',
  reject: 'danger',
  claimed: '',
  running: 'warning',
  blocked: 'danger',
  demo_done: 'success',
  shared: '',
  dropped: 'info',
}

const sortOptions = [
  { label: 'Recommendation', value: 'recommendation_sort' },
  { label: 'Most Stars', value: 'stars' },
  { label: 'Newest', value: 'first_seen_at' },
  { label: 'Recently Updated', value: 'last_pushed_at' },
  { label: 'Unevaluated First', value: 'unevaluated_sort' },
]

function getStatusTag(project: ProjectListItem): { text: string; type: string } {
  if (project.active_trial && (project.active_trial as Record<string, unknown>).status) {
    const status = (project.active_trial as Record<string, unknown>).status as string
    return { text: status, type: statusColors[status] || 'info' }
  }
  if (project.latest_evaluation && (project.latest_evaluation as Record<string, unknown>).decision) {
    const decision = (project.latest_evaluation as Record<string, unknown>).decision as string
    return { text: decision, type: statusColors[decision] || 'info' }
  }
  return { text: '-', type: 'info' }
}

function getScore(project: ProjectListItem): string {
  const ev = project.latest_evaluation as Record<string, unknown> | null
  if (ev && ev.recommendation_score != null) {
    return `${ev.recommendation_score}/5`
  }
  return '-'
}

async function openProject(project: ProjectListItem) {
  loadingDetail.value = true
  drawerVisible.value = true
  try {
    selectedProject.value = await fetchProject(project.id)
  } finally {
    loadingDetail.value = false
  }
}

async function handleClaim(project: ProjectListItem) {
  try {
    await ElMessageBox.confirm(`Claim ${project.name}?`, 'Claim Project', { type: 'info' })
    await store.claimProject(project.id)
    ElMessage.success(`Claimed ${project.name}`)
    drawerVisible.value = false
  } catch {
    // cancelled
  }
}

function handleFilterChange() {
  store.fetchProjects()
}

onMounted(() => {
  store.fetchTags()
  store.fetchProjects()
})
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px;">Candidate Pool</h2>
    <p style="color: #999; margin: 0 0 16px;">Browse, evaluate, and claim AI open-source projects</p>

    <!-- Filters -->
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-select v-model="store.filters.tag" placeholder="All Directions" clearable @change="handleFilterChange" style="width: 100%;">
          <el-option v-for="tag in store.allTags" :key="tag" :label="tag" :value="tag" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="store.filters.order_by" @change="handleFilterChange" style="width: 100%;">
          <el-option v-for="opt in sortOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-col>
      <el-col :span="12" style="text-align: right; color: #999;">
        {{ store.projects.length }} projects
      </el-col>
    </el-row>

    <!-- Table -->
    <el-table :data="store.projects" v-loading="store.loading" stripe @row-click="openProject"
              style="cursor: pointer;">
      <el-table-column prop="name" label="Project" min-width="180">
        <template #default="{ row }">
          <strong>{{ row.name }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="Tags" min-width="150">
        <template #default="{ row }">
          <el-tag v-for="tag in (row.tags || []).slice(0, 2)" :key="tag" size="small" style="margin-right: 4px;">
            {{ tag }}
          </el-tag>
          <span v-if="(row.tags || []).length > 2" style="color: #999;">+{{ row.tags.length - 2 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Score" width="80" align="center">
        <template #default="{ row }">
          {{ getScore(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="stars" label="Stars" width="100" align="right">
        <template #default="{ row }">
          {{ row.stars?.toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="language" label="Language" width="100" />
      <el-table-column label="Owner" width="100">
        <template #default="{ row }">
          {{ row.owner || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="Status" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusTag(row).type" size="small">
            {{ getStatusTag(row).text }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- Detail Drawer -->
    <el-drawer v-model="drawerVisible" :title="selectedProject?.name || ''" size="480px" direction="rtl">
      <div v-loading="loadingDetail">
        <template v-if="selectedProject">
          <!-- Basic Info -->
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Stars">{{ selectedProject.stars?.toLocaleString() }}</el-descriptions-item>
            <el-descriptions-item label="Forks">{{ selectedProject.forks?.toLocaleString() }}</el-descriptions-item>
            <el-descriptions-item label="Language">{{ selectedProject.language || '-' }}</el-descriptions-item>
            <el-descriptions-item label="License">{{ selectedProject.license || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Pool">{{ selectedProject.pool }}</el-descriptions-item>
            <el-descriptions-item label="Source">{{ selectedProject.source }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedProject.last_pushed_at" label="Last Push">{{ selectedProject.last_pushed_at?.split(' ')[0] }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedProject.first_seen_at" label="Discovered">{{ selectedProject.first_seen_at?.split(' ')[0] }}</el-descriptions-item>
          </el-descriptions>

          <!-- GitHub Link -->
          <div style="margin: 12px 0;">
            <el-link type="primary" :href="selectedProject.github_url" target="_blank">
              View on GitHub
            </el-link>
          </div>

          <!-- Description -->
          <div v-if="selectedProject.description" style="margin: 12px 0; padding: 8px 12px; background: #f5f7fa; border-radius: 4px;">
            {{ selectedProject.description }}
          </div>

          <!-- Tags -->
          <div v-if="selectedProject.tags?.length" style="margin: 12px 0;">
            <strong>Tags:</strong>
            <el-tag v-for="tag in selectedProject.tags" :key="tag" size="small" style="margin-right: 4px;">{{ tag }}</el-tag>
          </div>
          <div v-if="selectedProject.topics?.length" style="margin: 12px 0;">
            <strong>Topics：</strong>
            <el-tag v-for="topic in selectedProject.topics" :key="topic" size="small" type="info" style="margin-right: 4px;">{{ topic }}</el-tag>
          </div>

          <!-- LLM Description -->
          <el-divider v-if="selectedProject.llm_description" />
          <div v-if="selectedProject.llm_description" style="margin: 12px 0;">
            <strong>Description</strong>
            <p style="color: #666;">{{ selectedProject.llm_description }}</p>
          </div>
          <div v-if="selectedProject.llm_scenarios" style="margin: 12px 0;">
            <strong>Use Cases</strong>
            <p style="color: #666; white-space: pre-line;">{{ selectedProject.llm_scenarios }}</p>
          </div>

          <!-- Evaluation -->
          <template v-if="selectedProject.latest_evaluation">
            <el-divider />
            <h4>Evaluation</h4>
            <el-row :gutter="8">
              <el-col :span="8">
                <el-statistic title="Relevance" :value="(selectedProject.latest_evaluation as Record<string, unknown>).relevance_score ?? '-'" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="Trialability" :value="(selectedProject.latest_evaluation as Record<string, unknown>).trialability_score ?? '-'" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="Value" :value="(selectedProject.latest_evaluation as Record<string, unknown>).value_score ?? '-'" />
              </el-col>
            </el-row>
            <div style="margin-top: 8px;">
              <el-tag :type="statusColors[(selectedProject.latest_evaluation as Record<string, unknown>).decision as string] || 'info'">
                Decision: {{ (selectedProject.latest_evaluation as Record<string, unknown>).decision }}
              </el-tag>
              <span v-if="(selectedProject.latest_evaluation as Record<string, unknown>).recommendation_score" style="margin-left: 8px;">
                Score: {{ (selectedProject.latest_evaluation as Record<string, unknown>).recommendation_score }}/5
              </span>
            </div>
            <p v-if="(selectedProject.latest_evaluation as Record<string, unknown>).decision_reason" style="color: #999; font-size: 12px; margin-top: 4px;">
              Reason: {{ (selectedProject.latest_evaluation as Record<string, unknown>).decision_reason }}
            </p>
          </template>

          <!-- Trial Info -->
          <template v-if="selectedProject.active_trial">
            <el-divider />
            <h4>Trial Info</h4>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="Owner">{{ (selectedProject.active_trial as Record<string, unknown>).owner }}</el-descriptions-item>
              <el-descriptions-item label="Status">
                <el-tag :type="statusColors[(selectedProject.active_trial as Record<string, unknown>).status as string]" size="small">
                  {{ (selectedProject.active_trial as Record<string, unknown>).status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item v-if="(selectedProject.active_trial as Record<string, unknown>).due_date" label="Due Date">
                {{ (selectedProject.active_trial as Record<string, unknown>).due_date }}
              </el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- Actions -->
          <el-divider />
          <template v-if="selectedProject.active_trial">
            <el-alert type="info" :closable="false" :title="`Claimed by ${(selectedProject.active_trial as Record<string, unknown>).owner}`" />
            <el-button style="margin-top: 8px;" @click="$router.push('/trials')">Go to Trials</el-button>
          </template>
          <template v-else>
            <el-button type="primary" @click="handleClaim(selectedProject)">
              Claim this project
            </el-button>
          </template>
        </template>
      </div>
    </el-drawer>
  </div>
</template>
