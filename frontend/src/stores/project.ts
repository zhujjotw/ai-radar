import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as projectsApi from '@/api/projects'
import type { ProjectListItem } from '@/api/projects'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<ProjectListItem[]>([])
  const allTags = ref<string[]>([])
  const loading = ref(false)
  const filters = ref({
    tag: '',
    order_by: 'recommendation_sort',
  })

  async function fetchProjects() {
    loading.value = true
    try {
      const params: Record<string, string> = {}
      if (filters.value.tag) params.tag = filters.value.tag
      params.order_by = filters.value.order_by
      projects.value = await projectsApi.fetchProjects(params)
    } finally {
      loading.value = false
    }
  }

  async function fetchTags() {
    allTags.value = await projectsApi.fetchTags()
  }

  async function claimProject(id: number) {
    await projectsApi.claimProject(id)
    await fetchProjects()
  }

  return { projects, allTags, loading, filters, fetchProjects, fetchTags, claimProject }
})
