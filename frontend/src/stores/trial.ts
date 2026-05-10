import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as trialsApi from '@/api/trials'
import type { TrialItem } from '@/api/trials'

export const useTrialStore = defineStore('trial', () => {
  const trials = ref<TrialItem[]>([])
  const loading = ref(false)
  const filters = ref({ status: '', owner: '' })

  async function fetchTrials() {
    loading.value = true
    try {
      const params: Record<string, string> = {}
      if (filters.value.status) params.status = filters.value.status
      if (filters.value.owner) params.owner = filters.value.owner
      trials.value = await trialsApi.fetchTrials(params)
    } finally {
      loading.value = false
    }
  }

  async function transitionTrial(id: number, req: Parameters<typeof trialsApi.transitionTrial>[1]) {
    await trialsApi.transitionTrial(id, req)
    await fetchTrials()
  }

  async function updateTrial(id: number, req: Record<string, string | null>) {
    await trialsApi.updateTrial(id, req)
    await fetchTrials()
  }

  return { trials, loading, filters, fetchTrials, transitionTrial, updateTrial }
})
