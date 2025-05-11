<template>
  <div class="project-phases">
    <el-card class="phase-card">
      <template #header>
        <div class="phase-header">
          <span>项目阶段控制</span>
          <el-button link @click="refreshPhases" :loading="loading">刷新</el-button>
        </div>
      </template>
      
      <el-steps :active="activeIndex" finish-status="success" :process-status="getCurrentStatus()">
        <el-step 
          v-for="phase in phases" 
          :key="phase.id" 
          :title="phase.name"
          :description="getPhaseDescription(phase)"
        />
      </el-steps>
      
      <div class="phase-control mt-20" v-if="currentPhase">
        <div class="current-phase-info">
          <h4>当前阶段: {{ currentPhase.name }}</h4>
          <p>{{ currentPhase.description }}</p>
          <el-tag v-if="phaseStatus" :type="getStatusType(phaseStatus)">
            {{ formatStatus(phaseStatus) }}
          </el-tag>
        </div>
        
        <div class="phase-actions mt-10">
          <el-button 
            type="primary" 
            @click="executePhase(currentPhase.id)"
            :loading="executing"
            :disabled="executing || isCompleted(currentPhase.id)"
          >
            {{ isCompleted(currentPhase.id) ? '已完成' : (isRunning(currentPhase.id) ? '执行中' : '执行此阶段') }}
          </el-button>
          
          <el-button 
            v-if="hasPreviousPhase"
            @click="selectPhase(previousPhaseIndex)"
            :disabled="executing"
          >
            上一阶段
          </el-button>
          
          <el-button 
            v-if="hasNextPhase"
            @click="selectPhase(nextPhaseIndex)"
            :disabled="executing"
          >
            下一阶段
          </el-button>
        </div>
      </div>
      
      <div class="phase-artifacts mt-20" v-if="phaseArtifacts && Object.keys(phaseArtifacts).length">
        <h4>阶段产物</h4>
        <el-table :data="artifactsList" stripe style="width: 100%">
          <el-table-column prop="phase" label="阶段" width="150" />
          <el-table-column prop="file" label="文件" />
          <el-table-column prop="timestamp" label="生成时间" width="180">
            <template #default="scope">
              {{ formatDate(scope.row.timestamp) }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'ProjectPhases',
  props: {
    projectId: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      phases: [],
      currentPhase: null,
      completedPhases: [],
      phaseArtifacts: {},
      phaseTimestamps: {},
      activeIndex: 0,
      loading: false,
      executing: false,
      statusInterval: null,
      phaseStatus: ''
    }
  },
  computed: {
    artifactsList() {
      const list = [];
      for (const phase in this.phaseArtifacts) {
        if (this.phases.find(p => p.id === phase)) {
          const phaseName = this.phases.find(p => p.id === phase).name;
          list.push({
            phase: phaseName,
            file: this.phaseArtifacts[phase],
            timestamp: this.phaseTimestamps[phase] || ''
          });
        }
      }
      return list;
    },
    previousPhaseIndex() {
      return Math.max(0, this.activeIndex - 1);
    },
    nextPhaseIndex() {
      return Math.min(this.phases.length - 1, this.activeIndex + 1);
    },
    hasPreviousPhase() {
      return this.activeIndex > 0;
    },
    hasNextPhase() {
      return this.activeIndex < this.phases.length - 1;
    }
  },
  created() {
    this.fetchPhases();
    this.startStatusInterval();
  },
  beforeUnmount() {
    this.stopStatusInterval();
  },
  methods: {
    async fetchPhases() {
      this.loading = true;
      try {
        const response = await this.$axios.get(`/api/projects/${this.projectId}/phases`);
        this.phases = response.data.phases || [];
        this.completedPhases = response.data.completed_phases || [];
        
        const currentPhaseId = response.data.current_phase;
        this.currentPhase = this.phases.find(p => p.id === currentPhaseId) || this.phases[0];
        
        this.activeIndex = this.phases.findIndex(p => p.id === currentPhaseId);
        if (this.activeIndex < 0) this.activeIndex = 0;
        
        // 同时获取项目状态，包括产物和时间戳
        await this.fetchStatus();
      } catch (error) {
        console.error('获取项目阶段失败', error);
        this.$message.error('获取项目阶段失败');
      } finally {
        this.loading = false;
      }
    },
    async fetchStatus() {
      try {
        const response = await this.$axios.get(`/api/projects/${this.projectId}/status`);
        this.phaseArtifacts = response.data.artifacts || {};
        this.phaseTimestamps = response.data.timestamps || {};
        this.completedPhases = response.data.phases_completed || [];
        
        // 更新当前阶段状态
        if (response.data.current_phase) {
          const currentPhaseId = response.data.current_phase;
          this.currentPhase = this.phases.find(p => p.id === currentPhaseId) || this.currentPhase;
          this.activeIndex = this.phases.findIndex(p => p.id === currentPhaseId);
          if (this.activeIndex < 0) this.activeIndex = 0;
        }
        
        // 更新阶段状态
        this.phaseStatus = response.data.status;
      } catch (error) {
        console.error('获取项目状态失败', error);
      }
    },
    refreshPhases() {
      this.fetchPhases();
    },
    async executePhase(phaseId) {
      this.executing = true;
      try {
        await this.$axios.post(`/api/projects/${this.projectId}/execute/${phaseId}`);
        this.$message.success('阶段执行已启动');
        
        // 立即获取最新状态
        await this.fetchStatus();
      } catch (error) {
        console.error('执行阶段失败', error);
        this.$message.error('执行阶段失败');
      } finally {
        this.executing = false;
      }
    },
    selectPhase(index) {
      if (index >= 0 && index < this.phases.length) {
        this.activeIndex = index;
        this.currentPhase = this.phases[index];
      }
    },
    isCompleted(phaseId) {
      return this.completedPhases.includes(phaseId);
    },
    isRunning(phaseId) {
      return this.currentPhase && this.currentPhase.id === phaseId && 
             this.phaseStatus && this.phaseStatus.includes('progress');
    },
    formatDate(dateString) {
      if (!dateString) return '';
      try {
        const date = new Date(dateString);
        return date.toLocaleString();
      } catch (e) {
        return dateString;
      }
    },
    getStatusType(status) {
      if (status.includes('completed')) return 'success';
      if (status.includes('progress')) return 'warning';
      if (status === 'failed') return 'danger';
      return 'info';
    },
    formatStatus(status) {
      if (status.includes('completed')) return '已完成';
      if (status.includes('progress')) return '执行中';
      if (status === 'failed') return '失败';
      if (status === 'pending') return '待执行';
      return status;
    },
    getPhaseDescription(phase) {
      if (this.isCompleted(phase.id)) return '已完成';
      if (this.currentPhase && this.currentPhase.id === phase.id) {
        if (this.phaseStatus && this.phaseStatus.includes('progress')) return '执行中';
        return '准备执行';
      }
      return '待执行';
    },
    getCurrentStatus() {
      if (this.phaseStatus && this.phaseStatus.includes('progress')) return 'process';
      if (this.phaseStatus === 'failed') return 'error';
      return 'process';
    },
    startStatusInterval() {
      // 每5秒自动刷新状态
      this.statusInterval = setInterval(() => {
        if (!this.executing) {
          this.fetchStatus();
        }
      }, 5000);
    },
    stopStatusInterval() {
      if (this.statusInterval) {
        clearInterval(this.statusInterval);
      }
    }
  }
}
</script>

<style scoped>
.project-phases {
  margin-bottom: 20px;
}
.phase-card {
  margin-bottom: 20px;
}
.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.current-phase-info {
  margin-bottom: 15px;
}
.mt-10 {
  margin-top: 10px;
}
.mt-20 {
  margin-top: 20px;
}
</style> 