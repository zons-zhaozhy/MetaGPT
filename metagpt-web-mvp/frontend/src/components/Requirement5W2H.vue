<template>
  <div class="requirement-5w2h">
    <h2>需求澄清 (5W2H框架)</h2>
    
    <el-card class="clarifier-container" shadow="hover">
      <!-- 技术领域选择 -->
      <div class="domain-selector">
        <h3>技术领域选择</h3>
        <el-select 
          v-model="selectedDomain" 
          placeholder="选择技术领域" 
          @change="handleDomainChange"
          class="domain-select"
        >
          <el-option
            v-for="domain in availableDomains"
            :key="domain.id"
            :label="domain.name"
            :value="domain.id"
          >
            <div class="domain-option">
              <span>{{ domain.name }}</span>
              <small>{{ domain.description }}</small>
            </div>
          </el-option>
        </el-select>
        <div class="domain-description">
          选择合适的技术领域可以提高需求分析的精准度，系统将使用领域特定的知识进行分析
        </div>
      </div>
      
      <!-- 进度指示器 -->
      <div class="progress-container">
        <el-steps :active="activeRound" finish-status="success" simple>
          <el-step 
            v-for="round in rounds" 
            :key="round.round_id" 
            :title="round.name" 
            :status="getStepStatus(round.status)"
          />
          <el-step title="完成" />
        </el-steps>
      </div>
      
      <!-- 分析结果展示 -->
      <div v-if="analysis" class="analysis-results">
        <h3>需求清晰度分析</h3>
        <div class="clarity-assessment">
          <div class="score-container">
            <el-progress 
              :percentage="analysis.clarity_score" 
              :status="getClarityStatus(analysis.clarity_score)"
              :stroke-width="20"
              :format="percentFormat"
            ></el-progress>
            <div class="score-label">
              <span v-if="analysis.clarity_score < 60">需求不清晰，建议全面澄清</span>
              <span v-else-if="analysis.clarity_score < 80">需求部分清晰，有改进空间</span>
              <span v-else>需求较为清晰，可针对性澄清</span>
            </div>
          </div>
          
          <!-- 雷达图展示各维度完整度 -->
          <div v-if="analysis.dimension_scores" class="dimension-chart">
            <div ref="radarChart" class="radar-chart"></div>
          </div>
          
          <!-- 一致性问题展示 -->
          <div v-if="analysis.consistency_issues && analysis.consistency_issues.length > 0" class="consistency-issues">
            <h4>技术术语一致性问题</h4>
            <el-alert
              v-for="(issue, index) in analysis.consistency_issues"
              :key="index"
              type="warning"
              :title="issue.description"
              :closable="false"
              show-icon
            >
              <div class="issue-content">
                <div class="issue-terms">
                  <el-tag 
                    v-for="term in issue.terms" 
                    :key="term" 
                    type="info" 
                    effect="plain" 
                    class="term-tag"
                  >
                    {{ term }}
                  </el-tag>
                </div>
                <div class="issue-question">
                  建议问题: {{ issue.clarification_question }}
                </div>
              </div>
            </el-alert>
          </div>
        </div>
      </div>
      
      <!-- 当前需求展示 -->
      <div v-if="currentRequirement" class="current-requirement">
        <h3>当前需求描述</h3>
        <div class="requirement-content">
          <pre>{{ currentRequirement }}</pre>
        </div>
      </div>
      
      <!-- 文档上传 -->
      <div class="upload-section">
        <h3>需求文档上传</h3>
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
      
      <!-- 分析按钮 -->
      <div class="analyze-actions">
        <el-button 
          type="primary" 
          @click="analyzeRequirement" 
          :loading="isAnalyzing"
          :disabled="!currentRequirement && fileList.length === 0"
        >
          {{ isFirstAnalysis ? '分析需求并生成澄清问题' : '重新分析需求' }}
        </el-button>
      </div>
      
      <!-- 轮次问题组 -->
      <div v-if="rounds.length > 0" class="round-questions">
        <h3>{{ currentRound ? currentRound.name : '需求澄清问题' }}</h3>
        <p v-if="currentRound" class="round-description">{{ currentRound.description }}</p>
        
        <!-- 问题列表 -->
        <el-collapse v-model="activeQuestions" accordion>
          <el-collapse-item 
            v-for="question in currentQuestions" 
            :key="question.id" 
            :name="question.id"
            :disabled="isAnswering && answeringQuestionId !== question.id"
          >
            <template #title>
              <div class="question-title">
                <span class="question-text">{{ question.question }}</span>
                <div class="question-tags">
                  <el-tag 
                    size="small" 
                    :type="getQuestionStatusType(question.status)"
                    class="question-tag"
                  >
                    {{ getQuestionStatusText(question.status) }}
                  </el-tag>
                  <el-tag 
                    v-if="question.severity === 'high'" 
                    size="small" 
                    type="danger"
                    effect="dark"
                    class="severity-tag"
                  >
                    重要
                  </el-tag>
                  <el-tag 
                    v-if="question.is_followup" 
                    size="small" 
                    type="info"
                    effect="plain"
                    class="followup-tag"
                  >
                    后续问题
                  </el-tag>
                </div>
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
              
              <div v-if="question.status === 'pending'" class="answer-form">
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
              
              <!-- 后续问题提示 -->
              <div v-if="question.followup_questions && question.followup_questions.length > 0" class="followup-questions">
                <el-alert
                  type="info"
                  title="系统根据您的回答生成了以下后续问题"
                  :closable="false"
                  show-icon
                >
                  <div class="followup-list">
                    <div v-for="(fq, index) in question.followup_questions" :key="index" class="followup-item">
                      <span class="followup-number">{{ index + 1 }}.</span>
                      <span class="followup-text">{{ fq }}</span>
                    </div>
                  </div>
                </el-alert>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
        
        <!-- 完成当前轮次 -->
        <div v-if="currentRound && currentRound.status !== 'completed'" class="round-actions">
          <el-button 
            type="success" 
            @click="completeRound" 
            :disabled="hasCurrentRoundPendingQuestions || isCompletingRound"
            :loading="isCompletingRound"
          >
            {{ isLastRound ? '完成需求澄清' : '完成当前轮次并进入下一轮' }}
          </el-button>
        </div>
      </div>
      
      <!-- 提醒用户分析需求 -->
      <div v-else-if="!isAnalyzing" class="empty-questions">
        <el-empty description="请上传需求文档或输入需求描述，然后点击&quot;分析需求&quot;按钮开始澄清流程"></el-empty>
      </div>
      
      <!-- 分析中提示 -->
      <div v-else class="loading-container">
        <el-icon class="loading-icon"><loading /></el-icon>
        <span>正在分析需求并生成澄清问题...</span>
      </div>

      <!-- 知识图谱可视化 -->
      <div v-if="currentRequirement" class="knowledge-graph-section">
        <h3>需求知识图谱</h3>
        <div class="graph-actions">
          <el-button type="primary" @click="fetchKnowledgeGraph" :loading="isLoadingGraph" size="small">
            生成知识图谱
          </el-button>
        </div>
        <div id="knowledge-graph-container" class="knowledge-graph-container"></div>
        
        <!-- 图谱说明 -->
        <div v-if="knowledgeGraph && knowledgeGraph.nodes && knowledgeGraph.nodes.length > 0" class="graph-legend">
          <div class="legend-title">图例说明:</div>
          <div class="legend-items">
            <div class="legend-item" v-for="dim in ['what', 'why', 'who', 'when', 'where', 'how', 'how_much']" :key="dim">
              <div class="legend-color" :style="{backgroundColor: getDimensionColor(dim)}"></div>
              <div class="legend-label">{{ getDimensionName(dim) }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
    
    <!-- 完成澄清对话框 -->
    <el-dialog
      v-model="finalizeDialogVisible"
      title="完成需求澄清"
      width="60%"
    >
      <div class="finalize-content">
        <h4>完整需求</h4>
        <pre class="final-requirement">{{ finalRequirement }}</pre>
        
        <div v-if="analysis" class="final-clarity-assessment">
          <h4>最终清晰度评估</h4>
          <div class="final-score-container">
            <el-progress 
              :percentage="analysis.clarity_score" 
              :status="getClarityStatus(analysis.clarity_score)"
              :stroke-width="20"
              :format="percentFormat"
            ></el-progress>
          </div>
          
          <div v-if="analysis.dimension_scores" class="dimension-list">
            <h5>各维度评分：</h5>
            <ul>
              <li v-for="(score, dimension) in analysis.dimension_scores" :key="dimension">
                <strong>{{ getDimensionName(dimension) }}:</strong> {{ score.toFixed(0) }}分
              </li>
            </ul>
          </div>
        </div>
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
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { Loading, UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
// 导入G6图形库
import G6 from '@antv/g6'

// 注册必要的组件
echarts.use([
  TitleComponent, 
  TooltipComponent, 
  LegendComponent, 
  RadarChart, 
  CanvasRenderer
])

export default {
  name: 'Requirement5W2H',
  components: {
    Loading,
    UploadFilled
  },
  props: {
    projectId: {
      type: String,
      required: true
    }
  },
  emits: ['clarification-complete'],
  setup(props, { emit }) {
    // 状态变量
    const rounds = ref([])
    const analysis = ref(null)
    const activeRound = ref(0)
    const activeQuestions = ref([])
    const newAnswer = ref('')
    const isAnalyzing = ref(false)
    const isAnswering = ref(false)
    const isCompletingRound = ref(false)
    const answeringQuestionId = ref(null)
    const currentRequirement = ref('')
    const finalizeDialogVisible = ref(false)
    const fileList = ref([])
    const radarChart = ref(null)
    const myChart = ref(null)
    const isFirstAnalysis = ref(true)
    const selectedDomain = ref('general')
    const availableDomains = ref([])
    const isLoadingDomains = ref(false)
    const knowledgeGraph = ref(null)
    const isLoadingGraph = ref(false)
    const graphInstance = ref(null)
    
    // 计算属性
    const currentRound = computed(() => {
      if (rounds.value.length === 0) return null
      
      // 找到状态为active或pending的第一个轮次
      const activeRoundObj = rounds.value.find(r => r.status === 'active' || r.status === 'pending')
      if (activeRoundObj) return activeRoundObj
      
      // 如果没有活动轮次，返回最后一个已完成的轮次
      return rounds.value[rounds.value.length - 1]
    })
    
    const currentQuestions = computed(() => {
      if (!currentRound.value) return []
      return currentRound.value.questions || []
    })
    
    const hasCurrentRoundPendingQuestions = computed(() => {
      return currentQuestions.value.some(q => q.status === 'pending')
    })
    
    const isLastRound = computed(() => {
      if (rounds.value.length === 0) return true
      return currentRound.value && currentRound.value.round_number === rounds.value.length
    })
    
    const finalRequirement = computed(() => {
      let result = currentRequirement.value || ''
      
      // 添加已回答的问题和答案
      const answeredRounds = rounds.value.filter(r => r.status === 'completed')
      
      if (answeredRounds.length > 0) {
        result += '\n\n## 需求澄清问答\n'
        
        answeredRounds.forEach((round, roundIndex) => {
          result += `\n### ${round.name}\n`
          
          // 获取该轮次的已回答问题
          const answeredQuestions = (round.questions || []).filter(q => 
            q.status === 'answered' && q.answers && q.answers.length > 0
          )
          
          if (answeredQuestions.length > 0) {
            answeredQuestions.forEach((q, qIndex) => {
              result += `\n问题 ${roundIndex+1}.${qIndex+1}: ${q.question}\n`
              if (q.answers && q.answers.length > 0) {
                result += `回答: ${q.answers[0].answer}\n`
              }
            })
          }
        })
      }
      
      return result
    })
    
    // 方法
    const loadProjectInfo = async () => {
      try {
        const response = await axios.get(`/api/projects/${props.projectId}`)
        
        if (response.data && response.data.requirement) {
          currentRequirement.value = response.data.requirement
        }
      } catch (error) {
        console.error('加载项目信息失败:', error)
        ElMessage.error('加载项目信息失败')
      }
    }
    
    const fetchRounds = async () => {
      try {
        const response = await axios.get(`/api/clarify/rounds/${props.projectId}`)
        
        if (response.data) {
          rounds.value = response.data.rounds || []
          
          // 如果提供了分析数据，更新它
          if (response.data.analysis) {
            analysis.value = response.data.analysis
            
            // 绘制雷达图
            nextTick(() => {
              drawRadarChart()
            })
          }
          
          // 计算当前轮次
          if (rounds.value.length > 0) {
            // 查找活动轮次的索引
            const index = rounds.value.findIndex(r => r.status === 'active' || r.status === 'pending')
            if (index >= 0) {
              activeRound.value = index + 1
            } else {
              // 如果没有活动轮次，设置为最后一个轮次的索引+1
              activeRound.value = rounds.value.length
            }
          }
        }
      } catch (error) {
        console.error('获取轮次信息失败:', error)
        ElMessage.error('获取轮次信息失败')
      }
    }
    
    const fetchAvailableDomains = async () => {
      try {
        isLoadingDomains.value = true
        const response = await axios.get('/api/clarify/domains')
        
        if (response.data && response.data.domains) {
          availableDomains.value = response.data.domains
        }
      } catch (error) {
        console.error('获取技术领域失败:', error)
        // 设置默认领域
        availableDomains.value = [
          { id: 'general', name: '通用软件开发', description: '通用软件开发领域的需求分析' },
          { id: 'web', name: 'Web应用开发', description: 'Web应用开发领域的需求分析' },
          { id: 'mobile', name: '移动应用开发', description: '移动应用开发领域的需求分析' },
          { id: 'ai', name: '人工智能应用', description: '人工智能应用领域的需求分析' }
        ]
      } finally {
        isLoadingDomains.value = false
      }
    }
    
    const handleDomainChange = () => {
      // 如果已经进行过分析，提示用户可能需要重新分析
      if (analysis.value) {
        ElMessage.info('技术领域已更改，您可能需要重新分析需求以获取更精准的结果')
      }
    }
    
    const analyzeRequirement = async () => {
      try {
        isAnalyzing.value = true
        
        // 调用需求分析API，传入领域信息
        const response = await axios.post(`/api/clarify/analyze/${props.projectId}`, {
          domain: selectedDomain.value
        })
        
        if (response.data) {
          // 更新分析结果
          analysis.value = response.data.analysis
          
          // 更新轮次
          await fetchRounds()
          
          // 重新加载项目信息，获取更新后的需求
          await loadProjectInfo()
          
          ElMessage.success('需求分析完成，已生成澄清问题')
          isFirstAnalysis.value = false
          
          // 绘制雷达图
          nextTick(() => {
            drawRadarChart()
          })
        }
      } catch (error) {
        console.error('分析需求失败:', error)
        ElMessage.error(error.response?.data?.error || '分析需求失败')
      } finally {
        isAnalyzing.value = false
      }
    }
    
    const submitAnswer = async (question) => {
      if (!newAnswer.value.trim()) {
        ElMessage.warning('请输入回答')
        return
      }
      
      try {
        isAnswering.value = true
        answeringQuestionId.value = question.id
        
        // 先进行语义分析
        const semanticResponse = await axios.post(
          `/api/clarify/answer/${question.id}/semantic-analysis`,
          { answer: newAnswer.value }
        )
        
        // 检查是否有严重模糊点
        let shouldProceed = true
        if (semanticResponse.data && semanticResponse.data.analysis) {
          const analysis = semanticResponse.data.analysis
          
          // 如果分析质量低于60分，提示用户
          if (analysis.answer_quality < 60) {
            const result = await ElMessageBox.confirm(
              `您的回答可能存在以下问题:\n${analysis.new_ambiguous_points.map(p => `- ${p.reason}`).join('\n')}\n\n建议修改回答以提高清晰度。是否仍要提交？`,
              '回答质量提示',
              {
                confirmButtonText: '仍要提交',
                cancelButtonText: '修改回答',
                type: 'warning'
              }
            ).catch(() => false)
            
            shouldProceed = result === 'confirm'
          }
        }
        
        if (!shouldProceed) {
          isAnswering.value = false
          answeringQuestionId.value = null
          return
        }
        
        // 提交回答
        const response = await axios.post(
          `/api/clarify/answer/${question.id}`,
          { answer: newAnswer.value }
        )
        
        if (response.data && response.data.success) {
          ElMessage.success('回答提交成功')
          
          // 更新问题状态
          const questionToUpdate = currentQuestions.value.find(q => q.id === question.id)
          if (questionToUpdate) {
            questionToUpdate.status = 'answered'
            
            // 添加回答
            if (!questionToUpdate.answers) {
              questionToUpdate.answers = []
            }
            
            questionToUpdate.answers.push({
              id: response.data.answer_id,
              answer: newAnswer.value,
              created_at: new Date().toISOString()
            })
            
            // 如果有后续问题，保存它们
            if (response.data.needs_followup && response.data.followup_questions) {
              questionToUpdate.followup_questions = response.data.followup_questions
            }
          }
          
          // 检查是否完成轮次
          if (response.data.round_completed) {
            // 重新获取轮次信息
            await fetchRounds()
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
        ElMessage.error(error.response?.data?.error || '提交回答失败')
      } finally {
        isAnswering.value = false
        answeringQuestionId.value = null
      }
    }
    
    const completeRound = async () => {
      // 如果是最后一轮，则显示完成确认对话框
      if (isLastRound.value) {
        finalizeDialogVisible.value = true
        return
      }
      
      // 否则，完成当前轮次并加载下一轮
      try {
        isCompletingRound.value = true
        
        // 目前不需要额外操作，因为当前轮次的所有问题已经回答，
        // 服务器端会自动解锁下一轮次
        
        // 重新获取轮次信息
        await fetchRounds()
        
        ElMessage.success('当前轮次已完成，进入下一轮次')
      } catch (error) {
        console.error('完成轮次失败:', error)
        ElMessage.error(error.response?.data?.error || '完成轮次失败')
      } finally {
        isCompletingRound.value = false
      }
    }
    
    const confirmFinalize = async () => {
      try {
        isCompletingRound.value = true
        
        // 调用完成澄清API
        const response = await axios.post(`/api/clarify/complete/${props.projectId}`)
        
        if (response.data && response.data.success) {
          ElMessage.success('需求澄清已完成')
          finalizeDialogVisible.value = false
          
          // 通知父组件完成
          emit('clarification-complete', finalRequirement.value)
        } else {
          ElMessage.error('完成需求澄清失败')
        }
      } catch (error) {
        console.error('完成需求澄清失败:', error)
        ElMessage.error(error.response?.data?.error || '完成需求澄清失败')
      } finally {
        isCompletingRound.value = false
      }
    }
    
    // 辅助方法
    const getStepStatus = (status) => {
      if (status === 'completed') return 'success'
      if (status === 'active') return 'process'
      if (status === 'pending') return 'wait'
      return 'wait'
    }
    
    const getClarityStatus = (score) => {
      if (score < 60) return 'exception'
      if (score < 80) return 'warning'
      return 'success'
    }
    
    const percentFormat = (percentage) => {
      return `${percentage.toFixed(0)}%`
    }
    
    const getQuestionStatusType = (status) => {
      switch (status) {
        case 'pending': return 'warning'
        case 'answered': return 'success'
        default: return 'info'
      }
    }
    
    const getQuestionStatusText = (status) => {
      switch (status) {
        case 'pending': return '待回答'
        case 'answered': return '已回答'
        default: return '未知状态'
      }
    }
    
    const formatDate = (dateString) => {
      if (!dateString) return ''
      
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    const drawRadarChart = () => {
      if (!analysis.value || !analysis.value.dimension_scores) return
      
      // 检查DOM元素是否存在
      if (!radarChart.value) return
      
      // 如果已存在图表实例，销毁它
      if (myChart.value) {
        myChart.value.dispose()
      }
      
      // 创建新的图表实例
      myChart.value = echarts.init(radarChart.value)
      
      // 准备数据
      const dimensionScores = analysis.value.dimension_scores
      const indicators = []
      const data = []
      
      // 添加雷达图的指示器
      for (const [dimension, score] of Object.entries(dimensionScores)) {
        indicators.push({
          name: getDimensionName(dimension),
          max: 100
        })
        data.push(score)
      }
      
      // 设置图表选项
      const option = {
        title: {
          text: '需求维度完整度评估',
          left: 'center'
        },
        tooltip: {},
        radar: {
          indicator: indicators,
          radius: '60%'
        },
        series: [
          {
            name: '维度完整度',
            type: 'radar',
            data: [
              {
                value: data,
                name: '完整度评分',
                areaStyle: {
                  color: 'rgba(64, 158, 255, 0.6)'
                },
                lineStyle: {
                  color: '#409EFF'
                },
                itemStyle: {
                  color: '#409EFF'
                }
              }
            ]
          }
        ]
      }
      
      // 应用选项
      myChart.value.setOption(option)
      
      // 响应窗口大小变化
      window.addEventListener('resize', () => {
        myChart.value.resize()
      })
    }
    
    const getDimensionName = (dimension) => {
      const dimensionMap = {
        'what': 'What (功能)',
        'why': 'Why (目的)',
        'who': 'Who (用户)',
        'when': 'When (场景)',
        'where': 'Where (环境)',
        'how': 'How (方法)',
        'how_much': 'How much (约束)'
      }
      return dimensionMap[dimension] || dimension
    }
    
    // 上传相关方法
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
    
    const handleExceed = () => {
      ElMessage.warning('只能上传一个文件，请先删除已上传的文件')
    }
    
    const handleRemove = () => {
      fileList.value = []
    }
    
    const uploadRequirementFile = async (options) => {
      try {
        const formData = new FormData()
        formData.append('file', options.file)
        
        const response = await axios.post(
          `/api/projects/${props.projectId}/upload-requirement`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          }
        )
        
        if (response.data && response.data.success) {
          ElMessage.success('需求文档上传解析成功')
          
          // 重新加载项目信息
          await loadProjectInfo()
          
          // 如果分析结果可用，更新它
          if (response.data.clarity_score) {
            if (!analysis.value) analysis.value = {}
            analysis.value.clarity_score = response.data.clarity_score
            analysis.value.ambiguous_points = response.data.ambiguous_points || []
            
            // 自动启动分析
            analyzeRequirement()
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
      }
    }
    
    // 知识图谱相关方法
    const fetchKnowledgeGraph = async () => {
      try {
        isLoadingGraph.value = true
        const response = await axios.get(`/api/clarify/knowledge-graph/${props.projectId}`);
        
        if (response.data && response.data.graph) {
          knowledgeGraph.value = response.data.graph;
          nextTick(() => {
            renderKnowledgeGraph(response.data.graph);
          });
          ElMessage.success('需求知识图谱生成成功');
        } else {
          ElMessage.warning('知识图谱数据不完整');
        }
      } catch (error) {
        console.error('获取需求知识图谱失败:', error);
        ElMessage.error(error.response?.data?.error || '获取需求知识图谱失败');
      } finally {
        isLoadingGraph.value = false;
      }
    }
    
    const renderKnowledgeGraph = (graphData) => {
      // 初始化图表
      const container = document.getElementById('knowledge-graph-container');
      if (!container) return;
      
      const width = container.scrollWidth;
      const height = container.scrollHeight || 500;
      
      // 销毁已有实例
      if (graphInstance.value) {
        graphInstance.value.destroy();
      }
      
      // 创建新实例
      graphInstance.value = new G6.Graph({
        container,
        width,
        height,
        modes: {
          default: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select']
        },
        layout: {
          type: 'force',
          preventOverlap: true,
          linkDistance: 100
        },
        defaultNode: {
          size: 30,
          style: {
            fill: '#C6E5FF',
            stroke: '#5B8FF9',
            lineWidth: 1
          },
          labelCfg: {
            style: {
              fill: '#000',
              fontSize: 12
            }
          }
        },
        defaultEdge: {
          style: {
            stroke: '#aaa',
            lineWidth: 1,
            endArrow: true
          },
          labelCfg: {
            autoRotate: true,
            style: {
              fill: '#666',
              fontSize: 10
            }
          }
        },
        // 自适应布局
        fitView: true,
        fitViewPadding: [20, 40, 20, 20]
      });
      
      // 转换数据格式适应G6
      const g6Data = {
        nodes: graphData.nodes.map(node => ({
          id: node.id,
          label: node.label,
          type: 'circle',
          style: {
            fill: getDimensionColor(node.dimension),
            stroke: getDimensionColor(node.dimension, true)
          },
          // 添加维度和类型信息用于后续交互
          dimension: node.dimension,
          nodeType: node.type,
          description: node.description
        })),
        edges: graphData.edges.map(edge => ({
          source: edge.source,
          target: edge.target,
          label: edge.label
        }))
      };
      
      graphInstance.value.data(g6Data);
      graphInstance.value.render();
      
      // 添加节点点击事件
      graphInstance.value.on('node:click', evt => {
        const node = evt.item.getModel();
        ElMessage.info(`${node.label}: ${node.description || '无描述'}`);
      });
      
      // 自适应窗口大小变化
      window.addEventListener('resize', () => {
        if (graphInstance.value) {
          graphInstance.value.changeSize(container.scrollWidth, container.scrollHeight || 500);
        }
      });
    }
    
    // 根据维度获取对应颜色
    const getDimensionColor = (dimension, isStroke = false) => {
      const colors = {
        what: '#91CC75',
        why: '#FAC858',
        who: '#5470C6',
        when: '#EE6666',
        where: '#73C0DE',
        how: '#3BA272',
        how_much: '#FC8452'
      };
      
      const defaultColor = '#B4B4B4';
      const color = colors[dimension] || defaultColor;
      
      return isStroke ? darkenColor(color) : color;
    }
    
    // 辅助函数：颜色加深
    const darkenColor = (color) => {
      // 简单处理：移除#，分别获取RGB值
      const hex = color.replace('#', '');
      let r = parseInt(hex.substr(0, 2), 16);
      let g = parseInt(hex.substr(2, 2), 16);
      let b = parseInt(hex.substr(4, 2), 16);
      
      // 各减少20%
      r = Math.floor(r * 0.8);
      g = Math.floor(g * 0.8);
      b = Math.floor(b * 0.8);
      
      // 转回十六进制
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }
    
    // 初始化
    onMounted(() => {
      loadProjectInfo()
      fetchRounds()
      fetchAvailableDomains()
    })
    
    // 监听轮次变化，更新激活的问题
    watch(currentQuestions, (newQuestions) => {
      if (newQuestions && newQuestions.length > 0) {
        // 默认展开第一个未回答的问题
        const firstPendingQuestion = newQuestions.find(q => q.status === 'pending')
        if (firstPendingQuestion) {
          activeQuestions.value = [firstPendingQuestion.id]
        }
      }
    })
    
    return {
      rounds,
      analysis,
      activeRound,
      activeQuestions,
      newAnswer,
      isAnalyzing,
      isAnswering,
      isCompletingRound,
      answeringQuestionId,
      currentRequirement,
      finalizeDialogVisible,
      fileList,
      radarChart,
      isFirstAnalysis,
      selectedDomain,
      availableDomains,
      isLoadingDomains,
      currentRound,
      currentQuestions,
      hasCurrentRoundPendingQuestions,
      isLastRound,
      finalRequirement,
      loadProjectInfo,
      fetchRounds,
      analyzeRequirement,
      submitAnswer,
      completeRound,
      confirmFinalize,
      getStepStatus,
      getClarityStatus,
      percentFormat,
      getQuestionStatusType,
      getQuestionStatusText,
      formatDate,
      drawRadarChart,
      getDimensionName,
      beforeUpload,
      handleExceed,
      handleRemove,
      uploadRequirementFile,
      fetchAvailableDomains,
      handleDomainChange,
      knowledgeGraph,
      isLoadingGraph,
      fetchKnowledgeGraph,
      renderKnowledgeGraph,
      getDimensionColor,
      darkenColor
    }
  }
}
</script>

<style scoped>
.requirement-5w2h {
  padding: 20px;
}

.clarifier-container {
  margin-top: 20px;
}

/* 领域选择器样式 */
.domain-selector {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f8f9fb;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}

.domain-select {
  width: 300px;
}

.domain-description {
  margin-top: 10px;
  color: #909399;
  font-size: 0.9em;
}

.domain-option {
  display: flex;
  flex-direction: column;
}

.domain-option small {
  color: #909399;
  font-size: 0.8em;
}

/* 一致性问题样式 */
.consistency-issues {
  margin-top: 20px;
}

.issue-content {
  margin-top: 10px;
}

.issue-terms {
  margin-bottom: 10px;
}

.term-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.issue-question {
  font-style: italic;
  color: #606266;
  margin-top: 5px;
}

/* 问题标签样式 */
.question-tags {
  display: flex;
  align-items: center;
  gap: 5px;
}

.severity-tag, .followup-tag {
  margin-left: 5px;
}

/* 后续问题样式 */
.followup-questions {
  margin-top: 15px;
}

.followup-list {
  margin-top: 10px;
}

.followup-item {
  margin-bottom: 5px;
}

.followup-number {
  font-weight: bold;
  margin-right: 5px;
}

.followup-text {
  color: #606266;
}

.progress-container {
  margin-bottom: 20px;
}

.analysis-results {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
}

.clarity-assessment {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.score-container {
  flex-basis: 300px;
  flex-grow: 1;
}

.dimension-chart {
  flex-basis: 400px;
  flex-grow: 1;
}

.radar-chart {
  width: 100%;
  height: 300px;
}

.score-label {
  margin-top: 5px;
  text-align: center;
  font-weight: bold;
}

.current-requirement {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
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

.upload-section {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
}

.analyze-actions {
  margin-bottom: 20px;
  display: flex;
  justify-content: center;
}

.round-questions {
  margin-top: 20px;
}

.round-description {
  margin-bottom: 15px;
  color: #606266;
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

.round-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
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

.finalize-content {
  max-height: 500px;
  overflow-y: auto;
}

.final-requirement {
  white-space: pre-wrap;
  word-wrap: break-word;
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}

.final-clarity-assessment {
  margin-top: 20px;
}

.final-score-container {
  margin: 15px 0;
}

.dimension-list {
  margin-top: 15px;
}

.dimension-list ul {
  list-style-type: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.dimension-list li {
  flex-basis: 200px;
  padding: 5px 10px;
  background-color: #f5f7fa;
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

/* 知识图谱相关样式 */
.knowledge-graph-section {
  margin-top: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
}

.graph-actions {
  margin-bottom: 10px;
  text-align: right;
}

.knowledge-graph-container {
  width: 100%;
  height: 400px;
  background-color: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.graph-legend {
  margin-top: 10px;
  padding: 10px;
  border-top: 1px dashed #e0e0e0;
}

.legend-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-right: 15px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 5px;
}

.legend-label {
  font-size: 0.8em;
  color: #606266;
}
</style> 