<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTrialStore } from '@/stores/trial'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchTransitions, fetchStatuses } from '@/api/trials'

const router = useRouter()
const store = useTrialStore()

const statusOptions = ref<{ value: string; label: string }[]>([])

// Status color map (Element Plus tag types)
const statusColors: Record<string, string> = {
  claimed: '',
  running: 'warning',
  blocked: 'danger',
  demo_done: 'success',
  shared: '',
  dropped: 'info',
}

// Primary action per status
const primaryActions: Record<string, { label: string; target: string; type: string }> = {
  claimed: { label: '开始试用', target: 'running', type: 'primary' },
  running: { label: 'Demo 完成', target: 'demo_done', type: 'success' },
  blocked: { label: '恢复试用', target: 'running', type: 'primary' },
  demo_done: { label: '分享', target: 'shared', type: 'primary' },
  dropped: { label: '重新认领', target: 'claimed', type: 'primary' },
}

// Secondary actions per status (shown in dropdown)
const secondaryActions: Record<string, { label: string; target: string; needsDialog: boolean }[]> = {
  claimed: [
    { label: '放弃', target: 'dropped', needsDialog: true },
  ],
  running: [
    { label: '标记阻塞', target: 'blocked', needsDialog: true },
    { label: '放弃', target: 'dropped', needsDialog: true },
  ],
  blocked: [
    { label: '放弃', target: 'dropped', needsDialog: true },
  ],
  demo_done: [
    { label: '放弃', target: 'dropped', needsDialog: true },
  ],
  dropped: [],
  shared: [],
}

// Dialog state
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogLoading = ref(false)
const dialogData = ref({
  trialId: 0,
  targetStatus: '',
  blockers: '',
  result_summary: '',
  drop_reason: '',
})
const dialogFields = ref<{ label: string; key: string; placeholder: string; required: boolean }[]>([])

// Expand row fields
interface RowFields {
  selected_target: string
  owner: string
  environment: string
  demo_url: string
  trial_notes: string
  result_summary: string
  next_action: string
}
const expandedFields = ref<Record<number, RowFields>>({})

function initExpandFields(trialId: number, row: Record<string, unknown>) {
  expandedFields.value = {
    ...expandedFields.value,
    [trialId]: {
      selected_target: '',
      owner: (row.owner as string) || '',
      environment: (row.environment as string) || '',
      demo_url: (row.demo_url as string) || '',
      trial_notes: (row.trial_notes as string) || '',
      result_summary: (row.result_summary as string) || '',
      next_action: (row.next_action as string) || '',
    },
  }
}

function handleExpand(row: Record<string, unknown>, expanded: boolean) {
  if (expanded) {
    initExpandFields(row.id as number, row)
  }
}

