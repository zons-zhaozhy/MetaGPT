# MetaGPT Web MVP可视可控实现方案

## 1. 目标与设计原则

- **目标**：让用户对MetaGPT开发全过程"可视、可控、可交互"，特别是需求澄清、阶段推进、代理工作流等核心环节。
- **原则**：
  - 分阶段执行，关键节点用户可干预
  - 实时展示中间产物、日志、进度
  - 需求澄清环节高度交互，支持多轮澄清与反馈
  - 技术方案最小侵入、可扩展、易维护

---

## 2. 技术风险与缓解措施可行性分析

| 风险点                 | 缓解措施                         | 可行性分析与结论                |
|-----------------------|--------------------------------|-----------------------------|
| 核心逻辑侵入风险         | 采用装饰器/事件监听/分阶段API，最小化对MetaGPT主流程修改 | ✅ 通过外部包装和状态持久化，主流程无需大改，兼容性好 |
| 状态管理复杂性           | 阶段状态持久化、幂等API、异常恢复机制           | ✅ SQLite/JSON持久化+API幂等，易于实现和维护 |
| 资源使用效率             | 按需加载、阶段性清理、状态序列化               | ✅ 仅保存必要上下文，内存压力可控           |
| 用户交互复杂度           | 前端分阶段UI、引导式交互、进度可视化            | ✅ 组件化UI+WebSocket/轮询，主流前端技术可实现 |
| 代理活动可视化           | 日志/事件流捕获、前端实时渲染                  | ✅ 日志钩子+事件推送，前后端均有成熟方案     |

结论：所有关键风险均有成熟可行的工程化缓解措施，方案可落地。

---

## 3. MVP阶段性实现方案

### 阶段1：分阶段执行与状态持久化

- **目标**：实现MetaGPT分阶段执行（如需求分析、架构设计、编码等），每阶段结束后持久化状态，前端可查询。
- **核心功能**：
  - 后端API：`/api/projects/<id>/phases`（查询阶段）、`/api/projects/<id>/execute/<phase>`（执行阶段）
  - 阶段状态JSON持久化，支持恢复/重试
  - 前端展示阶段进度、当前状态
- **验证标准**：用户可见每个阶段进度，阶段可单独执行/重试。
- **实现细节**：
  ```python
  # 状态持久化示例
  class ProjectPhaseManager:
      def __init__(self, project_id):
          self.project_id = project_id
          self.db_path = f"data/projects/{project_id}/phases.json"
          
      def save_phase_state(self, phase, state, artifacts):
          """保存阶段状态到JSON文件"""
          phase_data = {
              "phase": phase,
              "state": state,  # running, completed, failed
              "artifacts": artifacts,
              "timestamp": datetime.now().isoformat()
          }
          # 确保目录存在
          os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
          
          # 读取现有数据
          data = {}
          if os.path.exists(self.db_path):
              with open(self.db_path, "r") as f:
                  data = json.load(f)
          
          # 更新阶段数据
          data[phase] = phase_data
          
          # 写入文件
          with open(self.db_path, "w") as f:
              json.dump(data, f, indent=2)
              
      def get_phase_state(self, phase=None):
          """获取特定阶段或所有阶段的状态"""
          if not os.path.exists(self.db_path):
              return {} if phase is None else None
              
          with open(self.db_path, "r") as f:
              data = json.load(f)
              
          return data if phase is None else data.get(phase)
  ```

### 阶段2：需求澄清与多轮交互

- **目标**：实现需求澄清多轮问答，用户可补充/修正需求，AI动态生成澄清问题。
- **核心功能**：
  - 后端API：`/api/projects/<id>/clarify`（生成澄清问题）、`/api/projects/<id>/clarify/answer`（提交回答）
  - 前端交互式问答UI，展示澄清历史与最终需求文档
