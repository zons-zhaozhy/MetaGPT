from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
import os
import uuid
import json
from datetime import datetime
import traceback

from utils.requirement_analyzer import RequirementAnalyzer5W2H

clarify_bp = Blueprint('clarify', __name__, url_prefix='/api/clarify')

@clarify_bp.route('/analyze/<project_id>', methods=['POST'])
@jwt_required()
def analyze_requirement(project_id):
    """
    分析项目需求并生成多维度评估结果和结构化澄清问题
    """
    try:
        # 获取领域信息（如果提供）
        data = request.json or {}
        domain = data.get('domain', 'general')  # 默认为通用领域
        
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", 
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        # 获取项目需求
        requirement = project[2] or ""
        
        # 检查需求是否为空
        if not requirement.strip():
            return jsonify({"error": "项目需求为空，请先输入需求或上传需求文档"}), 400
        
        # 使用新的5W2H需求分析器，传入领域信息
        analyzer = RequirementAnalyzer5W2H(
            openai_api_key=current_app.config.get('OPENAI_API_KEY'),
            domain=domain
        )
        analysis = analyzer.analyze_requirement(requirement)
        
        # 生成结构化的轮次问题
        structured_questions = analyzer.generate_structured_questions(analysis)
        
        # 检查是否已经有分析结果
        existing_analysis = conn.execute(
            "SELECT * FROM requirement_analysis WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        
        current_time = datetime.now().isoformat()
        
        # 保存分析结果到数据库
        if existing_analysis:
            # 更新现有分析，包含一致性问题
            conn.execute(
                """
                UPDATE requirement_analysis 
                SET clarity_score = ?, dimension_scores = ?, 
                    ambiguous_points = ?, consistency_issues = ?, updated_at = ? 
                WHERE project_id = ?
                """,
                (
                    analysis.get("clarity_score", 0),
                    json.dumps(analysis.get("dimension_scores", {})),
                    json.dumps(analysis.get("ambiguous_points", [])),
                    json.dumps(analysis.get("consistency_issues", [])),
                    current_time,
                    project_id
                )
            )
        else:
            # 创建新分析，包含一致性问题
            conn.execute(
                """
                INSERT INTO requirement_analysis 
                (id, project_id, clarity_score, dimension_scores, 
                 ambiguous_points, consistency_issues, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    project_id,
                    analysis.get("clarity_score", 0),
                    json.dumps(analysis.get("dimension_scores", {})),
                    json.dumps(analysis.get("ambiguous_points", [])),
                    json.dumps(analysis.get("consistency_issues", [])),
                    current_time,
                    current_time
                )
            )
        
        # 创建或更新澄清轮次
        # 首先，检查是否已经有轮次
        existing_rounds = conn.execute(
            "SELECT * FROM clarification_rounds WHERE project_id = ? ORDER BY round_number",
            (project_id,)
        ).fetchall()
        
        # 需要创建的轮次定义
        rounds_to_create = [
            {
                "id": "round1", 
                "name": "核心功能与目标确认", 
                "description": "确认系统的核心功能、商业价值和主要用户",
                "questions": structured_questions["round1"],
                "round_number": 1
            },
            {
                "id": "round2", 
                "name": "边界条件与约束确认", 
                "description": "确认系统的使用场景、环境、操作流程和限制条件",
                "questions": structured_questions["round2"],
                "round_number": 2
            }
        ]
        
        # 如果第三轮有问题，也添加
        if structured_questions["round3"]:
            rounds_to_create.append({
                "id": "round3", 
                "name": "特定模糊点跟进", 
                "description": "针对性解决剩余关键问题",
                "questions": structured_questions["round3"],
                "round_number": 3
            })
        
        # 如果已有轮次，更新它们；否则创建新轮次
        if existing_rounds:
            # 更新现有轮次
            for existing_round in existing_rounds:
                round_id = existing_round[2]  # round_id
                round_number = existing_round[3]  # round_number
                
                # 找到对应的新轮次
                matching_round = next(
                    (r for r in rounds_to_create if r["round_number"] == round_number), 
                    None
                )
                
                if matching_round:
                    # 更新轮次基本信息
                    conn.execute(
                        """
                        UPDATE clarification_rounds
                        SET name = ?, description = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            matching_round["name"],
                            matching_round["description"],
                            current_time,
                            existing_round[0]  # id
                        )
                    )
                    
                    # 更新问题（先删除旧问题，再添加新问题）
                    conn.execute(
                        "DELETE FROM clarification_questions WHERE round_id = ?",
                        (existing_round[0],)
                    )
                    
                    # 添加新问题
                    for i, question in enumerate(matching_round["questions"]):
                        # 检测问题是否来自高严重性模糊点
                        severity = "medium"
                        for point in analysis.get("ambiguous_points", []):
                            if point.get("clarification_question") == question:
                                severity = point.get("severity", "medium")
                                break
                                
                        conn.execute(
                            """
                            INSERT INTO clarification_questions
                            (id, project_id, round_id, question, priority, severity, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(uuid.uuid4()),
                                project_id,
                                existing_round[0],
                                question,
                                i,
                                severity,
                                "pending",
                                current_time
                            )
                        )
        else:
            # 创建新轮次和问题
            for round_info in rounds_to_create:
                round_id = str(uuid.uuid4())
                
                conn.execute(
                    """
                    INSERT INTO clarification_rounds
                    (id, project_id, round_id, round_number, name, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        project_id,
                        round_info["id"],
                        round_info["round_number"],
                        round_info["name"],
                        round_info["description"],
                        "pending" if round_info["round_number"] == 1 else "locked",
                        current_time,
                        current_time
                    )
                )
                
                # 添加问题
                for i, question in enumerate(round_info["questions"]):
                    # 检测问题是否来自高严重性模糊点
                    severity = "medium"
                    for point in analysis.get("ambiguous_points", []):
                        if point.get("clarification_question") == question:
                            severity = point.get("severity", "medium")
                            break
                            
                    conn.execute(
                        """
                        INSERT INTO clarification_questions
                        (id, project_id, round_id, question, priority, severity, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            project_id,
                            round_id,
                            question,
                            i,
                            severity,
                            "pending",
                            current_time
                        )
                    )
        
        conn.commit()
        
        # 记录智能体活动
        from api.projects import log_agent_activity
        log_agent_activity(
            project_id=project_id,
            phase_id="requirement_analysis",
            agent_name="需求分析器",
            message=f"需求5W2H分析完成，整体清晰度得分: {analysis.get('clarity_score', 0):.1f}/100",
            message_type="analysis"
        )
        
        # 返回分析结果
        return jsonify({
            "project_id": project_id,
            "analysis": analysis,
            "structured_questions": structured_questions,
            "rounds": rounds_to_create
        })
    
    except Exception as e:
        print(f"需求分析错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/rounds/<project_id>', methods=['GET'])
@jwt_required()
def get_clarification_rounds(project_id):
    """
    获取项目的需求澄清轮次信息
    """
    try:
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", 
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        # 获取轮次
        rounds = conn.execute(
            """
            SELECT id, project_id, round_id, round_number, name, description, status, created_at, updated_at
            FROM clarification_rounds
            WHERE project_id = ?
            ORDER BY round_number
            """,
            (project_id,)
        ).fetchall()
        
        result = []
        for round_info in rounds:
            round_id = round_info[0]
            
            # 获取轮次的问题
            questions = conn.execute(
                """
                SELECT id, question, priority, severity, status, created_at
                FROM clarification_questions
                WHERE round_id = ?
                ORDER BY priority
                """,
                (round_id,)
            ).fetchall()
            
            question_list = []
            for q in questions:
                question_data = {
                    "id": q[0],
                    "question": q[1],
                    "priority": q[2],
                    "severity": q[3] if len(q) > 3 else "medium",  # 兼容旧数据
                    "status": q[4] if len(q) > 4 else q[3],  # 兼容旧数据
                    "created_at": q[5] if len(q) > 5 else q[4]  # 兼容旧数据
                }
                
                # 获取问题的回答
                answers = conn.execute(
                    """
                    SELECT id, answer, created_at
                    FROM clarification_answers
                    WHERE question_id = ?
                    ORDER BY created_at
                    """,
                    (q[0],)
                ).fetchall()
                
                question_data["answers"] = [
                    {
                        "id": a[0],
                        "answer": a[1],
                        "created_at": a[2]
                    } for a in answers
                ]
                
                question_list.append(question_data)
            
            # 添加轮次信息
            result.append({
                "id": round_info[0],
                "project_id": round_info[1],
                "round_id": round_info[2],
                "round_number": round_info[3],
                "name": round_info[4],
                "description": round_info[5],
                "status": round_info[6],
                "created_at": round_info[7],
                "updated_at": round_info[8],
                "questions": question_list
            })
        
        # 获取需求分析结果
        analysis = conn.execute(
            """
            SELECT clarity_score, dimension_scores, ambiguous_points, consistency_issues, updated_at
            FROM requirement_analysis
            WHERE project_id = ?
            """,
            (project_id,)
        ).fetchone()
        
        analysis_data = None
        if analysis:
            analysis_data = {
                "clarity_score": analysis[0],
                "dimension_scores": json.loads(analysis[1]) if analysis[1] else {},
                "ambiguous_points": json.loads(analysis[2]) if analysis[2] else [],
                "consistency_issues": json.loads(analysis[3]) if len(analysis) > 3 and analysis[3] else [],
                "updated_at": analysis[4] if len(analysis) > 4 else analysis[3]
            }
        
        return jsonify({
            "project_id": project_id,
            "rounds": result,
            "analysis": analysis_data
        })
    
    except Exception as e:
        print(f"获取澄清轮次错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/questions/<round_id>', methods=['GET'])
@jwt_required()
def get_round_questions(round_id):
    """
    获取指定轮次的澄清问题
    """
    try:
        conn = current_app.db
        
        # 检查轮次是否存在
        round_info = conn.execute(
            "SELECT * FROM clarification_rounds WHERE id = ?", 
            (round_id,)
        ).fetchone()
        
        if not round_info:
            return jsonify({"error": "Round not found"}), 404
        
        # 获取轮次的问题
        questions = conn.execute(
            """
            SELECT id, question, priority, severity, status, created_at
            FROM clarification_questions
            WHERE round_id = ?
            ORDER BY priority
            """,
            (round_id,)
        ).fetchall()
        
        result = []
        for q in questions:
            severity = q[3] if len(q) > 3 else "medium"  # 兼容旧数据
            status = q[4] if len(q) > 4 else q[3]  # 兼容旧数据
            created_at = q[5] if len(q) > 5 else q[4]  # 兼容旧数据
            
            question_data = {
                "id": q[0],
                "question": q[1],
                "priority": q[2],
                "severity": severity,
                "status": status,
                "created_at": created_at
            }
            
            # 获取问题的回答
            answers = conn.execute(
                """
                SELECT id, answer, created_at
                FROM clarification_answers
                WHERE question_id = ?
                ORDER BY created_at
                """,
                (q[0],)
            ).fetchall()
            
            question_data["answers"] = [
                {
                    "id": a[0],
                    "answer": a[1],
                    "created_at": a[2]
                } for a in answers
            ]
            
            result.append(question_data)
        
        return jsonify({
            "round_id": round_id,
            "project_id": round_info[1],  # project_id
            "round_info": {
                "id": round_info[0],
                "round_id": round_info[2],
                "round_number": round_info[3],
                "name": round_info[4],
                "description": round_info[5],
                "status": round_info[6]
            },
            "questions": result
        })
    
    except Exception as e:
        print(f"获取轮次问题错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/answer/<question_id>', methods=['POST'])
@jwt_required()
def submit_answer(question_id):
    """
    提交问题答案
    """
    try:
        data = request.json
        if not data or 'answer' not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        answer = data.get('answer')
        
        conn = current_app.db
        
        # 检查问题是否存在
        question = conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?",
            (question_id,)
        ).fetchone()
        
        if not question:
            return jsonify({"error": "Question not found"}), 404
        
        project_id = question[1]  # project_id
        round_id = question[2]  # round_id
        
        # 保存回答
        answer_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        
        conn.execute(
            """
            INSERT INTO clarification_answers 
            (id, question_id, project_id, answer, created_at) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (answer_id, question_id, project_id, answer, current_time)
        )
        
        # 更新问题状态
        conn.execute(
            "UPDATE clarification_questions SET status = 'answered' WHERE id = ?",
            (question_id,)
        )
        
        # 分析回答，检查是否需要后续问题
        needs_followup = False
        followup_questions = []
        
        # 使用增强的语义分析功能
        openai_api_key = current_app.config.get('OPENAI_API_KEY')
        if openai_api_key:
            # 获取原始问题
            question_text = question[3]  # question
            
            # 获取项目需求和领域
            project = conn.execute(
                "SELECT requirement, domain FROM projects WHERE id = ?",
                (project_id,)
            ).fetchone()
            
            if project and project[0]:
                try:
                    # 获取项目领域
                    domain = project[1] if len(project) > 1 else "general"
                    
                    # 创建分析器实例
                    analyzer = RequirementAnalyzer5W2H(
                        openai_api_key=openai_api_key,
                        domain=domain
                    )
                    
                    # 使用语义分析功能
                    analysis = analyzer.analyze_answer_semantically(
                        question_text, 
                        answer, 
                        project[0]  # 需求文本
                    )
                    
                    # 检查是否需要后续问题
                    if analysis.get("needs_followup", False):
                        needs_followup = True
                        followup_questions = analysis.get("suggested_followup_questions", [])
                        
                        # 记录分析结果
                        log_agent_activity(
                            project_id=project_id,
                            phase_id="requirement_analysis",
                            agent_name="需求分析器",
                            message=f"回答质量评分: {analysis.get('answer_quality', 0)}/100，检测到 {len(analysis.get('new_ambiguous_points', []))} 个模糊点",
                            message_type="analysis"
                        )
                    
                except Exception as e:
                    print(f"回答语义分析错误: {e}")
                    # 错误时尝试使用基础分析方法
                    basic_analysis = analyzer._rule_based_answer_analysis(question_text, answer)
                    needs_followup = basic_analysis.get("needs_followup", False)
                    followup_questions = basic_analysis.get("suggested_followup_questions", [])
        
        # 检查轮次中是否所有问题都已回答
        total_questions = conn.execute(
            "SELECT COUNT(*) FROM clarification_questions WHERE round_id = ?",
            (round_id,)
        ).fetchone()[0]
        
        answered_questions = conn.execute(
            "SELECT COUNT(*) FROM clarification_questions WHERE round_id = ? AND status = 'answered'",
            (round_id,)
        ).fetchone()[0]
        
        # 如果该轮次所有问题都已回答，更新轮次状态并解锁下一轮
        if total_questions == answered_questions:
            # 更新当前轮次状态
            conn.execute(
                "UPDATE clarification_rounds SET status = 'completed', updated_at = ? WHERE id = ?",
                (current_time, round_id)
            )
            
            # 获取当前轮次信息
            current_round = conn.execute(
                "SELECT round_number FROM clarification_rounds WHERE id = ?",
                (round_id,)
            ).fetchone()
            
            if current_round:
                next_round_number = current_round[0] + 1
                
                # 尝试解锁下一轮
                next_round = conn.execute(
                    """
                    SELECT id FROM clarification_rounds 
                    WHERE project_id = ? AND round_number = ?
                    """,
                    (project_id, next_round_number)
                ).fetchone()
                
                if next_round:
                    conn.execute(
                        "UPDATE clarification_rounds SET status = 'active', updated_at = ? WHERE id = ?",
                        (current_time, next_round[0])
                    )
        
        # 更新项目需求文本
        # 获取现有需求
        project = conn.execute(
            "SELECT requirement FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()
        
        if project:
            existing_requirement = project[0] or ""
            question_text = question[3]  # question
            
            # 获取轮次信息
            round_info = conn.execute(
                "SELECT name FROM clarification_rounds WHERE id = ?",
                (round_id,)
            ).fetchone()
            
            round_name = round_info[0] if round_info else "需求澄清"
            
            # 添加问答到需求中
            updated_requirement = f"{existing_requirement}\n\n## {round_name}\n问题：{question_text}\n回答：{answer}"
            
            conn.execute(
                "UPDATE projects SET requirement = ? WHERE id = ?",
                (updated_requirement, project_id)
            )
        
        # 如果需要后续问题，添加这些问题
        if needs_followup and followup_questions:
            for i, followup_question in enumerate(followup_questions):
                if not followup_question:
                    continue
                    
                # 创建后续问题
                conn.execute(
                    """
                    INSERT INTO clarification_questions
                    (id, project_id, round_id, question, priority, severity, status, created_at, is_followup, parent_question_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        project_id,
                        round_id,
                        followup_question,
                        100 + i,  # 高优先级，放在当前轮次末尾
                        "high",
                        "pending",
                        current_time,
                        1,  # 标记为后续问题
                        question_id  # 关联到父问题
                    )
                )
        
        conn.commit()
        
        # 记录活动
        from api.projects import log_agent_activity
        log_agent_activity(
            project_id=project_id,
            phase_id="requirement_analysis",
            agent_name="用户",
            message=f"回答了问题: \"{question[3][:30]}...\"",
            message_type="answer"
        )
        
        # 如果添加了后续问题，记录
        if needs_followup and followup_questions:
            log_agent_activity(
                project_id=project_id,
                phase_id="requirement_analysis",
                agent_name="需求分析器",
                message=f"发现回答中的新模糊点，添加了{len(followup_questions)}个后续问题",
                message_type="followup"
            )
        
        return jsonify({
            "success": True,
            "answer_id": answer_id,
            "question_id": question_id,
            "needs_followup": needs_followup,
            "followup_questions": followup_questions if needs_followup else [],
            "round_completed": total_questions == answered_questions
        })
        
    except Exception as e:
        print(f"提交回答错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/complete/<project_id>', methods=['POST'])
@jwt_required()
def complete_clarification(project_id):
    """
    完成需求澄清过程
    """
    try:
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", 
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        current_time = datetime.now().isoformat()
        
        # 更新所有轮次状态为已完成
        conn.execute(
            """
            UPDATE clarification_rounds 
            SET status = 'completed', updated_at = ? 
            WHERE project_id = ? AND status != 'completed'
            """,
            (current_time, project_id)
        )
        
        # 更新项目的澄清状态
        conn.execute(
            """
            UPDATE projects 
            SET clarification_completed = 1, clarification_completed_at = ? 
            WHERE id = ?
            """,
            (current_time, project_id)
        )
        
        conn.commit()
        
        # 记录活动
        from api.projects import log_agent_activity
        log_agent_activity(
            project_id=project_id,
            phase_id="requirement_analysis",
            agent_name="用户",
            message="完成需求澄清过程，准备进入下一阶段",
            message_type="system"
        )
        
        return jsonify({
            "success": True,
            "project_id": project_id,
            "completed_at": current_time
        })
        
    except Exception as e:
        print(f"完成澄清错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/template', methods=['GET'])
@jwt_required()
def get_clarification_template():
    """
    获取5W2H需求澄清模板
    """
    try:
        # 获取领域信息（如果提供）
        domain = request.args.get('domain', 'general')
        
        analyzer = RequirementAnalyzer5W2H(domain=domain)
        template = analyzer.generate_clarification_template()
        
        return jsonify(template)
        
    except Exception as e:
        print(f"获取模板错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/domains', methods=['GET'])
@jwt_required()
def get_available_domains():
    """
    获取支持的技术领域列表
    """
    try:
        # 创建分析器实例
        analyzer = RequirementAnalyzer5W2H()
        
        # 获取所有支持的领域
        domains = ["general"] + list(analyzer.DOMAIN_AMBIGUOUS_TERMS.keys())
        
        # 构建领域描述
        domain_descriptions = {
            "general": "通用软件开发",
            "web": "Web应用开发",
            "mobile": "移动应用开发",
            "ai": "人工智能应用"
        }
        
        # 格式化结果
        result = [
            {
                "id": domain,
                "name": domain_descriptions.get(domain, domain.capitalize()),
                "description": f"{domain_descriptions.get(domain, domain.capitalize())}领域的需求分析"
            }
            for domain in domains
        ]
        
        return jsonify({
            "domains": result
        })
        
    except Exception as e:
        print(f"获取领域列表错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/knowledge-graph/<project_id>', methods=['GET'])
@jwt_required()
def get_requirement_knowledge_graph(project_id):
    """
    获取项目需求的知识图谱
    """
    try:
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", 
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        # 获取项目需求
        requirement = project[2] or ""
        
        # 检查需求是否为空
        if not requirement.strip():
            return jsonify({"error": "项目需求为空，无法构建知识图谱"}), 400
            
        # 获取项目领域
        domain = project[10] if len(project) > 10 else "general"  # 获取domain字段
        
        # 使用分析器构建知识图谱
        analyzer = RequirementAnalyzer5W2H(
            openai_api_key=current_app.config.get('OPENAI_API_KEY'),
            domain=domain
        )
        
        graph = analyzer.build_requirement_knowledge_graph(requirement)
        
        # 记录智能体活动
        from api.projects import log_agent_activity
        log_agent_activity(
            project_id=project_id,
            phase_id="requirement_analysis",
            agent_name="需求分析器",
            message="生成需求知识图谱",
            message_type="system"
        )
        
        return jsonify({
            "project_id": project_id,
            "graph": graph
        })
        
    except Exception as e:
        print(f"构建知识图谱错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@clarify_bp.route('/answer/<question_id>/semantic-analysis', methods=['POST'])
@jwt_required()
def analyze_answer_semantically(question_id):
    """
    语义分析回答并检测新的模糊点
    """
    try:
        data = request.json
        if not data or 'answer' not in data:
            return jsonify({"error": "缺少回答内容"}), 400
            
        answer = data.get('answer')
        
        conn = current_app.db
        
        # 获取问题信息
        question = conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?",
            (question_id,)
        ).fetchone()
        
        if not question:
            return jsonify({"error": "问题不存在"}), 404
            
        project_id = question[1]  # project_id
        
        # 获取问题文本
        question_text = question[3]  # question
        
        # 获取项目需求和领域
        project = conn.execute(
            "SELECT requirement, domain FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "项目不存在"}), 404
            
        requirement_text = project[0] or ""
        domain = project[1] if len(project) > 1 else "general"
        
        # 使用分析器进行语义分析
        analyzer = RequirementAnalyzer5W2H(
            openai_api_key=current_app.config.get('OPENAI_API_KEY'),
            domain=domain
        )
        
        analysis_result = analyzer.analyze_answer_semantically(
            question_text, 
            answer, 
            requirement_text
        )
        
        return jsonify({
            "question_id": question_id,
            "project_id": project_id,
            "analysis": analysis_result
        })
        
    except Exception as e:
        print(f"语义分析回答错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500 