// Primary action: direct transition (no extra fields needed)
async function handlePrimary(row: { id: number; status: string; project_name: string | null }) {
  const action = primaryActions[row.status]
  if (!action) return

  if (action.target === 'shared') {
    // Navigate to shares page
    router.push('/shares')
    return
  }

  // demo_done needs result_summary, open dialog
  if (action.target === 'demo_done') {
    openDialog(row.id, action.target, row.project_name)
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将 "${row.project_name}" 状态从 ${row.status} 改为 ${action.target}?`,
      action.label,
      { type: 'info', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
    await store.transitionTrial(row.id, { target_status: action.target })
    ElMessage.success(`状态已更新为 ${action.target}`)
  } catch {
    // cancelled or error
  }
}

// Secondary action: open dialog for extra fields
function openDialog(trialId: number, targetStatus: string, projectName: string | null) {
  dialogData.value = {
    trialId,
    targetStatus,
    blockers: '',
    result_summary: '',
    drop_reason: '',
  }

  const fields: { label: string; key: string; placeholder: string; required: boolean }[] = []
  const titleMap: Record<string, string> = {
    blocked: '标记阻塞',
    demo_done: 'Demo 完成',
    dropped: '放弃试用',
  }
  dialogTitle.value = `${titleMap[targetStatus] || targetStatus} — ${projectName || ''}`

  if (targetStatus === 'blocked') {
    fields.push({ label: '阻塞原因', key: 'blockers', placeholder: '描述阻塞原因（必填）', required: true })
  } else if (targetStatus === 'demo_done') {
    fields.push({ label: '结果摘要', key: 'result_summary', placeholder: '描述试用结果和结论（必填）', required: true })
  } else if (targetStatus === 'dropped') {
    fields.push({ label: '放弃原因', key: 'drop_reason', placeholder: '可选：为什么放弃', required: false })
  }

  dialogFields.value = fields
  dialogVisible.value = true
}

async function handleDialogConfirm() {
  const d = dialogData.value
  // Validate required fields
  for (const f of dialogFields.value) {
    if (f.required && !d[f.key as keyof typeof d]?.trim()) {
      ElMessage.warning(`请填写${f.label}`)
      return
    }
  }

  dialogLoading.value = true
  try {
    await store.transitionTrial(d.trialId, {
      target_status: d.targetStatus,
      blockers: d.blockers || undefined,
      result_summary: d.result_summary || undefined,
      drop_reason: d.drop_reason || undefined,
    })
    ElMessage.success(`状态已更新为 ${d.targetStatus}`)
    dialogVisible.value = false
  } finally {
    dialogLoading.value = false
  }
}

async function handleSaveDetail(trialId: number) {
  const fields = expandedFields.value[trialId]
  if (!fields) return
  try {
    await store.updateTrial(trialId, {
      owner: fields.owner || null,
      environment: fields.environment || null,
      demo_url: fields.demo_url || null,
      trial_notes: fields.trial_notes || null,
      result_summary: fields.result_summary || null,
      next_action: fields.next_action || null,
    })
    ElMessage.success('已保存')
  } catch {
    // handled by interceptor
  }
}

onMounted(async () => {
  const statuses = await fetchStatuses()
  statusOptions.value = Object.entries(statuses).map(([key, val]) => ({
    value: key,
    label: `${(val as Record<string, string>).emoji} ${(val as Record<string, string>).label}`,
  }))
  statusOptions.value.unshift({ value: '', label: 'All' })
  store.fetchTrials()
})
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px;">Trials</h2>
    <p style="color: #999; margin: 0 0 16px;">Claim projects for trial, track progress, and record outcomes</p>

    <!-- Filters -->
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-select v-model="store.filters.status" @change="store.fetchTrials()" style="width: 100%;">
          <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-input v-model="store.filters.owner" placeholder="Owner" clearable @clear="store.fetchTrials()" @keyup.enter="store.fetchTrials()" />
      </el-col>
      <el-col :span="12" style="text-align: right; color: #999;">
        Showing {{ store.trials.length }} trial(s)
      </el-col>
    </el-row>

    <!-- Table -->
    <el-table :data="store.trials" v-loading="store.loading" stripe row-key="id"
              @expand-change="handleExpand">
      <!-- Expand: detail editing -->
      <el-table-column type="expand">
        <template #default="{ row }">
          <div style="padding: 16px;">
            <h4>Trial Details</h4>
            <el-form label-width="100px" size="small">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="Owner">
                    <el-input v-model="expandedFields[row.id].owner" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="Environment">
                    <el-input v-model="expandedFields[row.id].environment" placeholder="试用环境" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="Demo URL">
                    <el-input v-model="expandedFields[row.id].demo_url" placeholder="演示链接" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="Next Action">
                    <el-input v-model="expandedFields[row.id].next_action" placeholder="下一步行动" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="Notes">
                <el-input v-model="expandedFields[row.id].trial_notes" type="textarea" :rows="2" placeholder="试用笔记" />
              </el-form-item>
              <el-form-item label="Result">
                <el-input v-model="expandedFields[row.id].result_summary" type="textarea" :rows="2" placeholder="试用结论" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" size="small" @click="handleSaveDetail(row.id)">Save Details</el-button>
              </el-form-item>
            </el-form>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="project_name" label="Project" min-width="180" />
      <el-table-column prop="owner" label="Owner" width="120" />
      <el-table-column label="Status" width="130">
        <template #default="{ row }">
          <el-tag :type="statusColors[row.status] || 'info'" size="small" effect="dark">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Due Date" width="120">
        <template #default="{ row }">
          {{ row.due_date || '-' }}
        </template>
      </el-table-column>

      <!-- Actions column -->
      <el-table-column label="Actions" width="220" fixed="right">
        <template #default="{ row }">
          <div v-if="primaryActions[row.status]" style="display: flex; align-items: center; gap: 4px;">
            <!-- Primary action button -->
            <el-button
              :type="(primaryActions[row.status]?.type as any) || 'primary'"
              size="small"
              @click="handlePrimary(row)"
            >
              {{ primaryActions[row.status]?.label }}
            </el-button>

            <!-- Secondary actions dropdown -->
            <el-dropdown v-if="secondaryActions[row.status]?.length" trigger="click"
                         @command="(cmd: string) => openDialog(row.id, cmd, row.project_name)">
              <el-button size="small">
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="action in secondaryActions[row.status]"
                    :key="action.target"
                    :command="action.target"
                  >
                    {{ action.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <el-tag v-else-if="row.status === 'shared'" type="success" size="small">已完成</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog for transitions requiring extra fields -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px">
      <el-form label-width="80px">
        <el-form-item
          v-for="f in dialogFields"
          :key="f.key"
          :label="f.label"
          :required="f.required"
        >
          <el-input
            v-model="dialogData[f.key as keyof typeof dialogData]"
            type="textarea"
            :rows="3"
            :placeholder="f.placeholder"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleDialogConfirm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