- **验证标准**：用户能多轮补充/修正需求，最终需求文档更完整。
- **实现细节**：
  ```python
  # 需求澄清API实现示例
  @app.route('/api/projects/<id>/clarify', methods=['GET'])
  def generate_clarification_questions(id):
      """生成澄清问题"""
      # 获取项目当前需求
      project = get_project(id)
      requirement = project.get('requirement', '')
      
      # 使用LLM生成澄清问题
      questions = generate_questions_with_llm(requirement)
      
      # 保存到项目状态
      save_clarification_questions(id, questions)
      
      return jsonify({
          'project_id': id,
          'questions': questions
      })
      
  @app.route('/api/projects/<id>/clarify/answer', methods=['POST'])
  def submit_clarification_answers(id):
      """提交澄清问题的回答"""
      data = request.json
      question_id = data.get('question_id')
      answer = data.get('answer')
      
      # 保存回答
      save_answer(id, question_id, answer)
      
      # 更新需求文档
      update_requirement_doc(id, question_id, answer)
      
      # 检查是否需要生成后续问题
      needs_followup = check_if_needs_followup(id, question_id, answer)
      
      return jsonify({
          'success': True,
          'needs_followup': needs_followup
      })
  ```

### 阶段3：代理活动与中间产物可视化

- **目标**：实时展示各代理（产品经理、架构师等）思考过程、日志和中间文档。
- **核心功能**：
  - 后端事件流/日志API，推送各阶段日志与产物
  - 前端实时渲染代理活动流、文档、进度条
- **验证标准**：用户可见每个代理的工作过程和中间产物。
- **实现细节**：
  ```python
  # 日志钩子实现示例
  class AgentLogHandler:
      def __init__(self, project_id):
          self.project_id = project_id
          self.logs = []
          self.subscribers = set()
          
      def log(self, agent_name, message, message_type="log"):
          """记录代理日志"""
          log_entry = {
              "timestamp": datetime.now().isoformat(),
              "agent": agent_name,
              "message": message,
              "type": message_type  # log, artifact, error
          }
          self.logs.append(log_entry)
          
          # 推送给所有订阅者
          self.notify_subscribers(log_entry)
          
      def notify_subscribers(self, log_entry):
          """通知所有订阅者"""
          for subscriber in self.subscribers:
              subscriber(log_entry)
              
      def subscribe(self, callback):
          """添加日志订阅者"""
          self.subscribers.add(callback)
          
      def unsubscribe(self, callback):
          """移除日志订阅者"""
          self.subscribers.discard(callback)
              
      def get_logs(self, agent=None, limit=100, offset=0):
          """获取日志，可按代理过滤"""
          filtered_logs = [log for log in self.logs if agent is None or log["agent"] == agent]
          return filtered_logs[offset:offset+limit]
  
  # WebSocket实现示例
  @socketio.on('connect')
  def handle_connect():
      session['room'] = request.args.get('project_id')
      join_room(session['room'])
      
  @socketio.on('subscribe_logs')
  def handle_subscribe_logs(data):
      project_id = data.get('project_id')
      # 获取项目日志处理器
      log_handler = get_project_log_handler(project_id)
      
      # 创建WebSocket推送回调
      def log_callback(log_entry):
          emit('agent_log', log_entry, room=project_id)
          
      # 注册回调
      log_handler.subscribe(log_callback)
      
      # 存储在会话中以便断开连接时清理
      session['log_callback'] = log_callback
      session['project_log_handler'] = log_handler
  ```

### 阶段4：用户干预与流程控制

- **目标**：关键节点暂停，用户可确认/修改/跳过/终止流程。
- **核心功能**：
  - 后端支持阶段暂停/继续/终止API
  - 前端提供控制按钮与反馈入口
