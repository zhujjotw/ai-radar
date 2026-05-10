import api from './client'

export interface TrialItem {
  id: number
  project_id: number
  owner: string
  status: string
  claimed_at: string | null
  due_date: string | null
  environment: string | null
  demo_url: string | null
  trial_notes: string | null
  blockers: string | null
  result_summary: string | null
  next_action: string | null
  project_name: string | null
}

export async function fetchTrials(params?: Record<string, string>): Promise<TrialItem[]> {
  const { data } = await api.get<TrialItem[]>('/trials', { params })
  return data
}

export async function fetchTrial(id: number): Promise<TrialItem> {
  const { data } = await api.get<TrialItem>(`/trials/${id}`)
  return data
}

export async function transitionTrial(id: number, req: {
  target_status: string
  blockers?: string
  result_summary?: string
  drop_reason?: string
}): Promise<TrialItem> {
  const { data } = await api.post<TrialItem>(`/trials/${id}/transition`, req)
  return data
}

export async function updateTrial(id: number, req: Record<string, string | null>): Promise<TrialItem> {
  const { data } = await api.put<TrialItem>(`/trials/${id}`, req)
  return data
}

export async function fetchTransitions(status: string): Promise<{ target: string; label: string; description: string }[]> {
  const { data } = await api.get('/trials/transitions', { params: { status } })
  return data
}

export async function fetchStatuses(): Promise<Record<string, { emoji: string; color: string; label: string }>> {
  const { data } = await api.get('/trials/statuses')
  return data
}
