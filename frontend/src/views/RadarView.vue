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
  { label: '推荐分优先', value: 'recommendation_sort' },
  { label: 'Stars 最多', value: 'stars' },
  { label: '最新发现', value: 'first_seen_at' },
  { label: '最近更新', value: 'last_pushed_at' },
  { label: '未评估优先', value: 'unevaluated_sort' },
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
    await ElMessageBox.confirm(`确认认领 ${project.name}?`, '认领项目', { type: 'info' })
    await store.claimProject(project.id)
    ElMessage.success(`已认领 ${project.name}`)
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
    <p style="color: #999; margin: 0 0 16px;">AI 开源项目候选池 — 浏览、评估、认领</p>

    <!-- Filters -->
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-select v-model="store.filters.tag" placeholder="全部方向" clearable @change="handleFilterChange" style="width: 100%;">
          <el-option v-for="tag in store.allTags" :key="tag" :label="tag" :value="tag" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="store.filters.order_by" @change="handleFilterChange" style="width: 100%;">
          <el-option v-for="opt in sortOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-col>
      <el-col :span="12" style="text-align: right; color: #999;">
        共 {{ store.projects.length }} 个项目
      </el-col>
    </el-row>

    <!-- Table -->
    <el-table :data="store.projects" v-loading="store.loading" stripe @row-click="openProject"
              style="cursor: pointer;">
      <el-table-column prop="name" label="项目名称" min-width="180">
        <template #default="{ row }">
          <strong>{{ row.name }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="标签" min-width="150">
        <template #default="{ row }">
          <el-tag v-for="tag in (row.tags || []).slice(0, 2)" :key="tag" size="small" style="margin-right: 4px;">
            {{ tag }}
          </el-tag>
          <span v-if="(row.tags || []).length > 2" style="color: #999;">+{{ row.tags.length - 2 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="推荐分" width="80" align="center">
        <template #default="{ row }">
          {{ getScore(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="stars" label="Stars" width="100" align="right">
        <template #default="{ row }">
          {{ row.stars?.toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="language" label="语言" width="100" />
      <el-table-column label="负责人" width="100">
        <template #default="{ row }">
          {{ row.owner || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
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
            <el-descriptions-item label="语言">{{ selectedProject.language || '-' }}</el-descriptions-item>
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
            <strong>方向标签：</strong>
            <el-tag v-for="tag in selectedProject.tags" :key="tag" size="small" style="margin-right: 4px;">{{ tag }}</el-tag>
          </div>
          <div v-if="selectedProject.topics?.length" style="margin: 12px 0;">
            <strong>Topics：</strong>
            <el-tag v-for="topic in selectedProject.topics" :key="topic" size="small" type="info" style="margin-right: 4px;">{{ topic }}</el-tag>
          </div>

          <!-- LLM Description -->
          <el-divider v-if="selectedProject.llm_description" />
          <div v-if="selectedProject.llm_description" style="margin: 12px 0;">
            <strong>项目描述</strong>
            <p style="color: #666;">{{ selectedProject.llm_description }}</p>
          </div>
          <div v-if="selectedProject.llm_scenarios" style="margin: 12px 0;">
            <strong>适用场景</strong>
            <p style="color: #666; white-space: pre-line;">{{ selectedProject.llm_scenarios }}</p>
          </div>

          <!-- Evaluation -->
          <template v-if="selectedProject.latest_evaluation">
            <el-divider />
            <h4>评估信息</h4>
            <el-row :gutter="8">
              <el-col :span="8">
                <el-statistic title="相关性" :value="(selectedProject.latest_evaluation as Record<string, unknown>).relevance_score ?? '-'" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="可试用性" :value="(selectedProject.latest_evaluation as Record<string, unknown>).trialability_score ?? '-'" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="业务价值" :value="(selectedProject.latest_evaluation as Record<string, unknown>).value_score ?? '-'" />
              </el-col>
            </el-row>
            <div style="margin-top: 8px;">
              <el-tag :type="statusColors[(selectedProject.latest_evaluation as Record<string, unknown>).decision as string] || 'info'">
                决策: {{ (selectedProject.latest_evaluation as Record<string, unknown>).decision }}
              </el-tag>
              <span v-if="(selectedProject.latest_evaluation as Record<string, unknown>).recommendation_score" style="margin-left: 8px;">
                推荐分: {{ (selectedProject.latest_evaluation as Record<string, unknown>).recommendation_score }}/5
              </span>
            </div>
            <p v-if="(selectedProject.latest_evaluation as Record<string, unknown>).decision_reason" style="color: #999; font-size: 12px; margin-top: 4px;">
              原因: {{ (selectedProject.latest_evaluation as Record<string, unknown>).decision_reason }}
            </p>
          </template>

          <!-- Trial Info -->
          <template v-if="selectedProject.active_trial">
            <el-divider />
            <h4>试用信息</h4>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="负责人">{{ (selectedProject.active_trial as Record<string, unknown>).owner }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="statusColors[(selectedProject.active_trial as Record<string, unknown>).status as string]" size="small">
                  {{ (selectedProject.active_trial as Record<string, unknown>).status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item v-if="(selectedProject.active_trial as Record<string, unknown>).due_date" label="截止日期">
                {{ (selectedProject.active_trial as Record<string, unknown>).due_date }}
              </el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- Actions -->
          <el-divider />
          <template v-if="selectedProject.active_trial">
            <el-alert type="info" :closable="false" :title="`已由 ${(selectedProject.active_trial as Record<string, unknown>).owner} 认领`" />
            <el-button style="margin-top: 8px;" @click="$router.push('/trials')">前往 Trials 管理</el-button>
          </template>
          <template v-else>
            <el-button type="primary" @click="handleClaim(selectedProject)">
              认领此项目
            </el-button>
          </template>
        </template>
      </div>
    </el-drawer>
  </div>
</template>
