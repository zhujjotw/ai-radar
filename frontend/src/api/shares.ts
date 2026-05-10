import api from './client'

export interface ShareItem {
  id: number
  trial_id: number
  title: string
  summary: string | null
  key_findings: string | null
  reusable_patterns: string | null
  applicable_scenarios: string | null
  knowledge_doc_url: string | null
  shared_at: string | null
  shared_by: string | null
  project_name: string | null
}

export async function fetchShares(sharedBy?: string): Promise<ShareItem[]> {
  const { data } = await api.get<ShareItem[]>('/shares', { params: sharedBy ? { shared_by: sharedBy } : {} })
  return data
}

export async function createShare(req: {
  trial_id: number
  title: string
  summary?: string
  key_findings?: string
  reusable_patterns?: string
  applicable_scenarios?: string
  knowledge_doc_url?: string
  shared_by?: string
}): Promise<ShareItem> {
  const { data } = await api.post<ShareItem>('/shares', req)
  return data
}

export async function fetchReadyTrials(): Promise<{ trial_id: number; project_name: string; owner: string; result_summary: string | null }[]> {
  const { data } = await api.get('/shares/ready-trials')
  return data
}

export async function fetchShareMarkdown(id: number): Promise<string> {
  const { data } = await api.get(`/shares/${id}/markdown`)
  return data.markdown
}
