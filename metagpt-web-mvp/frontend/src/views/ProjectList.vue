<template>
  <div class="project-list-container">
    <div class="page-header">
      <h2>项目列表</h2>
      <el-button type="primary" @click="$router.push('/projects/new')">创建项目</el-button>
    </div>
    
    <el-card class="mt-20">
      <el-table
        v-loading="loading"
        :data="projects"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="180">
          <template #default="scope">
            <el-progress
              :percentage="getProgressPercentage(scope.row.active_step)"
              :status="getProgressStatus(scope.row.status)"
            />
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="150">
          <template #default="scope">
            <el-button
              link
              size="small"
              @click="viewProject(scope.row.id)"
            >
              查看
            </el-button>
            <el-button
              link
              size="small"
              @click="downloadProject(scope.row.id)"
              :disabled="scope.row.status !== '已完成'"
            >
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div v-if="!loading && projects.length === 0" class="empty-data">
        <el-empty description="暂无项目，点击『创建项目』开始使用" />
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'ProjectList',
  data() {
    return {
      loading: false,
      projects: []
    };
  },
  created() {
    this.fetchProjects();
  },
  methods: {
    async fetchProjects() {
      this.loading = true;
      try {
        const response = await this.$axios.get('/api/projects');
        this.projects = response.data;
      } catch (error) {
        console.error('获取项目列表失败', error);
        this.$message.error('获取项目列表失败');
      } finally {
        this.loading = false;
      }
    },
    formatDate(dateString) {
      try {
        const date = new Date(dateString);
        return date.toLocaleString();
      } catch (e) {
        return dateString;
      }
    },
    getStatusType(status) {
      const statusMap = {
        'pending': 'info',
        '需求分析中': 'warning',
        '架构设计中': 'warning',
        '编码实现中': 'warning',
        '测试验证中': 'warning',
        '已完成': 'success',
        '失败': 'danger'
      };
      return statusMap[status] || 'info';
    },
    getProgressPercentage(step) {
      // 根据当前阶段计算进度百分比
      const stepMap = {
        0: 0,    // 未开始
        1: 20,   // 需求分析
        2: 40,   // 架构设计
        3: 60,   // 编码实现
        4: 80,   // 测试验证
        5: 100   // 已完成
      };
      return stepMap[step] || 0;
    },
    getProgressStatus(status) {
      if (status === '已完成') {
        return 'success';
      } else if (status === '失败') {
        return 'exception';
      }
      return '';
    },
    viewProject(id) {
      this.$router.push(`/projects/${id}`);
    },
    async downloadProject(id) {
      try {
        // 直接在新窗口打开下载链接
        window.open(`${this.$axios.defaults.baseURL}/api/projects/${id}/download`, '_blank');
      } catch (error) {
        console.error('下载项目失败', error);
        this.$message.error('下载项目失败');
      }
    }
  }
};
</script>

<style scoped>
.project-list-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-data {
  margin-top: 20px;
  text-align: center;
}
</style> 