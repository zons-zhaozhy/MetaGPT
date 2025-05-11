<template>
  <div class="project-detail">
    <!-- WebSocket连接状态指示器 -->
    <div class="websocket-status-indicator">
      <div :class="['status-dot', socketConnected ? 'connected' : 'disconnected']" 
           :title="socketConnected ? '实时连接已建立' : '实时连接已断开'"></div>
      <span>实时状态</span>
    </div>
    
    <div v-if="isLoading" class="loading-container">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <span>加载项目中...</span>
    </div>
    
    <div v-else-if="!project" class="not-found">
      <el-empty description="项目未找到"></el-empty>
      <el-button type="primary" @click="goBack">返回项目列表</el-button>
    </div>
    
    <div v-else class="project-container">
      <div class="project-header">
        <div class="project-title">
          <h1>{{ project.name }}</h1>
          <el-tag :type="getStatusType(project.status)">{{ project.status }}</el-tag>
          <el-tag v-if="isProcessing" type="warning">MetaGPT处理中...</el-tag>
          <el-tag v-if="!socketConnected" type="danger" class="socket-status">实时连接断开</el-tag>
          <el-tooltip v-if="!socketConnected" content="实时更新已断开，将使用轮询获取最新状态" placement="top">
            <el-icon class="ml-2"><WarningFilled /></el-icon>
          </el-tooltip>
        </div>
        
        <div class="project-actions">
          <el-button @click="goBack">返回列表</el-button>
          <el-button type="primary" @click="downloadProject">下载项目</el-button>
        </div>
      </div>
      
      <div v-if="isProcessing" class="processing-notification">
        <el-alert
          title="MetaGPT正在处理您的需求"
          type="info"
          description="处理大型项目可能需要几分钟时间，请耐心等待。您可以查看智能体日志获取实时进度。"
          :closable="false"
          show-icon
        >
          <template #default>
            <el-button type="primary" size="small" @click="activeTab = 'logs'">
              查看处理日志
            </el-button>
          </template>
        </el-alert>
      </div>
      
      <el-tabs v-model="activeTab" class="project-tabs">
        <el-tab-pane label="需求澄清" name="clarification">
          <requirement-clarifier 
            :project-id="projectId" 
            @clarification-complete="onClarificationComplete"
          />
        </el-tab-pane>
        
        <el-tab-pane label="阶段管理" name="phases">
          <phase-manager :project-id="projectId" />
        </el-tab-pane>
        
        <el-tab-pane label="智能体日志" name="logs">
          <agent-logs :project-id="projectId" />
        </el-tab-pane>
        
        <el-tab-pane label="文件查看" name="files">
          <project-files :project-id="projectId" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import io from 'socket.io-client'
import RequirementClarifier from '../components/RequirementClarifier.vue'
import PhaseManager from '../components/PhaseManager.vue'
import AgentLogs from '../components/AgentLogs.vue'
import ProjectFiles from '../components/ProjectFiles.vue'

