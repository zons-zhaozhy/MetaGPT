<template>
  <div class="requirement-clarifier">
    <h2>需求澄清</h2>
    
    <el-tabs v-model="activeTab" class="clarity-tabs">
      <el-tab-pane label="5W2H 结构化澄清" name="5w2h">
        <requirement-5w2h 
          :projectId="projectId" 
          @clarification-complete="handleClarificationComplete"
        />
      </el-tab-pane>
      
      <el-tab-pane label="传统澄清" name="traditional">
        <div class="clarifier-container">
          <div class="clarifier-header">
            <h3>需求问答</h3>
            <div class="clarifier-actions">
              <el-button type="primary" @click="generateQuestions" :loading="isGenerating" :disabled="isAnswering">
                生成澄清问题
              </el-button>
              <el-button type="success" @click="finalizeClarification" :disabled="questions.length === 0 || hasUnansweredQuestions">
                完成澄清
              </el-button>
            </div>
          </div>
          
          <div class="upload-section">
            <h4>需求上传</h4>
            <div class="upload-content">
              <el-upload
                class="requirement-uploader"
                action="#"
                :http-request="uploadRequirementFile"
                :limit="1"
                :on-exceed="handleExceed"
                :file-list="fileList"
                :on-remove="handleRemove"
                :before-upload="beforeUpload"
                drag
              >
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                  拖拽文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    支持PDF、Word文档、Markdown和文本文件，文件大小不超过5MB
                  </div>
                </template>
              </el-upload>
            </div>
          </div>
          
          <div v-if="clarityScore !== null" class="clarity-assessment">
            <h4>需求清晰度评估</h4>
            <div class="score-container">
              <el-progress 
                :percentage="clarityScore * 100" 
                :status="clarityScore < 0.6 ? 'exception' : (clarityScore < 0.8 ? 'warning' : 'success')"
                :stroke-width="20"
                :show-text="true"
                :format="percentFormat"
              ></el-progress>
              <div class="score-label">
                <span v-if="clarityScore < 0.6">需求不清晰，建议澄清</span>
                <span v-else-if="clarityScore < 0.8">需求部分清晰，有改进空间</span>
                <span v-else>需求清晰，可继续进行</span>
              </div>
            </div>
            
            <div v-if="ambiguousPoints && ambiguousPoints.length > 0" class="ambiguous-points">
              <h5>模糊点列表</h5>
              <el-collapse>
                <el-collapse-item v-for="(point, index) in ambiguousPoints" :key="index" :name="index">
                  <template #title>
                    <span class="point-type-tag" :class="getPointTypeClass(point.type)">{{ point.type }}</span>
                    <span class="point-title">{{ point.description }}</span>
                  </template>
                  <div class="point-detail">
                    <div class="point-position">
                      <strong>相关文本:</strong> 
                      <el-tag size="small" effect="plain">{{ point.position }}</el-tag>
                    </div>
                    <div class="point-question">
                      <strong>建议澄清问题:</strong> {{ point.clarification_question }}
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
          
          <div v-if="currentRequirement" class="current-requirement">
            <h4>当前需求</h4>
            <div class="requirement-content">
              <pre>{{ currentRequirement }}</pre>
            </div>
          </div>
          
          <div v-if="isGenerating" class="loading-container">
            <el-icon class="loading-icon"><Loading /></el-icon>
            <span>正在生成澄清问题...</span>
          </div>
          
          <div v-else-if="questions.length === 0" class="empty-questions">
            <el-empty description="暂无澄清问题，点击'生成澄清问题'按钮开始澄清"></el-empty>
          </div>
          
          <el-collapse v-else v-model="activeQuestions" accordion>
            <el-collapse-item 
              v-for="question in questions" 
              :key="question.id" 
              :name="question.id"
              :disabled="isAnswering && answeringQuestionId !== question.id"
            >
              <template #title>
                <div class="question-title">
                  <span class="question-text">{{ question.question }}</span>
                  <el-tag 
                    size="small" 
                    :type="getQuestionStatusType(question.status)"
                    class="question-tag"
                  >
                    {{ getQuestionStatusText(question.status) }}
                  </el-tag>
                </div>
              </template>
              
              <div class="question-content">
                <div v-if="question.answers && question.answers.length > 0" class="question-answers">
                  <div v-for="(answer, index) in question.answers" :key="answer.id" class="answer-item">
                    <div class="answer-header">
                      <span class="answer-label">回答 {{ index + 1 }}</span>
                      <span class="answer-time">{{ formatDate(answer.created_at) }}</span>
                    </div>
                    <div class="answer-content">{{ answer.answer }}</div>
                  </div>
                </div>
                
                <div v-if="question.status === 'pending' || question.needs_followup" class="answer-form">
                  <el-input
                    v-model="newAnswer"
                    type="textarea"
                    placeholder="请输入您的回答"
                    :rows="4"
                    :disabled="isAnswering && answeringQuestionId !== question.id"
                  ></el-input>
                  <div class="answer-actions">
                    <el-button 
                      type="primary" 
                      @click="submitAnswer(question)" 
                      :loading="isAnswering && answeringQuestionId === question.id"
                      :disabled="!newAnswer || (isAnswering && answeringQuestionId !== question.id)"
                    >
                      提交回答
                    </el-button>
                  </div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-tab-pane>
    </el-tabs>
    
    <el-dialog
      v-model="finalizeDialogVisible"
      title="完成需求澄清"
      width="50%"
    >
      <div class="finalize-content">
        <h4>完整需求</h4>
        <pre class="final-requirement">{{ finalRequirement }}</pre>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="finalizeDialogVisible = false">继续澄清</el-button>
          <el-button type="primary" @click="confirmFinalize">确认需求并进入下一阶段</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import Requirement5W2H from './Requirement5W2H.vue'
