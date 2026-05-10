import api from './client'

export interface ProjectListItem {
  id: number
  name: string
  github_url: string
  repo_full_name: string
  description: string | null
  pool: string
  source: string
  stars: number
  forks: number
  open_issues: number
  language: string | null
  tags: string[]
  topics: string[]
  license: string | null
  filter_status: string
  last_pushed_at: string | null
  first_seen_at: string | null
  llm_description: string | null
  llm_scenarios: string | null
  latest_evaluation: Record<string, unknown> | null
  active_trial: Record<string, unknown> | null
  owner: string
}

export interface ProjectDetail extends ProjectListItem {
  source_url: string | null
  discovered_reason: string | null
  has_quickstart: boolean
  readme_summary: string | null
  filter_reason: string | null
}

export async function fetchProjects(params?: Record<string, string | boolean | number>): Promise<ProjectListItem[]> {
  const { data } = await api.get<ProjectListItem[]>('/projects', { params })
  return data
}

export async function fetchProject(id: number): Promise<ProjectDetail> {
  const { data } = await api.get<ProjectDetail>(`/projects/${id}`)
  return data
}

export async function fetchTags(): Promise<string[]> {
  const { data } = await api.get<string[]>('/projects/tags')
  return data
}

export async function claimProject(id: number): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(`/projects/${id}/claim`)
  return data
}
