import api from './client'

export interface GraphNode {
  id: string
  label: string
  group: string
  title: string
  color: string
  size: number
  shape: string
}

export interface GraphEdge {
  from: string
  to: string
  label: string
  color: string
}

export interface TopicGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: { project_count: number; topic_count: number; edge_count: number }
  topic_distribution: Record<string, number>
}

export async function fetchTopicGraph(): Promise<TopicGraph> {
  const { data } = await api.get<TopicGraph>('/graph/topic-graph')
  return data
}