import { ref, computed, onMounted } from 'vue'
import { Loading, UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

export default {
  name: 'RequirementClarifier',
  components: {
    Loading,
    UploadFilled,
    Requirement5W2H
  },
  props: {
    projectId: {
      type: String,
      required: true
    }
  },
  emits: ['clarification-complete'],
  setup(props, { emit }) {
    const questions = ref([])
    const activeQuestions = ref([])
    const newAnswer = ref('')
    const isGenerating = ref(false)
    const isAnswering = ref(false)
    const answeringQuestionId = ref(null)
    const currentRequirement = ref('')
    const finalizeDialogVisible = ref(false)
    const generatingQuestions = ref(false)
    const hasGeneratedQuestions = ref(false)
    const loading = ref(false)
    const fileList = ref([])
    const isUploading = ref(false)
    const clarityScore = ref(null)
    const ambiguousPoints = ref([])
    const activeTab = ref('5w2h')  // 默认使用5W2H模式
    
    // 是否有未回答的问题
    const hasUnansweredQuestions = computed(() => {
      return questions.value.some(q => q.status === 'pending')
    })
    
    // 最终需求（包括问答）
    const finalRequirement = computed(() => {
      let result = currentRequirement.value || ''
      
      // 添加已回答的问题和答案
      const answeredQuestions = questions.value.filter(q => q.status === 'answered' && q.answers && q.answers.length > 0)
      
      if (answeredQuestions.length > 0) {
        result += '\n\n## 需求澄清问答\n'
        
        answeredQuestions.forEach((q, index) => {
          result += `\n### 问题 ${index + 1}: ${q.question}\n`
          if (q.answers && q.answers.length > 0) {
            result += `回答: ${q.answers[0].answer}\n`
          }
        })
      }
      
      return result
    })
    
    // 上传前验证
    const beforeUpload = (file) => {
      const allowedTypes = [
        'application/pdf', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
        'text/plain', 
        'text/markdown'
      ]
      const maxSize = 5 * 1024 * 1024 // 5MB
      
      if (!allowedTypes.includes(file.type) && 
          !(file.name.endsWith('.md') || file.name.endsWith('.markdown'))) {
        ElMessage.error('只支持PDF、Word文档、Markdown和文本文件')
        return false
      }
      
      if (file.size > maxSize) {
        ElMessage.error('文件大小不能超过5MB')
        return false
      }
      
      return true
    }
    
    // 处理超出限制
    const handleExceed = () => {
      ElMessage.warning('只能上传一个文件，请先删除已上传的文件')
    }
    
    // 处理移除文件
    const handleRemove = () => {
      fileList.value = []
    }
    
    // 上传需求文件
    const uploadRequirementFile = async (options) => {
      try {
        isUploading.value = true
        
        const formData = new FormData()
        formData.append('file', options.file)
        
        const token = localStorage.getItem('token')
        if (!token) {
          ElMessage.error('未登录或会话已过期')
          return
        }
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/upload-requirement`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
              'Authorization': `Bearer ${token}`
            }
          }
        )
        
        if (response.data && response.data.success) {
          ElMessage.success('需求文档上传解析成功')
          
          // 更新需求清晰度信息
          clarityScore.value = response.data.clarity_score
          ambiguousPoints.value = response.data.ambiguous_points || []
          
          // 重新加载项目信息和问题列表
          await loadProjectInfo()
          await fetchQuestions()
          
          // 如果存在模糊点但没有生成问题，自动生成问题
          if (response.data.needs_clarification && questions.value.length === 0) {
            generateQuestions()
          }
          
          options.onSuccess()
        } else {
          ElMessage.error(response.data.error || '上传失败')
          options.onError('上传失败')
        }
      } catch (error) {
        console.error('文件上传错误:', error)
        ElMessage.error(error.response?.data?.error || '文件上传失败')
        options.onError('上传失败')
      } finally {
        isUploading.value = false
      }
    }
    
    // 格式化百分比显示
    const percentFormat = (percentage) => {
      return `${percentage.toFixed(0)}%`
    }
    
    // 获取模糊点类型样式
    const getPointTypeClass = (type) => {
      const typeMap = {
        '功能模糊': 'point-type-function',
        '术语歧义': 'point-type-term',
        '需求缺失': 'point-type-missing',
        '约束不明': 'point-type-constraint',
        '场景不全': 'point-type-scenario'
      }
      
      return typeMap[type] || 'point-type-other'
    }
    
    // 加载需求信息
    const loadProjectInfo = async () => {
      try {
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.get(`/api/projects/${props.projectId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        
        if (response.data && response.data.requirement) {
          currentRequirement.value = response.data.requirement
        }
      } catch (error) {
        console.error('加载项目信息失败:', error)
        ElMessage.error('加载项目信息失败')
      }
    }
    
    // 获取澄清问题
    const fetchQuestions = async () => {
      try {
        loading.value = true;
        const response = await axios.get(`/api/projects/${props.projectId}/clarify/questions`);
        questions.value = response.data.questions || [];
      } catch (error) {
        console.error('加载澄清问题失败:', error);
        
        // 如果没有问题或API返回错误，初始化为空列表
        questions.value = [];
        
        // 延迟尝试生成问题
        if (!hasGeneratedQuestions.value) {
          setTimeout(() => {
            generateQuestions();
          }, 1000);
        }
      } finally {
        loading.value = false;
      }
    };
    
    // 生成澄清问题
    const generateQuestions = async () => {
      try {
        isGenerating.value = true;
        generatingQuestions.value = true;
        
        const response = await axios.get(`/api/projects/${props.projectId}/clarify`);
        
        if (response.data) {
          // 更新清晰度评估
          if ('clarity_score' in response.data) {
            clarityScore.value = response.data.clarity_score;
          }
          
          ElMessage.success('澄清问题生成成功');
          hasGeneratedQuestions.value = true;
          
          // 重新加载问题列表
          await fetchQuestions();
          
          // 重新加载项目信息，获取更新后的需求
          await loadProjectInfo();
        }
      } catch (error) {
        console.error('生成澄清问题失败:', error);
        ElMessage.error(error.response?.data?.error || '生成澄清问题失败');
      } finally {
        isGenerating.value = false;
        generatingQuestions.value = false;
      }
    };
    
    // 提交问题回答
    const submitAnswer = async (question) => {
      if (!newAnswer.value.trim()) {
        ElMessage.warning('请输入回答')
        return
      }
      
      try {
        isAnswering.value = true
        answeringQuestionId.value = question.id
        
        const token = localStorage.getItem('token')
        if (!token) return
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/clarify/answer`,
          {
            question_id: question.id,
            answer: newAnswer.value
          },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        if (response.data && response.data.success) {
          ElMessage.success('回答提交成功')
          
          // 更新问题状态
          const updatedQuestion = questions.value.find(q => q.id === question.id)
          if (updatedQuestion) {
            updatedQuestion.status = 'answered'
            updatedQuestion.needs_followup = response.data.needs_followup
            
            // 添加回答
            if (!updatedQuestion.answers) {
              updatedQuestion.answers = []
            }
            
            updatedQuestion.answers.push({
              id: response.data.answer_id,
              answer: newAnswer.value,
              created_at: new Date().toISOString()
            })
          }
          
          // 清空回答输入框
          newAnswer.value = ''
          
          // 重新加载项目信息，获取更新后的需求
          await loadProjectInfo()
        } else {
          ElMessage.error('回答提交失败')
        }
      } catch (error) {
        console.error('提交回答失败:', error)
        ElMessage.error('提交回答失败')
      } finally {
        isAnswering.value = false
        answeringQuestionId.value = null
      }
    }
    
    // 获取问题状态样式
    const getQuestionStatusType = (status) => {
      switch (status) {
        case 'pending': return 'warning'
        case 'answered': return 'success'
        default: return 'info'
      }
    }
    
    // 获取问题状态文本
    const getQuestionStatusText = (status) => {
      switch (status) {
        case 'pending': return '待回答'
        case 'answered': return '已回答'
        default: return '未知状态'
      }
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return ''
      
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 完成澄清
    const finalizeClarification = () => {
      finalizeDialogVisible.value = true
    }
    
    // 确认完成澄清
    const confirmFinalize = () => {
      finalizeDialogVisible.value = false
      emit('clarification-complete', finalRequirement.value)
    }
    
    // 处理5W2H完成澄清
    const handleClarificationComplete = (requirement) => {
      emit('clarification-complete', requirement)
    }
    
    // 在组件挂载时加载数据
    onMounted(() => {
      loadProjectInfo()
      fetchQuestions()
    })
    
    return {
      questions,
      activeQuestions,
      newAnswer,
      isGenerating,
      isAnswering,
      answeringQuestionId,
      currentRequirement,
      hasUnansweredQuestions,
      finalRequirement,
      finalizeDialogVisible,
      fileList,
      isUploading,
      clarityScore,
      ambiguousPoints,
      activeTab,
      generateQuestions,
      submitAnswer,
      getQuestionStatusType,
      getQuestionStatusText,
      formatDate,
      finalizeClarification,
      confirmFinalize,
      beforeUpload,
      handleExceed,
      handleRemove,
      uploadRequirementFile,
      percentFormat,
      getPointTypeClass,
      handleClarificationComplete
    }
  }
}
</script>

<style scoped>
.requirement-clarifier {
  padding: 20px;
}

.clarity-tabs {
  margin-top: 20px;
}

.clarifier-container {
  margin-top: 20px;
}

.clarifier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.current-requirement {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 10px;
  background-color: #f9f9f9;
}

.requirement-content {
  max-height: 200px;
  overflow-y: auto;
}

.requirement-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
}

.loading-icon {
  font-size: 24px;
  margin-right: 10px;
  animation: rotating 2s linear infinite;
}

.empty-questions {
  margin: 30px 0;
}

.question-title {
  display: flex;
  align-items: center;
}

.question-text {
  flex: 1;
}

.question-tag {
  margin-left: 10px;
}

.question-content {
  padding: 10px 0;
}

.question-answers {
  margin-bottom: 15px;
}

.answer-item {
  margin-bottom: 10px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.answer-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 0.9em;
  color: #606266;
}

.answer-content {
  white-space: pre-wrap;
}

.answer-form {
  margin-top: 15px;
}

.answer-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.finalize-content {
  max-height: 400px;
  overflow-y: auto;
}

.final-requirement {
  white-space: pre-wrap;
  word-wrap: break-word;
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 文件上传区域样式 */
.upload-section {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
}

.upload-content {
  margin-top: 10px;
}

.requirement-uploader {
  width: 100%;
}

/* 需求清晰度评估区域样式 */
.clarity-assessment {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
}

.score-container {
  margin: 15px 0;
}

.score-label {
  margin-top: 5px;
  text-align: center;
  font-weight: bold;
}

.ambiguous-points {
  margin-top: 15px;
}

.point-type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 8px;
  color: #fff;
}

.point-type-function {
  background-color: #409eff;
}

.point-type-term {
  background-color: #e6a23c;
}

.point-type-missing {
  background-color: #f56c6c;
}

.point-type-constraint {
  background-color: #67c23a;
}

.point-type-scenario {
  background-color: #909399;
}

.point-type-other {
  background-color: #9c27b0;
}

.point-title {
  font-weight: 500;
}

.point-detail {
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-top: 8px;
}

.point-position {
  margin-bottom: 8px;
}

.point-question {
  color: #606266;
}
</style> 