export default {
  name: 'ProjectDetail',
  components: {
    Loading,
    WarningFilled,
    RequirementClarifier,
    PhaseManager,
    AgentLogs,
    ProjectFiles
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const projectId = ref(route.params.id)
    const project = ref(null)
    const isLoading = ref(true)
    const activeTab = ref('clarification')
    const socketConnected = ref(false)
    const socket = ref(null)
    const lastPollingTime = ref(0)
    const statusPollingInterval = ref(null)
    
    const isProcessing = computed(() => {
      if (!project.value) return false;
      return ['pending', '需求分析中', '架构设计中', '编码实现中', '测试验证中', '执行中'].includes(project.value.status);
    });
    
    const initSocketConnection = () => {
      // 清理旧的连接
      if (socket.value) {
        // 确保移除所有旧的监听器
        socket.value.off('connect');
        socket.value.off('connect_error');
        socket.value.off('disconnect');
        socket.value.off('joined');
        socket.value.off('agent_log');
        socket.value.off('error');
        
        socket.value.disconnect();
        socket.value = null;
      }
      
      try {
        // 明确指定后端Socket.IO服务地址
        const socketUrl = process.env.NODE_ENV === 'production' ? 
          window.location.origin : 
          'http://localhost:5001';
          
        console.log(`正在连接Socket.IO服务: ${socketUrl}`);
          
        socket.value = io(socketUrl, {
          path: '/socket.io/',
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 1000,
          timeout: 20000,
          withCredentials: true,
          transports: ['websocket', 'polling']
        });
        
        // 添加所有事件监听器
        socket.value.on('connect', () => {
          console.log('Socket.IO连接成功');
          socketConnected.value = true;
          
          // 加入项目房间
          socket.value.emit('join', { project_id: projectId.value });
          console.log(`尝试加入项目房间: ${projectId.value}`);
        });
        
        // 单独处理加入房间成功事件
        socket.value.on('joined', (data) => {
          console.log('成功加入项目房间:', data);
          ElMessage.success('实时连接已建立');
        });
        
        socket.value.on('connect_error', (error) => {
          console.error('Socket.IO连接错误:', error);
          socketConnected.value = false;
          ElMessage.warning('实时连接失败，将使用轮询获取状态');
          
          startStatusPolling();
        });
        
        socket.value.on('disconnect', () => {
          console.log('Socket.IO连接断开');
          socketConnected.value = false;
          
          startStatusPolling();
        });
        
        socket.value.on('agent_log', (data) => {
          console.log('收到智能体日志:', data);
          
          if (data.message_type === 'system' && activeTab.value !== 'logs') {
            ElMessage.info(`${data.agent_name}: ${data.message}`);
          }
          
          if (data.message_type === 'system' || data.message_type === 'artifact') {
            loadProject();
          }
        });
        
        // 添加错误处理
        socket.value.on('error', (error) => {
          console.error('Socket.IO错误:', error);
          ElMessage.error(`Socket.IO错误: ${error.message || '未知错误'}`);
        });
        
      } catch (error) {
        console.error('初始化Socket.IO连接失败:', error);
        socketConnected.value = false;
        
        startStatusPolling();
      }
    };
    
    const startStatusPolling = () => {
      if (statusPollingInterval.value) return;
      
      statusPollingInterval.value = setInterval(() => {
        const now = Date.now();
        if (now - lastPollingTime.value > 5000) {
          loadProject();
          lastPollingTime.value = now;
        }
      }, 5000);
    };
    
    const stopStatusPolling = () => {
      if (statusPollingInterval.value) {
        clearInterval(statusPollingInterval.value);
        statusPollingInterval.value = null;
      }
    };
    
    const loadProject = async () => {
      if (project.value === null) {
        isLoading.value = true;
      }
      
      const token = localStorage.getItem('token')
      if (!token) {
        router.push('/login')
        return
      }
      
      try {
        const response = await axios.get(`/api/projects/${projectId.value}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        
        if (response.data) {
          project.value = response.data
          
          if (!isLoading.value) {
            if (project.value.status === 'pending' || project.value.active_step === 0) {
              activeTab.value = 'clarification'
            } else if (isProcessing.value && activeTab.value !== 'logs') {
              ElMessage.info('MetaGPT正在处理您的需求，可以查看实时日志');
            }
          } else if (project.value.status === 'pending' || project.value.active_step === 0) {
            activeTab.value = 'clarification'
          } else {
            activeTab.value = 'phases'
          }
        }
      } catch (error) {
        console.error('加载项目信息失败:', error)
        
        if (error.response && error.response.status === 404) {
          project.value = {
            id: projectId.value,
            name: "项目不存在",
            status: "pending",
            active_step: 0,
            requirement: "请添加项目需求"
          }
          ElMessage.warning('项目不存在或已被删除，请检查项目ID')
        } else if (error.response && error.response.status === 401) {
          ElMessage.error('身份验证失败，请重新登录')
          setTimeout(() => {
            router.push('/login')
          }, 1500)
        } else {
          ElMessage.error('访问项目失败，正在重新尝试...')
          
          setTimeout(() => {
            loadProject()
          }, 1000)
        }
      } finally {
        isLoading.value = false
      }
    }
    
    const goBack = () => {
      router.push('/projects')
    }
    
    const downloadProject = async () => {
      const token = localStorage.getItem('token')
      if (!token) return
      
      const response = await axios.get(`/api/projects/${projectId.value}/download`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project.value.name}.zip`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      ElMessage.success('项目下载成功')
    }
    
    const onClarificationComplete = () => {
      activeTab.value = 'phases'
    }
    
    const getStatusType = (status) => {
      if (status === '已完成') return 'success'
      if (status === '需求分析中' || status === '架构设计中' || status === '编码实现中' || status === '测试验证中' || status === '执行中') return 'primary'
      if (status === '失败' || status === '执行出错') return 'danger'
      if (status === 'pending') return 'info'
      if (status === '已中断') return 'warning'
      return 'info' // 默认返回info类型而不是空字符串
    }
    
    onMounted(() => {
      loadProject();
      initSocketConnection();
    });
    
    onUnmounted(() => {
      stopStatusPolling();
      
      if (socket.value) {
        socket.value.disconnect();
        socket.value = null;
      }
    });
    
    return {
      projectId,
      project,
      isLoading,
      activeTab,
      socketConnected,
      isProcessing,
      goBack,
      downloadProject,
      onClarificationComplete,
      getStatusType
    }
  }
}
</script>

<style scoped>
.project-detail {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #909399;
}

.loading-icon {
  margin-right: 10px;
  font-size: 24px;
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 20px;
}

.project-container {
  margin-top: 20px;
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.project-title {
  display: flex;
  align-items: center;
  gap: 15px;
}

.socket-status {
  margin-left: 10px;
}

.processing-notification {
  margin-bottom: 20px;
}

.ml-2 {
  margin-left: 8px;
}

.project-tabs {
  margin-top: 20px;
}

/* 添加WebSocket状态指示器样式 */
.websocket-status-indicator {
  position: fixed;
  top: 70px;
  right: 20px;
  display: flex;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.9);
  padding: 5px 10px;
  border-radius: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 5px;
  transition: background-color 0.3s ease;
}

.status-dot.connected {
  background-color: #67C23A; /* 绿色 */
  box-shadow: 0 0 5px #67C23A;
}

.status-dot.disconnected {
  background-color: #F56C6C; /* 红色 */
  box-shadow: 0 0 5px #F56C6C;
}
</style> 