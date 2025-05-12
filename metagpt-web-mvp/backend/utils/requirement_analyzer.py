import os
import json
import openai
import re
from typing import Dict, List, Any, Tuple, Optional, Union

class RequirementAnalyzer5W2H:
    """基于5W2H框架的需求分析器，支持多维度分析和评分"""
    
    # 5W2H维度定义
    DIMENSIONS = {
        "what": {"name": "What", "description": "系统需要做什么？（核心功能和目标）"},
        "why": {"name": "Why", "description": "为什么需要这个系统？（商业价值和目的）"},
        "who": {"name": "Who", "description": "谁会使用这个系统？（用户角色和相关方）"},
        "when": {"name": "When", "description": "什么场景下使用？（使用场景和触发条件）"},
        "where": {"name": "Where", "description": "在哪些环境下使用？（使用环境和部署要求）"},
        "how": {"name": "How", "description": "如何完成核心流程？（主要操作流程）"},
        "how_much": {"name": "How much", "description": "约束和限制是什么？（性能、成本等约束）"}
    }
    
    # 基础模糊词字典，按维度分类
    AMBIGUOUS_TERMS = {
        "what": ["功能", "特性", "能力", "优化", "改进", "提高", "增强"],
        "why": ["需要", "必须", "应该", "可能"],
        "who": ["用户", "客户", "人们", "他们"],
        "when": ["有时", "经常", "偶尔", "可能", "未来"],
        "where": ["环境", "场景", "地方", "位置"],
        "how": ["友好", "美观", "合理", "适当", "灵活", "高效"],
        "how_much": ["大约", "较多", "较少", "足够", "高性能", "低延迟", "实时"]
    }
    
    # 领域特定模糊词字典 - 按技术领域分类
    DOMAIN_AMBIGUOUS_TERMS = {
        # 通用软件开发模糊词
        "general": {
            "what": ["智能", "动态", "灵活", "可扩展", "模块化", "简洁", "强大", "便捷"],
            "how": ["简单", "直观", "方便", "易用", "优雅", "现代化", "自动化"],
            "how_much": ["快速", "高效", "稳定", "可靠", "安全", "经济", "低成本"]
        },
        # Web应用特定模糊词
        "web": {
            "what": ["响应式", "跨平台", "可访问性", "SEO友好", "沉浸式"],
            "how": ["无缝", "流畅", "交互式", "直观"],
            "how_much": ["轻量级", "高并发", "低延迟"]
        },
        # 移动应用特定模糊词
        "mobile": {
            "what": ["离线功能", "触控友好", "原生体验"],
            "how": ["手势操作", "简洁界面"],
            "how_much": ["省电", "省流量", "小内存占用"]
        },
        # 人工智能特定模糊词
        "ai": {
            "what": ["智能推荐", "认知能力", "学习能力", "预测", "理解"],
            "how": ["训练", "推理", "学习"],
            "how_much": ["准确率高", "召回率高", "低偏差"]
        }
    }
    
    # 增强的领域技术术语词典
    TECH_DOMAIN_TERMS = {
        "web": {
            "frameworks": ["React", "Vue", "Angular", "Next.js", "Svelte", "Express", "Django", "Flask", "Spring Boot", "Laravel"],
            "databases": ["MongoDB", "PostgreSQL", "MySQL", "Redis", "Firestore", "ElasticSearch", "DynamoDB", "SQLite"],
            "cloud": ["AWS", "Azure", "GCP", "Vercel", "Netlify", "Heroku", "Firebase"],
            "concepts": ["响应式", "SEO", "PWA", "微服务", "serverless", "SPA", "SSR", "JAMstack", "GraphQL", "RESTful"]
        },
        "mobile": {
            "frameworks": ["React Native", "Flutter", "Swift UI", "Jetpack Compose", "Xamarin", "Ionic"],
            "platforms": ["iOS", "Android", "跨平台", "iPhone", "iPad", "Samsung", "MIUI"],
            "concepts": ["离线优先", "推送通知", "位置服务", "热更新", "应用内购买", "深度链接", "生物认证"]
        },
        "ai": {
            "techniques": ["机器学习", "深度学习", "NLP", "计算机视觉", "强化学习", "迁移学习", "联邦学习"],
            "frameworks": ["TensorFlow", "PyTorch", "scikit-learn", "Hugging Face", "ONNX", "Keras", "MXNet"],
            "concepts": ["训练", "推理", "微调", "embedding", "向量数据库", "prompt", "token", "transformer", "神经网络"]
        },
        "iot": {
            "platforms": ["Arduino", "Raspberry Pi", "ESP32", "智能家居", "工业物联网", "ESP8266"],
            "protocols": ["MQTT", "Zigbee", "Z-Wave", "BLE", "LoRaWAN", "CoAP", "WiFi", "5G"],
            "concepts": ["边缘计算", "设备互联", "传感器", "远程控制", "低功耗", "实时监控", "数字孪生"]
        },
        "devops": {
            "platforms": ["Docker", "Kubernetes", "Jenkins", "GitLab CI", "GitHub Actions", "Travis CI"],
            "tools": ["Ansible", "Terraform", "Prometheus", "Grafana", "ELK Stack", "Vault"],
            "concepts": ["CI/CD", "基础设施即代码", "监控", "日志聚合", "服务网格", "自动扩缩容"]
        }
    }
    
    # 技术术语一致性检查词典
    TECH_TERMS_CONSISTENCY = {
        # 前端技术栈
        "frontend": [
            ["React", "Vue", "Angular"], # 前端框架选择应一致
            ["JavaScript", "TypeScript"], # 前端语言选择应一致
            ["CSS", "SCSS", "LESS", "Tailwind", "Bootstrap"] # 样式技术选择应一致
        ],
        # 后端技术栈
        "backend": [
            ["Node.js", "Python", "Java", "Go", "C#"], # 后端语言选择应一致
            ["Express", "Django", "Spring Boot", "Flask"], # 后端框架选择应一致
            ["MongoDB", "MySQL", "PostgreSQL", "SQLite", "Oracle"] # 数据库选择应一致
        ],
        # 架构方式
        "architecture": [
            ["微服务", "单体应用", "无服务器"], # 架构风格选择应一致
            ["REST", "GraphQL", "SOAP", "gRPC"] # API风格选择应一致
        ]
    }
    
    def __init__(self, openai_api_key: Optional[str] = None, domain: str = "general"):
        # 优先使用传入的API密钥，其次使用环境变量
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        # 设置领域，默认为通用软件开发
        self.domain = domain
        # 合并基础模糊词和领域特定模糊词
        self._merge_ambiguous_terms()
        
    def _merge_ambiguous_terms(self):
        """合并基础模糊词和领域特定模糊词"""
        self.merged_ambiguous_terms = self.AMBIGUOUS_TERMS.copy()
        
        # 添加通用软件开发模糊词
        general_terms = self.DOMAIN_AMBIGUOUS_TERMS.get("general", {})
        for dimension, terms in general_terms.items():
            if dimension in self.merged_ambiguous_terms:
                self.merged_ambiguous_terms[dimension].extend(terms)
        
        # 添加特定领域模糊词（如果指定）
        if self.domain != "general" and self.domain in self.DOMAIN_AMBIGUOUS_TERMS:
            domain_terms = self.DOMAIN_AMBIGUOUS_TERMS.get(self.domain, {})
            for dimension, terms in domain_terms.items():
                if dimension in self.merged_ambiguous_terms:
                    self.merged_ambiguous_terms[dimension].extend(terms)
                    
        # 去重
        for dimension in self.merged_ambiguous_terms:
            self.merged_ambiguous_terms[dimension] = list(set(self.merged_ambiguous_terms[dimension]))
        
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        """
        分析需求文本，返回多维度评分和澄清问题
        
        返回:
            Dict: 包含以下字段:
                - clarity_score: 总体清晰度评分 (0-100)
                - dimension_scores: 各维度评分
                - ambiguous_points: 模糊点列表
                - questions: 建议澄清问题
                - needs_clarification: 是否需要澄清
                - consistency_issues: 术语一致性问题
        """
        if not requirement_text.strip():
            return self._empty_result()
            
        try:
            if not self.api_key:
                # 如果没有API密钥，使用规则引擎分析
                return self._rule_based_analysis(requirement_text)
                
            # 使用大模型进行5W2H分析
            return self._llm_based_analysis(requirement_text)
        except Exception as e:
            print(f"需求分析错误: {e}")
            # 出错时使用规则分析作为后备
            return self._rule_based_analysis(requirement_text)

    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果模板"""
        dimension_scores = {dim: 0 for dim in self.DIMENSIONS.keys()}
        return {
            "clarity_score": 0,
            "dimension_scores": dimension_scores,
            "ambiguous_points": [],
            "questions": ["请提供项目需求的基本描述。"],
            "needs_clarification": True,
            "consistency_issues": []
        }
            
    def _llm_based_analysis(self, text: str) -> Dict[str, Any]:
        """使用大模型进行5W2H框架的需求分析"""
        client = openai.OpenAI(api_key=self.api_key)
        
        prompt = f"""
        作为需求分析专家，请使用5W2H框架分析以下软件需求的清晰度，识别模糊点并生成澄清问题。
        
        所属技术领域: {self.domain}

        5W2H框架包括：
        1. What：系统需要做什么？（核心功能和目标）
        2. Why：为什么需要这个系统？（商业价值和目的）
        3. Who：谁会使用这个系统？（用户角色和相关方）
        4. When：什么场景下使用？（使用场景和触发条件）
        5. Where：在哪些环境下使用？（使用环境和部署要求）
        6. How：如何完成核心流程？（主要操作流程）
        7. How much：约束和限制是什么？（性能、成本等约束）

        请分析需求文本在每个维度的完整度，识别出模糊点和缺失信息，并生成针对性的澄清问题。
        同时，请检查技术术语的一致性，识别出可能存在矛盾或不一致的地方。

        以JSON格式返回，包含以下字段:
        {{
          "clarity_score": 0-100, // 总体清晰度评分
          "dimension_scores": {{
            "what": 0-100, // 各维度的评分
            "why": 0-100,
            "who": 0-100,
            "when": 0-100,
            "where": 0-100,
            "how": 0-100,
            "how_much": 0-100
          }},
          "ambiguous_points": [
            {{
              "dimension": "what|why|who|when|where|how|how_much", // 所属维度
              "type": "功能模糊|术语歧义|需求缺失|约束不明|场景不全|一致性问题",
              "description": "具体描述模糊点",
              "position": "需求中的相关文本",
              "clarification_question": "针对性的澄清问题",
              "severity": "high|medium|low" // 严重程度
            }}
            // 可以有多个模糊点
          ],
          "questions": [
            "问题1", "问题2"  // 按优先级排序的澄清问题列表
          ],
          "needs_clarification": true或false, // 是否需要进行需求澄清
          "consistency_issues": [
            {{
              "terms": ["Term1", "Term2"], // 存在不一致的术语
              "description": "不一致描述", 
              "clarification_question": "建议的澄清问题"
            }}
          ]
        }}

        需求文本：
        {text}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "你是一个专业的需求分析专家，擅长使用5W2H框架评估软件需求的清晰度并识别需要澄清的地方。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
            
            # 确保重要字段存在
            if "dimension_scores" not in analysis:
                analysis["dimension_scores"] = {dim: 0 for dim in self.DIMENSIONS.keys()}
            
            if "clarity_score" not in analysis:
                # 计算平均分
                scores = list(analysis["dimension_scores"].values())
                analysis["clarity_score"] = sum(scores) / len(scores) if scores else 0
                
            if "needs_clarification" not in analysis:
                analysis["needs_clarification"] = analysis["clarity_score"] < 80
                
            if "questions" not in analysis:
                analysis["questions"] = []
                for point in analysis.get("ambiguous_points", []):
                    if "clarification_question" in point:
                        analysis["questions"].append(point["clarification_question"])
                        
            if "consistency_issues" not in analysis:
                analysis["consistency_issues"] = []
                        
            return analysis
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"解析大模型响应失败: {e}")
            # 出错时使用规则分析作为后备
            return self._rule_based_analysis(text)
            
    def _rule_based_analysis(self, text: str) -> Dict[str, Any]:
        """基于规则的5W2H需求分析"""
        # 计算各维度的模糊词出现次数
        ambiguous_counts = {}
        dimension_terms = {}
        
        for dimension, terms in self.merged_ambiguous_terms.items():
            ambiguous_counts[dimension] = 0
            dimension_terms[dimension] = []
            
            for term in terms:
                if term in text:
                    ambiguous_counts[dimension] += text.count(term)
                    dimension_terms[dimension].append(term)
                    
        # 生成模糊点
        ambiguous_points = []
        for dimension, terms in dimension_terms.items():
            for term in terms:
                # 找出包含模糊词的句子
                sentences = [s.strip() for s in text.split('。') if term in s and s.strip()]
                for sentence in sentences:
                    if not sentence:
                        continue
                    
                    dim_name = self.DIMENSIONS[dimension]["name"]
                    question = f"关于{dim_name}维度：请具体说明'{sentence}'中的'{term}'具体指什么？需要什么具体的标准或要求？"
                    
                    point_type = "功能模糊"
                    severity = "medium"
                    if dimension in ["who", "where"]:
                        point_type = "场景不全"
                    elif dimension in ["how_much"]:
                        point_type = "约束不明"
                        severity = "high"
                    elif dimension in ["why", "when"]:
                        point_type = "需求缺失"
                    
                    ambiguous_points.append({
                        "dimension": dimension,
                        "type": point_type,
                        "description": f"'{term}'是模糊表述，需要具体化",
                        "position": sentence,
                        "clarification_question": question,
                        "severity": severity
                    })
        
        # 检查技术术语一致性
        consistency_issues = self._check_tech_terms_consistency(text)
        
        # 生成各维度的评分（满分100分）
        dimension_scores = {}
        for dimension in self.DIMENSIONS.keys():
            # 基础分80分，每个模糊词降低10分，最低0分
            dimension_count = ambiguous_counts.get(dimension, 0)
            dimension_scores[dimension] = max(0, 80 - dimension_count * 10)
            
            # 检查维度是否完全缺失
            dimension_keywords = self._get_dimension_keywords(dimension)
            has_dimension = any(keyword in text.lower() for keyword in dimension_keywords)
            
            if not has_dimension:
                dimension_scores[dimension] = max(0, dimension_scores[dimension] - 30)
                
                # 添加维度缺失的模糊点
                dim_name = self.DIMENSIONS[dimension]["name"]
                dim_desc = self.DIMENSIONS[dimension]["description"]
                
                ambiguous_points.append({
                    "dimension": dimension,
                    "type": "需求缺失",
                    "description": f"缺少{dim_name}维度的信息",
                    "position": "整个需求文档",
                    "clarification_question": f"请提供关于{dim_desc}",
                    "severity": "high"
                })
        
        # 添加一致性问题到模糊点
        for issue in consistency_issues:
            ambiguous_points.append({
                "dimension": "what",
                "type": "一致性问题",
                "description": issue["description"],
                "position": "技术选择部分",
                "clarification_question": issue["clarification_question"],
                "severity": "high"
            })
        
        # 计算总体清晰度评分（各维度的加权平均值）
        # What和How维度权重更高
        weights = {
            "what": 1.5,
            "how": 1.2,
            "how_much": 1.2,
            "who": 1.0,
            "why": 1.0,
            "when": 0.8,
            "where": 0.8
        }
        
        total_weight = sum(weights.values())
        weighted_sum = sum(dimension_scores[dim] * weights.get(dim, 1.0) for dim in dimension_scores)
        clarity_score = weighted_sum / total_weight
        
        # 生成优先级排序的澄清问题
        questions = []
        
        # 添加高严重性的问题
        high_severity_points = [p for p in ambiguous_points if p.get("severity") == "high"]
        for point in high_severity_points:
            if point["clarification_question"] not in questions:
                questions.append(point["clarification_question"])
        
        # 添加缺失维度的问题
        for dimension, score in dimension_scores.items():
            if score < 40:  # 维度评分低于40分，认为基本缺失
                dim_name = self.DIMENSIONS[dimension]["name"]
                dim_desc = self.DIMENSIONS[dimension]["description"]
                question = f"请补充{dim_name}维度的信息：{dim_desc}"
                if question not in questions:
                    questions.append(question)
        
        # 添加中等严重性的问题
        medium_severity_points = [p for p in ambiguous_points if p.get("severity") == "medium"]
        for point in medium_severity_points:
            if point["clarification_question"] not in questions and len(questions) < 8:
                questions.append(point["clarification_question"])
                
        # 如果问题太多，只保留前10个
        if len(questions) > 10:
            questions = questions[:10]
            
        # 如果没有问题但文本很短，添加一个通用问题
        if not questions and len(text.split()) < 50:
            questions.append("您的需求描述较短，请提供更详细的系统功能、用户场景和约束条件信息。")
            
        return {
            "clarity_score": clarity_score,
            "dimension_scores": dimension_scores,
            "ambiguous_points": ambiguous_points,
            "questions": questions,
            "needs_clarification": clarity_score < 80 or len(questions) > 0,
            "consistency_issues": consistency_issues
        }
    
    def _check_tech_terms_consistency(self, text: str) -> List[Dict[str, Any]]:
        """检查技术术语一致性"""
        issues = []
        text_lower = text.lower()
        
        for category, term_groups in self.TECH_TERMS_CONSISTENCY.items():
            for term_group in term_groups:
                # 检查文本中提到了哪些相关术语
                mentioned_terms = []
                for term in term_group:
                    if term.lower() in text_lower:
                        mentioned_terms.append(term)
                
                # 如果提到了多个术语，可能存在一致性问题
                if len(mentioned_terms) > 1:
                    issue = {
                        "terms": mentioned_terms,
                        "description": f"同时提到了多个{category}技术: {', '.join(mentioned_terms)}，可能存在技术选择不一致",
                        "clarification_question": f"请明确说明项目将使用哪一种{category}技术: {' 还是 '.join(mentioned_terms)}？"
                    }
                    issues.append(issue)
        
        return issues
    
    def _get_dimension_keywords(self, dimension: str) -> List[str]:
        """获取维度相关的关键词"""
        keywords = {
            "what": ["功能", "特性", "做什么", "实现", "目标", "要求"],
            "why": ["原因", "目的", "为什么", "价值", "意义", "解决", "问题"],
            "who": ["用户", "角色", "人员", "谁", "使用者", "客户", "管理员"],
            "when": ["时间", "场景", "情况", "条件", "触发", "何时", "频率"],
            "where": ["位置", "环境", "平台", "设备", "地点", "哪里", "部署"],
            "how": ["方式", "流程", "步骤", "如何", "操作", "交互", "实现"],
            "how_much": ["性能", "成本", "约束", "限制", "要求", "指标", "多少"]
        }
        return keywords.get(dimension, [])
    
    def generate_structured_questions(self, analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """生成按5W2H框架结构化的问题"""
        structured_questions = {
            "round1": [],  # 第一轮：核心功能与目标确认（What、Why、Who）
            "round2": [],  # 第二轮：边界条件与约束确认（When、Where、How、How much）
            "round3": []   # 第三轮：特定模糊点跟进
        }
        
        # 从分析结果中提取问题
        all_questions = analysis.get("questions", [])
        ambiguous_points = analysis.get("ambiguous_points", [])
        dimension_scores = analysis.get("dimension_scores", {})
        consistency_issues = analysis.get("consistency_issues", [])
        
        # 将问题按维度分类
        dimension_questions = {dim: [] for dim in self.DIMENSIONS.keys()}
        
        # 先处理分析器直接给出的问题
        for question in all_questions:
            # 尝试根据问题内容判断维度
            assigned = False
            for dim, info in self.DIMENSIONS.items():
                if info["name"] in question or info["description"] in question:
                    dimension_questions[dim].append(question)
                    assigned = True
                    break
            
            # 如果无法判断维度，放入第三轮
            if not assigned:
                structured_questions["round3"].append(question)
        
        # 再处理模糊点中的问题
        for point in ambiguous_points:
            dim = point.get("dimension")
            question = point.get("clarification_question")
            severity = point.get("severity", "medium")
            
            if dim and question and question not in dimension_questions.get(dim, []):
                # 高严重性的问题放在对应轮次的前面
                if severity == "high":
                    dimension_questions[dim].insert(0, question)
                else:
                    dimension_questions[dim].append(question)
        
        # 处理一致性问题
        for issue in consistency_issues:
            question = issue.get("clarification_question")
            if question and question not in structured_questions["round1"]:
                structured_questions["round1"].append(question)
        
        # 分配到不同轮次
        # 第一轮：What, Why, Who（核心功能与目标）
        for dim in ["what", "why", "who"]:
            # 如果维度评分低，优先添加该维度的问题
            if dimension_scores.get(dim, 0) < 60:
                structured_questions["round1"].extend(dimension_questions.get(dim, []))
            else:
                # 评分较高时，只添加最重要的问题
                important_questions = dimension_questions.get(dim, [])[:1]
                structured_questions["round1"].extend(important_questions)
        
        # 第二轮：When, Where, How, How_much（边界条件与约束）
        for dim in ["when", "where", "how", "how_much"]:
            if dimension_scores.get(dim, 0) < 60:
                structured_questions["round2"].extend(dimension_questions.get(dim, []))
            else:
                important_questions = dimension_questions.get(dim, [])[:1]
                structured_questions["round2"].extend(important_questions)
        
        # 确保每轮至少有一个问题
        if not structured_questions["round1"]:
            structured_questions["round1"].append("请描述系统的核心功能和目标用户。")
            
        if not structured_questions["round2"]:
            structured_questions["round2"].append("请描述系统的使用场景和主要约束条件。")
            
        # 限制问题数量，避免过多问题
        structured_questions["round1"] = structured_questions["round1"][:5]
        structured_questions["round2"] = structured_questions["round2"][:5]
        structured_questions["round3"] = structured_questions["round3"][:3]
        
        return structured_questions
        
    def generate_clarification_template(self) -> Dict[str, Any]:
        """生成需求澄清模板"""
        template = {
            "dimensions": {
                dim: {
                    "name": info["name"],
                    "description": info["description"],
                    "questions": self._get_template_questions(dim)
                } for dim, info in self.DIMENSIONS.items()
            },
            "rounds": [
                {
                    "id": "round1",
                    "name": "核心功能与目标确认",
                    "description": "确认系统的核心功能、商业价值和主要用户",
                    "dimensions": ["what", "why", "who"]
                },
                {
                    "id": "round2",
                    "name": "边界条件与约束确认",
                    "description": "确认系统的使用场景、环境、操作流程和限制条件",
                    "dimensions": ["when", "where", "how", "how_much"]
                },
                {
                    "id": "round3",
                    "name": "特定模糊点跟进",
                    "description": "针对性解决剩余关键问题",
                    "dimensions": []
                }
            ]
        }
        return template
        
    def _get_template_questions(self, dimension: str) -> List[str]:
        """获取维度的模板问题"""
        templates = {
            "what": [
                "系统需要实现哪些核心功能？",
                "系统的主要目标是什么？",
                "系统需要解决什么问题？",
                "系统的核心特性有哪些？"
            ],
            "why": [
                "为什么需要开发这个系统？",
                "这个系统的商业价值是什么？",
                "目前存在什么问题需要这个系统来解决？"
            ],
            "who": [
                "系统的主要用户是谁？",
                "系统涉及哪些角色？他们各自的职责是什么？",
                "系统的最终客户是谁？",
                "是否有不同类型的用户需要不同的功能？"
            ],
            "when": [
                "系统在什么场景或条件下使用？",
                "系统需要什么时候可用？有时间限制吗？",
                "系统使用的频率是怎样的？",
                "是否有特定的触发条件？"
            ],
            "where": [
                "系统将在什么环境中部署和运行？",
                "系统需要支持哪些平台或设备？",
                "系统的使用位置有特殊要求吗？",
                "系统需要考虑地理位置因素吗？"
            ],
            "how": [
                "用户将如何与系统交互？",
                "系统的主要操作流程是什么？",
                "系统如何实现核心功能？",
                "系统的交互设计有特殊要求吗？"
            ],
            "how_much": [
                "系统有哪些性能要求和限制？",
                "系统的成本预算是多少？",
                "系统需要支持多少用户同时使用？",
                "系统的响应时间要求是什么？",
                "系统的可靠性和可用性要求是什么？"
            ]
        }
        return templates.get(dimension, [])
    
    def analyze_answer_semantically(self, question, answer, requirement_context):
        """基于语义理解分析回答中的新模糊点"""
        # 使用大模型分析回答内容的完整性
        prompt = f"""
        你是需求分析专家，请分析以下问题和回答的质量，找出回答中可能引入的新模糊点。
        
        需求背景：
        {requirement_context}
        
        问题：{question}
        回答：{answer}
        
        请分析：
        1. 回答的完整性 (0-100)
        2. 回答中引入的新概念是否清晰
        3. 回答是否与已有需求一致
        4. 回答是否引入了新的模糊表述
        
        以JSON格式返回，包含以下字段:
        {{
          "answer_quality": 0-100,
          "new_ambiguous_points": [
            {{
              "text": "模糊表述文本",
              "reason": "分析为什么这是模糊的",
              "type": "术语模糊|量化不明|功能界限不清|技术冲突",
              "clarification_question": "建议的后续澄清问题",
              "severity": "high|medium|low"
            }}
          ],
          "needs_followup": true或false,
          "suggested_followup_questions": [
            "优先级最高的澄清问题1",
            "优先级第二的澄清问题2"
          ]
        }}
        """
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": "你是需求分析专家，擅长识别回答中的隐含模糊点。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except Exception as e:
            print(f"语义分析回答错误: {e}")
            # 降级为规则分析
            return self._rule_based_answer_analysis(question, answer)

    def _rule_based_answer_analysis(self, question, answer):
        """基于规则分析回答质量（作为语义分析的备选）"""
        # 实现基于规则的后备方案
        # 改进：不再简单检测模糊词，而是检测句式结构和修饰词
        
        # 开放性陈述识别
        open_patterns = [
            r"视情况而定",
            r"后续(再|可以).*决定",
            r"(可能|也许|大概).*考虑",
            r"基本上.*实现"
        ]
        
        # 不确定量化表述识别
        quantifier_patterns = [
            r"(很多|一些|少量|大量|足够).*",
            r"(高效|快速|实时|低延迟)(的|地)",
            r"(合理|适当)(的|地)"
        ]
        
        # 未定义术语识别
        ambiguous_points = []
        
        # 检查开放性陈述
        for pattern in open_patterns:
            matches = re.finditer(pattern, answer)
            for match in matches:
                ambiguous_points.append({
                    "text": match.group(0),
                    "reason": "回答包含不确定性表述",
                    "type": "功能界限不清",
                    "clarification_question": f"请明确说明'{match.group(0)}'的具体标准或条件",
                    "severity": "medium"
                })
        
        # 检查不确定量化
        for pattern in quantifier_patterns:
            matches = re.finditer(pattern, answer)
            for match in matches:
                ambiguous_points.append({
                    "text": match.group(0),
                    "reason": "回答包含模糊量化词",
                    "type": "量化不明",
                    "clarification_question": f"请定义'{match.group(0)}'的具体数值或范围",
                    "severity": "high"
                })
        
        # 结果封装
        needs_followup = len(ambiguous_points) > 0
        suggested_questions = [p["clarification_question"] for p in ambiguous_points[:2]]
        
        return {
            "answer_quality": 70 if needs_followup else 90,
            "new_ambiguous_points": ambiguous_points,
            "needs_followup": needs_followup,
            "suggested_followup_questions": suggested_questions
        }
        
    def semantic_ambiguity_detection(self, text, domain="general"):
        """使用语义理解增强的模糊点检测"""
        prompt = f"""
        你是需求分析专家，请识别以下{domain}领域需求文本中的模糊点，考虑上下文和语义。
        
        需求文本:
        {text}
        
        请考虑：
        1. 术语不明确：使用了未定义或多义的技术术语
        2. 量化不充分：使用模糊量词但未给出具体值或范围
        3. 功能边界不清：功能范围或条件描述不完整
        4. 技术冲突：提及互相冲突或不兼容的技术选择
        5. 依赖不明确：依赖关系或前提条件不清晰
        
        分析时要考虑句子上下文，而不是简单查找关键词。
        
        以JSON格式返回，包含以下字段:
        {{
          "ambiguous_points": [
            {{
              "text": "具体的模糊文本",
              "context": "包含模糊文本的完整句子",
              "dimension": "what|why|who|when|where|how|how_much",
              "type": "术语模糊|量化不明|功能界限不清|技术冲突|依赖不明确",
              "reason": "详细解释为什么这是模糊的",
              "clarification_question": "建议的澄清问题",
              "severity": "high|medium|low"
            }}
          ]
        }}
        """
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": f"你是专注于{domain}领域的需求分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("ambiguous_points", [])
        except Exception as e:
            print(f"语义模糊点检测错误: {e}")
            # 降级为基于规则的检测
            return self._rule_based_ambiguity_detection(text, domain)
            
    def contextual_term_analysis(self, text, domain="general"):
        """上下文相关的术语分析，检测特定领域术语的使用是否一致"""
        # 获取特定领域的术语
        domain_terms = self.TECH_DOMAIN_TERMS.get(domain, {})
        
        if not domain_terms:
            return []
        
        # 合并所有术语列表
        all_terms = []
        for category, terms in domain_terms.items():
            all_terms.extend(terms)
        
        # 使用正则表达式分割段落和句子
        sentences = re.split(r'[。.!?！？]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 分析每个句子中的术语使用
        term_occurrences = {}
        for sentence in sentences:
            for term in all_terms:
                if term.lower() in sentence.lower():
                    if term not in term_occurrences:
                        term_occurrences[term] = []
                    term_occurrences[term].append(sentence)
        
        # 查找术语使用的一致性问题
        consistency_issues = []
        
        # 检查同一类别中是否提到多个术语（潜在冲突）
        for category, terms in domain_terms.items():
            mentioned_terms = [term for term in terms if term in term_occurrences]
            if len(mentioned_terms) > 1:
                # 可能的技术选择冲突
                consistency_issues.append({
                    "category": category,
                    "terms": mentioned_terms,
                    "sentences": [s for term in mentioned_terms for s in term_occurrences[term]],
                    "issue_type": "技术选择冲突",
                    "clarification_question": f"请明确项目是使用{', '.join(mentioned_terms[:-1])}还是{mentioned_terms[-1]}？"
                })
        
        return consistency_issues
    
    def build_requirement_knowledge_graph(self, text):
        """构建需求知识图谱"""
        prompt = f"""
        你是需求分析专家，请从以下需求文本中提取关键实体和关系，构建知识图谱。
        
        需求文本:
        {text}
        
        请提取：
        1. 核心实体：用户角色、系统组件、功能模块、技术选择等
        2. 实体间关系：如"使用"、"包含"、"依赖"、"访问"等
        
        以JSON格式返回，包含以下字段:
        {{
          "nodes": [
            {{
              "id": "唯一标识符",
              "label": "实体名称",
              "type": "用户|组件|功能|技术|约束|环境",
              "description": "实体描述",
              "dimension": "what|why|who|when|where|how|how_much" 
            }}
          ],
          "edges": [
            {{
              "source": "源节点id",
              "target": "目标节点id",
              "label": "关系类型",
              "description": "关系描述"
            }}
          ]
        }}
        """
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": "你是需求分析专家，擅长提取需求中的实体和关系。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            knowledge_graph = json.loads(response.choices[0].message.content)
            return knowledge_graph
        except Exception as e:
            print(f"构建知识图谱错误: {e}")
            return {"nodes": [], "edges": []} 