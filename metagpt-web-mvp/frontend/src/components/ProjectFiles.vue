<template>
  <div class="project-files">
    <h2>项目文件</h2>
    
    <el-card class="files-container" shadow="hover">
      <div class="files-header">
        <h3>文件列表</h3>
        <el-button @click="refreshFiles" :loading="isLoading">
          刷新
        </el-button>
      </div>
      
      <div v-if="isLoading" class="loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>加载文件中...</span>
      </div>
      
      <div v-else-if="files.length === 0" class="empty-files">
        <el-empty description="暂无生成文件"></el-empty>
      </div>
      
      <el-table
        v-else
        :data="files"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="filename" label="文件名" min-width="180" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="scope">
            <el-tag size="small" :type="getFileTypeTag(scope.row.type)">
              {{ scope.row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="150">
          <template #default="scope">
            <el-button
              type="primary"
              size="small"
              @click="viewFile(scope.row)"
            >
              查看
            </el-button>
            <el-button
              type="success"
              size="small"
              @click="downloadFile(scope.row)"
            >
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 文件查看对话框 -->
    <el-dialog
      v-model="fileDialogVisible"
      :title="currentFile.filename || '文件内容'"
      width="80%"
    >
      <div v-if="isLoadingContent" class="loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>加载文件内容中...</span>
      </div>
      <div v-else>
        <pre v-if="isTextFile" class="file-content">{{ fileContent }}</pre>
        <div v-else-if="isImageFile" class="image-container">
          <img :src="fileImageUrl" alt="文件图片" />
        </div>
        <div v-else class="file-not-viewable">
          此文件类型不支持在线预览，请下载后查看
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="fileDialogVisible = false">关闭</el-button>
          <el-button 
            type="primary" 
            @click="downloadFile(currentFile)"
          >
            下载
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

export default {
  name: 'ProjectFiles',
  components: {
    Loading
  },
  props: {
    projectId: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const files = ref([])
    const isLoading = ref(false)
    const isLoadingContent = ref(false)
    const fileDialogVisible = ref(false)
    const currentFile = ref({})
    const fileContent = ref('')
    const fileImageUrl = ref('')
    
    // 是否是文本文件
    const isTextFile = computed(() => {
      const filename = currentFile.value.filename || ''
      return /\.(txt|md|json|js|py|html|css|java|xml|yaml|yml|cpp|h|c|cs|ini|log|sh|bat)$/i.test(filename)
    })
    
    // 是否是图片文件
    const isImageFile = computed(() => {
      const filename = currentFile.value.filename || ''
      return /\.(jpg|jpeg|png|gif|svg|webp)$/i.test(filename)
    })
    
    // 加载文件列表
    const loadFiles = async () => {
      try {
        isLoading.value = true
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.get(`/api/projects/${props.projectId}/files`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        
        if (response.data) {
          files.value = response.data || []
        }
      } catch (error) {
        console.error('加载文件列表失败:', error)
        ElMessage.error('加载文件列表失败')
      } finally {
        isLoading.value = false
      }
    }
    
    // 刷新文件列表
    const refreshFiles = () => {
      loadFiles()
    }
    
    // 查看文件
    const viewFile = async (file) => {
      currentFile.value = file
      fileContent.value = ''
      fileImageUrl.value = ''
      fileDialogVisible.value = true
      
      try {
        isLoadingContent.value = true
        const token = localStorage.getItem('token')
        if (!token) return
        
        // 如果是图片文件，设置图片URL
        if (isImageFile.value) {
          fileImageUrl.value = `/api/projects/${props.projectId}/files/${file.id}/view`
          return
        }
        
        // 如果是文本文件，获取内容
        if (isTextFile.value) {
          const response = await axios.get(`/api/projects/${props.projectId}/files/${file.id}/view`, {
            headers: { Authorization: `Bearer ${token}` }
          })
          
          if (response.data && response.data.content) {
            fileContent.value = response.data.content
          }
        }
      } catch (error) {
        console.error('加载文件内容失败:', error)
        ElMessage.error('加载文件内容失败')
      } finally {
        isLoadingContent.value = false
      }
    }
    
    // 下载文件
    const downloadFile = (file) => {
      const token = localStorage.getItem('token')
      if (!token) return
      
      // 创建下载链接
      const downloadUrl = `/api/projects/${props.projectId}/files/${file.id}/download`
      
      // 创建隐藏的下载链接并点击
      const link = document.createElement('a')
      link.href = downloadUrl
      link.setAttribute('download', file.filename)
      link.setAttribute('target', '_blank')
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
    
    // 获取文件类型标签
    const getFileTypeTag = (type) => {
      const typeMap = {
        'code': 'success',
        'document': 'info',
        'image': 'warning',
        'unknown': ''
      }
      return typeMap[type] || ''
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 监听项目ID变化
    watch(() => props.projectId, () => {
      if (props.projectId) {
        loadFiles()
      }
    })
    
    // 组件挂载时加载数据
    onMounted(() => {
      if (props.projectId) {
        loadFiles()
      }
    })
    
    return {
      files,
      isLoading,
      isLoadingContent,
      fileDialogVisible,
      currentFile,
      fileContent,
      fileImageUrl,
      isTextFile,
      isImageFile,
      refreshFiles,
      viewFile,
      downloadFile,
      getFileTypeTag,
      formatDate
    }
  }
}
</script>

<style scoped>
.project-files {
  margin: 20px 0;
}

.files-container {
  margin: 20px 0;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: #909399;
}

.loading-icon {
  margin-right: 10px;
  font-size: 20px;
}

.empty-files {
  margin: 30px 0;
}

.file-content {
  white-space: pre-wrap;
  overflow-x: auto;
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  font-family: monospace;
  max-height: 600px;
  overflow-y: auto;
}

.image-container {
  text-align: center;
}

.image-container img {
  max-width: 100%;
  max-height: 600px;
}

.file-not-viewable {
  text-align: center;
  color: #909399;
  padding: 30px;
}
</style> 