- **验证标准**：用户可主动控制流程推进，体验"可控"。
- **实现细节**：
  ```python
  # 流程控制API示例
  @app.route('/api/projects/<id>/control/<phase>', methods=['POST'])
  def control_project_phase(id, phase):
      """控制项目阶段执行"""
      data = request.json
      action = data.get('action')  # pause, resume, skip, abort
      
      # 获取项目执行控制器
      controller = get_project_controller(id)
      
      if action == 'pause':
          controller.pause_phase(phase)
          return jsonify({"status": "paused", "phase": phase})
          
      elif action == 'resume':
          controller.resume_phase(phase)
          return jsonify({"status": "resumed", "phase": phase})
          
      elif action == 'skip':
          controller.skip_phase(phase)
          return jsonify({"status": "skipped", "phase": phase})
          
      elif action == 'abort':
          controller.abort_phase(phase)
          return jsonify({"status": "aborted", "phase": phase})
          
      return jsonify({"error": "Invalid action"}), 400
  
  # 前端控制组件示例（React）
  function PhaseControls({ projectId, phase, status }) {
      const [loading, setLoading] = useState(false);
      
      async function handleControl(action) {
          setLoading(true);
          try {
              const response = await axios.post(
                  `/api/projects/${projectId}/control/${phase}`,
                  { action }
              );
              // 更新UI状态
          } catch (error) {
              console.error("Control action failed:", error);
          } finally {
              setLoading(false);
          }
      }
      
      return (
          <div className="phase-controls">
              {status === 'running' && (
                  <Button 
                      onClick={() => handleControl('pause')} 
                      loading={loading}
                  >
                      暂停
                  </Button>
              )}
              
              {status === 'paused' && (
                  <Button 
                      onClick={() => handleControl('resume')} 
                      loading={loading}
                  >
                      继续
                  </Button>
              )}
              
              {(status === 'paused' || status === 'running') && (
                  <Button 
                      onClick={() => handleControl('skip')} 
                      loading={loading}
                      type="warning"
                  >
                      跳过
                  </Button>
              )}
              
              <Button 
                  onClick={() => handleControl('abort')} 
                  loading={loading}
                  type="danger"
              >
                  终止
              </Button>
          </div>
      );
  }
  ```

---

## 4. 推进计划

1. **第1-2周**：实现分阶段执行与状态持久化，前后端基础API/UI联调
   - 完成状态持久化模块
   - 实现基础API
   - 搭建前端项目结构
   - API与前端联调

2. **第3-4周**：开发需求澄清多轮交互，完善前端交互体验
   - 实现需求澄清问题生成算法
   - 开发交互式问答UI组件
   - 完成需求文档动态更新机制
   - 前后端联调测试

3. **第5-6周**：实现代理活动可视化与中间产物展示
   - 开发日志捕获钩子
   - 实现WebSocket实时推送
   - 开发前端实时渲染组件
   - 完成中间产物展示功能

4. **第7-8周**：打通用户干预与流程控制，整体联调与测试
   - 实现流程控制机制
   - 开发前端控制面板
   - 完成异常处理与恢复机制
   - 系统整体联调与测试

---

## 5. 技术栈选择

### 前端技术栈

- **框架**：React.js 18.x
- **UI库**：Ant Design 5.x
- **状态管理**：Redux Toolkit
- **API请求**：Axios
- **实时通信**：Socket.io-client 4.x
- **可视化**：ECharts 5.x (图表)、React Flow 11.x (流程图)
- **代码编辑器**：Monaco Editor 0.44.x

### 后端技术栈

- **Web框架**：Flask 3.x / FastAPI 0.110.x
- **数据存储**：SQLite (轻量)、MongoDB 6.x (可扩展)
- **缓存/消息队列**：Redis 7.x
- **实时通信**：Flask-SocketIO / FastAPI WebSockets
- **任务队列**：Celery 5.x (异步任务)
- **认证**：Flask-JWT-Extended / FastAPI OAuth2

---

## 6. 验证与交付标准

- 每阶段有可用Demo，用户可体验"可视、可控、可交互"
- 需求澄清、阶段推进、代理可视化等核心功能可用
- 关键风险点均有工程化缓解措施，系统稳定可扩展
- 通过用户测试，收集并响应用户反馈
- 完整的部署文档和操作手册 