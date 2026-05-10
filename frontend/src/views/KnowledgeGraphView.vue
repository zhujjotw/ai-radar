<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchTopicGraph, type TopicGraph } from '@/api/graph'

const graphData = ref<TopicGraph | null>(null)
const loading = ref(false)
const graphContainer = ref<HTMLDivElement>()

onMounted(async () => {
  loading.value = true
  try {
    graphData.value = await fetchTopicGraph()
  } finally {
    loading.value = false
  }

  // Render vis-network after data is loaded
  if (graphData.value && graphContainer.value) {
    const { Network, DataSet } = await import('vis-network')
    const nodes = new DataSet(
      graphData.value.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        group: n.group,
        title: n.title,
        color: n.color,
        size: n.size,
        shape: n.shape,
      }))
    )
    const edges = new DataSet(
      graphData.value.edges.map((e) => ({
        from: e.from,
        to: e.to,
        label: e.label,
        color: e.color,
      }))
    )
    new Network(graphContainer.value, { nodes, edges }, {
      physics: {
        solver: 'forceAtlas2Based',
        stabilization: true,
      },
      height: '500px',
    })
  }
})
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px;">Knowledge Graph</h2>
    <p style="color: #999; margin: 0 0 16px;">基于 GitHub Topics 的项目知识图谱</p>

    <!-- Stats -->
    <el-row :gutter="16" style="margin-bottom: 16px;" v-if="graphData">
      <el-col :span="8">
        <el-statistic title="项目数量" :value="graphData.stats.project_count" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="Topic 数量" :value="graphData.stats.topic_count" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="连接数量" :value="graphData.stats.edge_count" />
      </el-col>
    </el-row>

    <!-- Graph -->
    <div ref="graphContainer" v-loading="loading" style="border: 1px solid #e6e6e6; border-radius: 4px; min-height: 500px;" />

    <!-- Topic Distribution Chart -->
    <el-divider />
    <h3>Topic 分布</h3>
    <div v-if="graphData?.topic_distribution" style="height: 400px;">
      <!-- Simple bar chart with el-progress -->
      <div v-for="(count, topic) in graphData.topic_distribution" :key="topic" style="margin-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="width: 160px; text-align: right; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            {{ topic }}
          </span>
          <el-progress :percentage="Math.round((count / Math.max(...Object.values(graphData.topic_distribution))) * 100)"
                       :stroke-width="18"
                       :format="() => String(count)"
                       style="flex: 1;" />
        </div>
      </div>
    </div>
  </div>
</template>
