<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { fetchTopicGraph, type TopicGraph } from '@/api/graph'

const graphData = ref<TopicGraph | null>(null)
const loading = ref(false)
const graphContainer = ref<HTMLDivElement>()
const isFullscreen = ref(false)
let networkInstance: any = null

function resizeGraph() {
  if (networkInstance && graphContainer.value) {
    networkInstance.redraw()
  }
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  // Wait for CSS transition, then resize vis-network
  setTimeout(resizeGraph, 50)
  setTimeout(resizeGraph, 300)
}

onMounted(async () => {
  loading.value = true
  try {
    graphData.value = await fetchTopicGraph()
  } finally {
    loading.value = false
  }

  if (!graphData.value?.nodes.length) return

  await nextTick()
  if (!graphContainer.value) return

  const visNetwork = await import('vis-network')
  const visData = await import('vis-data')

  const nodes = new visData.DataSet<any>(
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
  const edges = new visData.DataSet<any>(
    graphData.value.edges.map((e) => ({
      from: e.from,
      to: e.to,
      label: e.label,
      color: e.color,
    }))
  )
  networkInstance = new visNetwork.Network(graphContainer.value, { nodes, edges }, {
    physics: {
      solver: 'forceAtlas2Based',
      stabilization: { iterations: 100 },
    },
    height: '100%',
    interaction: {
      hover: true,
      tooltipDelay: 200,
      navigationButtons: false,
      keyboard: true,
    },
  })
})
</script>

<template>
  <div :style="{
    position: isFullscreen ? 'fixed' : 'static',
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: isFullscreen ? 9999 : 'auto',
    background: isFullscreen ? '#fff' : 'transparent',
    padding: isFullscreen ? '16px' : '0',
    overflow: 'hidden',
    transition: 'all 0.3s ease',
  }">
    <!-- Fullscreen header -->
    <div v-if="isFullscreen" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <div>
        <h2 style="margin: 0;">Knowledge Graph</h2>
        <span v-if="graphData" style="color: #999; font-size: 13px;">
          {{ graphData.stats.project_count }} 个项目 · {{ graphData.stats.topic_count }} 个 Topic · {{ graphData.stats.edge_count }} 条连接
        </span>
      </div>
      <el-button @click="toggleFullscreen" :icon="isFullscreen ? 'Close' : 'FullScreen'">
        退出全屏
      </el-button>
    </div>

    <!-- Normal header -->
    <template v-if="!isFullscreen">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
        <div>
          <h2 style="margin: 0;">Knowledge Graph</h2>
          <p style="color: #999; margin: 4px 0 0;">按方向标签聚类的项目知识图谱</p>
        </div>
      </div>

      <el-row :gutter="16" style="margin-bottom: 16px;" v-if="graphData">
        <el-col :span="6">
          <el-statistic title="项目数量" :value="graphData.stats.project_count" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="方向数量" :value="graphData.stats.topic_count" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="连接数量" :value="graphData.stats.edge_count" />
        </el-col>
        <el-col :span="6" style="text-align: right;">
          <el-button type="primary" @click="toggleFullscreen">全屏查看</el-button>
        </el-col>
      </el-row>
    </template>

    <!-- Graph canvas -->
    <div
      ref="graphContainer"
      v-loading="loading"
      :style="{
        border: '1px solid #e6e6e6',
        borderRadius: '4px',
        height: isFullscreen ? 'calc(100vh - 80px)' : '600px',
      }"
    />

    <!-- Topic Distribution (hidden in fullscreen) -->
    <template v-if="!isFullscreen">
      <el-divider />
      <h3>方向分布</h3>
      <div v-if="graphData?.topic_distribution">
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
    </template>
  </div>
</template>
