<template>
  <div class="requirement-clarifier">
    <h2>需求澄清</h2>
    
    <el-card class="clarifier-container" shadow="hover">
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
    </el-card>
    
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
import { ref, computed, onMounted, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

export default {
  name: 'RequirementClarifier',
  components: {
    Loading
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
        generatingQuestions.value = true;
        await axios.get(`/api/projects/${props.projectId}/clarify`);
        ElMessage.success('澄清问题生成成功');
        hasGeneratedQuestions.value = true;
        
        // 重新加载问题列表
        await fetchQuestions();
        
        // 重新加载项目信息，获取更新后的需求
        await loadProjectInfo();
      } catch (error) {
        console.error('生成澄清问题失败:', error);
        ElMessage.error('生成澄清问题失败');
      } finally {
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
          ElMessage.success('回答已提交')
          
          // 清空输入
          newAnswer.value = ''
          
          // 重新加载问题列表
          await fetchQuestions()
          
          // 重新加载项目信息，获取更新后的需求
          await loadProjectInfo()
          
          // 如果需要后续问题，可以在这里处理
          if (response.data.needs_followup) {
            ElMessage.info('系统可能会根据您的回答生成后续问题')
          }
        }
      } catch (error) {
        console.error('提交回答失败:', error)
        ElMessage.error('提交回答失败')
      } finally {
        isAnswering.value = false
        answeringQuestionId.value = null
      }
    }
    
    // 完成澄清，显示最终需求
    const finalizeClarification = () => {
      finalizeDialogVisible.value = true
    }
    
    // 确认完成澄清
    const confirmFinalize = () => {
      finalizeDialogVisible.value = false
      
      // 触发完成事件
      emit('clarification-complete', {
        requirement: finalRequirement.value
      })
      
      ElMessage.success('需求澄清完成')
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 获取问题状态类型
    const getQuestionStatusType = (status) => {
      if (status === 'answered') return 'success'
      if (status === 'pending') return 'warning'
      return 'info'
    }
    
    // 获取问题状态文本
    const getQuestionStatusText = (status) => {
      const statusMap = {
        'answered': '已回答',
        'pending': '待回答'
      }
      return statusMap[status] || status
    }
    
    // 组件挂载时获取数据
    onMounted(async () => {
      if (props.projectId) {
        await loadProjectInfo();
        await fetchQuestions();
      }
    });
    
    // 监听项目ID变化
    watch(() => props.projectId, async (newId) => {
      if (newId) {
        await loadProjectInfo();
        await fetchQuestions();
      }
    });
    
    return {
      questions,
      activeQuestions,
      newAnswer,
      isGenerating,
      isAnswering,
      answeringQuestionId,
      currentRequirement,
      finalRequirement,
      finalizeDialogVisible,
      hasUnansweredQuestions,
      fetchQuestions,
      submitAnswer,
      finalizeClarification,
      confirmFinalize,
      formatDate,
      getQuestionStatusType,
      getQuestionStatusText,
      loading,
      generateQuestions
    }
  }
}
</script>

<style scoped>
.requirement-clarifier {
  margin: 20px 0;
}

.clarifier-container {
  margin: 20px 0;
}

.clarifier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.clarifier-actions {
  display: flex;
  gap: 10px;
}

.current-requirement {
  margin-bottom: 20px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  background-color: #f5f7fa;
}

.requirement-content {
  max-height: 200px;
  overflow-y: auto;
}

.requirement-content pre {
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
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

.empty-questions {
  margin: 30px 0;
}

.question-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
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
  margin-bottom: 20px;
}

.answer-item {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px dashed #dcdfe6;
}

.answer-item:last-child {
  border-bottom: none;
}

.answer-header {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #909399;
  margin-bottom: 5px;
}

.answer-content {
  white-space: pre-wrap;
}

.answer-form {
  margin-top: 20px;
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
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  margin: 0;
  font-family: inherit;
}
</style> 