<template>
  <div class="new-project-container">
    <div class="page-header">
      <h2>创建项目</h2>
      <el-button @click="$router.push('/')">返回项目列表</el-button>
    </div>
    
    <el-card class="mt-20">
      <el-form :model="projectForm" :rules="rules" ref="projectFormRef" label-width="120px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        
        <el-form-item label="项目需求" prop="requirement">
          <el-input
            v-model="projectForm.requirement"
            type="textarea"
            :rows="8"
            placeholder="请输入项目需求描述，尽可能详细具体"
          />
          <div class="form-tips">
            提示：提供清晰、详细的需求描述将有助于生成更好的代码。例如描述功能、用户场景、技术偏好等。
          </div>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitForm">创建项目</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'NewProject',
  data() {
    return {
      submitting: false,
      projectForm: {
        name: '',
        requirement: ''
      },
      rules: {
        name: [
          { required: true, message: '请输入项目名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        requirement: [
          { required: true, message: '请输入项目需求', trigger: 'blur' },
          { min: 10, message: '需求描述至少 10 个字符', trigger: 'blur' }
        ]
      }
    };
  },
  methods: {
    submitForm() {
      this.$refs.projectFormRef.validate(async (valid) => {
        if (valid) {
          this.submitting = true;
          
          try {
            const response = await this.$axios.post('/api/projects', this.projectForm);
            
            this.$message({
              type: 'success',
              message: '项目创建成功'
            });
            
            // 跳转到项目详情页
            this.$router.push(`/projects/${response.data.id}`);
          } catch (error) {
            let errorMsg = '项目创建失败';
            
            if (error.response && error.response.data && error.response.data.error) {
              errorMsg = error.response.data.error;
            }
            
            this.$message({
              type: 'error',
              message: errorMsg
            });
          } finally {
            this.submitting = false;
          }
        } else {
          return false;
        }
      });
    },
    resetForm() {
      this.$refs.projectFormRef.resetFields();
    }
  }
};
</script>

<style scoped>
.new-project-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tips {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style> 