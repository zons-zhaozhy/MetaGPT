<template>
  <div class="phase-manager">
    <h2>项目阶段管理</h2>
    
    <el-card class="phase-container" shadow="hover">
      <div class="phase-header">
        <h3>项目阶段</h3>
        <el-tag v-if="currentProject">当前项目: {{ currentProject.name }}</el-tag>
      </div>
      
      <el-steps :active="activePhaseIndex" finish-status="success" process-status="process" align-center>
        <el-step 
          v-for="phase in phases" 
          :key="phase.phase_id" 
          :title="phaseNames[phase.phase_id] || phase.phase_id"
          :status="getPhaseStatus(phase)"
        >
          <template #icon>
            <el-badge v-if="phase.retry_count > 0" :value="phase.retry_count" type="warning">
              <el-icon v-if="phase.status === 'completed'"><Check /></el-icon>
              <el-icon v-else-if="phase.status === 'running'"><Loading /></el-icon>
              <el-icon v-else-if="phase.status === 'failed'"><Close /></el-icon>
              <el-icon v-else><More /></el-icon>
            </el-badge>
            <span v-else>
              <el-icon v-if="phase.status === 'completed'"><Check /></el-icon>
              <el-icon v-else-if="phase.status === 'running'"><Loading /></el-icon>
              <el-icon v-else-if="phase.status === 'failed'"><Close /></el-icon>
              <el-icon v-else><More /></el-icon>
            </span>
          </template>
        </el-step>
      </el-steps>
      
      <div class="phase-controls">
        <div v-if="currentPhase" class="current-phase-details">
          <h4>{{ phaseNames[currentPhase.phase_id] || currentPhase.phase_id }}</h4>
          <p v-if="currentPhase.started_at">开始时间: {{ formatDate(currentPhase.started_at) }}</p>
          <p v-if="currentPhase.completed_at">完成时间: {{ formatDate(currentPhase.completed_at) }}</p>
          <el-tag :type="getTagType(currentPhase.status)">{{ getStatusText(currentPhase.status) }}</el-tag>
        </div>
        
        <div class="phase-actions">
          <el-button 
            v-if="canExecutePhase" 
            type="primary" 
            @click="executePhase" 
            :loading="isExecuting"
          >
            执行当前阶段
          </el-button>
          
          <el-button 
            v-if="canPausePhase" 
            type="warning" 
            @click="pausePhase" 
            :loading="isPausing"
          >
            暂停执行
          </el-button>
          
          <el-button 
            v-if="canResumePhase" 
            type="success" 
            @click="resumePhase" 
            :loading="isResuming"
          >
            继续执行
          </el-button>
          
          <el-button 
            v-if="canSkipPhase" 
            type="info" 
            @click="confirmSkipPhase"
          >
            跳过阶段
          </el-button>
          
          <el-button 
            v-if="canAbortPhase" 
            type="danger" 
            @click="confirmAbortPhase"
          >
            终止执行
          </el-button>
        </div>
      </div>
      
      <div v-if="currentPhase && currentPhase.artifacts && currentPhase.artifacts.length > 0" class="phase-artifacts">
        <h4>阶段产物</h4>
        <el-table :data="currentPhase.artifacts" stripe style="width: 100%">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="type" label="类型">
            <template #default="scope">
              <el-tag :type="getArtifactTypeTag(scope.row.type)">{{ scope.row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="scope">
              <el-button type="primary" size="small" @click="viewArtifact(scope.row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
    
    <!-- 用于确认操作的对话框 -->
    <el-dialog
      v-model="confirmDialogVisible"
      :title="confirmDialogTitle"
      width="30%"
    >
      <span>{{ confirmDialogMessage }}</span>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="confirmDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleConfirmAction">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 用于查看产物的对话框 -->
    <el-dialog
      v-model="artifactDialogVisible"
      :title="selectedArtifact ? selectedArtifact.name : '查看产物'"
      width="80%"
    >
      <div v-if="selectedArtifact" class="artifact-viewer">
        <pre v-if="artifactContent" class="artifact-content">{{ artifactContent }}</pre>
        <img v-else-if="isImageArtifact" :src="getArtifactUrl(selectedArtifact)" alt="图像产物" />
        <div v-else class="artifact-loading">
          <el-icon><Loading /></el-icon> 加载中...
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { Check, Loading, Close, More } from '@element-plus/icons-vue'
import axios from 'axios'

export default {
  name: 'PhaseManager',
  components: {
    Check, Loading, Close, More
  },
  props: {
    projectId: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const phases = ref([])
    const currentProject = ref(null)
    const isExecuting = ref(false)
    const isPausing = ref(false)
    const isResuming = ref(false)
    const confirmDialogVisible = ref(false)
    const confirmDialogTitle = ref('')
    const confirmDialogMessage = ref('')
    const confirmAction = ref(null)
    const artifactDialogVisible = ref(false)
    const selectedArtifact = ref(null)
    const artifactContent = ref(null)
    
    const phaseNames = {
      'requirement_analysis': '需求分析',
      'architecture_design': '架构设计',
      'implementation': '编码实现',
      'testing': '测试验证',
      'deployment': '部署交付'
    }
    
    // 当前活跃阶段
    const activePhaseIndex = computed(() => {
      const index = phases.value.findIndex(p => p.status === 'running' || p.status === 'paused')
      if (index >= 0) return index
      
      // 如果没有运行中或暂停的阶段，找第一个未完成的阶段
      const pendingIndex = phases.value.findIndex(p => p.status === 'pending')
      if (pendingIndex >= 0) return pendingIndex
      
      // 如果所有阶段都完成了，返回最后一个阶段
      return phases.value.length - 1
    })
    
    // 当前阶段
    const currentPhase = computed(() => {
      if (activePhaseIndex.value >= 0 && activePhaseIndex.value < phases.value.length) {
        return phases.value[activePhaseIndex.value]
      }
      return null
    })
    
    // 是否可以执行当前阶段
    const canExecutePhase = computed(() => {
      return currentPhase.value && 
             (currentPhase.value.status === 'pending' || 
              currentPhase.value.status === 'failed' || 
              currentPhase.value.can_retry)
    })
    
    // 是否可以暂停当前阶段
    const canPausePhase = computed(() => {
      return currentPhase.value && currentPhase.value.status === 'running'
    })
    
    // 是否可以继续当前阶段
    const canResumePhase = computed(() => {
      return currentPhase.value && currentPhase.value.status === 'paused'
    })
    
    // 是否可以跳过当前阶段
    const canSkipPhase = computed(() => {
      return currentPhase.value && 
             (currentPhase.value.status === 'pending' || 
              currentPhase.value.status === 'failed')
    })
    
    // 是否可以终止当前阶段
    const canAbortPhase = computed(() => {
      return currentPhase.value && 
             (currentPhase.value.status === 'running' || 
              currentPhase.value.status === 'paused')
    })
    
    // 是否是图片类型的产物
    const isImageArtifact = computed(() => {
      if (!selectedArtifact.value) return false
      const name = selectedArtifact.value.name.toLowerCase()
      return name.endsWith('.png') || name.endsWith('.jpg') || 
             name.endsWith('.jpeg') || name.endsWith('.gif') || 
             name.endsWith('.svg')
    })
    
    // 加载项目阶段
    const loadPhases = async () => {
      try {
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.get(`/api/projects/${props.projectId}/phases`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        
        if (response.data && response.data.phases) {
          phases.value = response.data.phases
        }
      } catch (error) {
        console.error('加载项目阶段失败:', error)
      }
    }
    
    // 加载项目信息
    const loadProjectInfo = async () => {
      try {
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.get(`/api/projects/${props.projectId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        
        if (response.data) {
          currentProject.value = response.data
        }
      } catch (error) {
        console.error('加载项目信息失败:', error)
      }
    }
    
    // 执行当前阶段
    const executePhase = async () => {
      if (!currentPhase.value) return
      
      try {
        isExecuting.value = true
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/execute/${currentPhase.value.phase_id}`,
          { action: 'execute' },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.status === 'started') {
          // 更新状态
          currentPhase.value.status = 'running'
          currentPhase.value.started_at = new Date().toISOString()
        }
      } catch (error) {
        console.error('执行阶段失败:', error)
      } finally {
        isExecuting.value = false
      }
    }
    
    // 暂停当前阶段
    const pausePhase = async () => {
      if (!currentPhase.value) return
      
      try {
        isPausing.value = true
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/execute/${currentPhase.value.phase_id}`,
          { action: 'pause' },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.status === 'paused') {
          // 更新状态
          currentPhase.value.status = 'paused'
        }
      } catch (error) {
        console.error('暂停阶段失败:', error)
      } finally {
        isPausing.value = false
      }
    }
    
    // 继续当前阶段
    const resumePhase = async () => {
      if (!currentPhase.value) return
      
      try {
        isResuming.value = true
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/execute/${currentPhase.value.phase_id}`,
          { action: 'resume' },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.status === 'resumed') {
          // 更新状态
          currentPhase.value.status = 'running'
        }
      } catch (error) {
        console.error('继续阶段失败:', error)
      } finally {
        isResuming.value = false
      }
    }
    
    // 跳过当前阶段
    const skipPhase = async () => {
      if (!currentPhase.value) return
      
      try {
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/execute/${currentPhase.value.phase_id}`,
          { action: 'skip' },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.status === 'skipped') {
          // 更新状态
          currentPhase.value.status = 'skipped'
          currentPhase.value.completed_at = new Date().toISOString()
          
          // 重新加载阶段
          await loadPhases()
        }
      } catch (error) {
        console.error('跳过阶段失败:', error)
      }
    }
    
    // 终止当前阶段
    const abortPhase = async () => {
      if (!currentPhase.value) return
      
      try {
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/execute/${currentPhase.value.phase_id}`,
          { action: 'abort' },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.status === 'aborted') {
          // 更新状态
          currentPhase.value.status = 'aborted'
          currentPhase.value.completed_at = new Date().toISOString()
        }
      } catch (error) {
        console.error('终止阶段失败:', error)
      }
    }
    
    // 确认跳过阶段
    const confirmSkipPhase = () => {
      confirmDialogTitle.value = '确认跳过阶段'
      confirmDialogMessage.value = `确定要跳过 "${phaseNames[currentPhase.value.phase_id] || currentPhase.value.phase_id}" 阶段吗？`
      confirmAction.value = skipPhase
      confirmDialogVisible.value = true
    }
    
    // 确认终止阶段
    const confirmAbortPhase = () => {
      confirmDialogTitle.value = '确认终止执行'
      confirmDialogMessage.value = `确定要终止 "${phaseNames[currentPhase.value.phase_id] || currentPhase.value.phase_id}" 阶段的执行吗？`
      confirmAction.value = abortPhase
      confirmDialogVisible.value = true
    }
    
    // 处理确认操作
    const handleConfirmAction = () => {
      if (confirmAction.value) {
        confirmAction.value()
      }
      confirmDialogVisible.value = false
    }
    
    // 查看产物
    const viewArtifact = async (artifact) => {
      selectedArtifact.value = artifact
      artifactContent.value = null
      artifactDialogVisible.value = true
      
      if (!isImageArtifact.value) {
        try {
          const token = localStorage.getItem('token')
          if (!token) return
          
          // 这里假设后端提供了一个获取产物内容的API
          // 实际上可能需要调整，根据实际的API设计
          const response = await axios.get(`/api/projects/${props.projectId}/artifacts/${artifact.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          })
          
          if (response.data && response.data.content) {
            artifactContent.value = response.data.content
          }
        } catch (error) {
          console.error('加载产物内容失败:', error)
          artifactContent.value = '无法加载内容'
        }
      }
    }
    
    // 获取产物URL
    const getArtifactUrl = (artifact) => {
      return `/api/projects/${props.projectId}/artifacts/${artifact.id}/view`
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 获取阶段状态
    const getPhaseStatus = (phase) => {
      if (phase.status === 'completed') return 'success'
      if (phase.status === 'running') return 'process'
      if (phase.status === 'failed' || phase.status === 'aborted') return 'error'
      if (phase.status === 'paused') return 'warning'
      return 'wait'
    }
    
    // 获取状态标签类型
    const getTagType = (status) => {
      if (status === 'completed') return 'success'
      if (status === 'running') return 'primary'
      if (status === 'failed' || status === 'aborted') return 'danger'
      if (status === 'paused') return 'warning'
      if (status === 'skipped') return 'info'
      return ''
    }
    
    // 获取状态文本
    const getStatusText = (status) => {
      const statusMap = {
        'pending': '等待执行',
        'running': '执行中',
        'completed': '已完成',
        'failed': '执行失败',
        'paused': '已暂停',
        'skipped': '已跳过',
        'aborted': '已终止'
      }
      return statusMap[status] || status
    }
    
    // 获取产物类型标签
    const getArtifactTypeTag = (type) => {
      const typeMap = {
        'document': 'info',
        'code': 'success',
        'image': 'warning'
      }
      return typeMap[type] || ''
    }
    
    // 定期刷新数据
    let refreshInterval = null
    
    const startRefreshing = () => {
      refreshInterval = setInterval(async () => {
        if (currentPhase.value && currentPhase.value.status === 'running') {
          await loadPhases()
        }
      }, 5000) // 每5秒刷新一次
    }
    
    const stopRefreshing = () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
        refreshInterval = null
      }
    }
    
    // 监听项目ID变化
    watch(() => props.projectId, async () => {
      if (props.projectId) {
        await loadProjectInfo()
        await loadPhases()
      }
    })
    
    // 组件挂载时加载数据
    onMounted(async () => {
      if (props.projectId) {
        await loadProjectInfo()
        await loadPhases()
        startRefreshing()
      }
    })
    
    // 组件卸载时清理
    const beforeUnmount = () => {
      stopRefreshing()
    }
    
    return {
      phases,
      currentProject,
      currentPhase,
      activePhaseIndex,
      isExecuting,
      isPausing,
      isResuming,
      confirmDialogVisible,
      confirmDialogTitle,
      confirmDialogMessage,
      artifactDialogVisible,
      selectedArtifact,
      artifactContent,
      phaseNames,
      canExecutePhase,
      canPausePhase,
      canResumePhase,
      canSkipPhase,
      canAbortPhase,
      isImageArtifact,
      executePhase,
      pausePhase,
      resumePhase,
      confirmSkipPhase,
      confirmAbortPhase,
      handleConfirmAction,
      viewArtifact,
      getArtifactUrl,
      formatDate,
      getPhaseStatus,
      getTagType,
      getStatusText,
      getArtifactTypeTag,
      beforeUnmount
    }
  }
}
</script>

<style scoped>
.phase-manager {
  margin: 20px 0;
}

.phase-container {
  margin: 20px 0;
}

.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.phase-controls {
  margin: 20px 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.current-phase-details {
  flex: 1;
}

.phase-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.phase-artifacts {
  margin-top: 20px;
}

.artifact-viewer {
  min-height: 200px;
  max-height: 600px;
  overflow: auto;
}

.artifact-content {
  white-space: pre-wrap;
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
}

.artifact-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}
</style> 