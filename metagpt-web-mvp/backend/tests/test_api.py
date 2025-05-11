import unittest
import json
import os
import sys
import uuid
from unittest.mock import patch

# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

class MetaGPTWebAPITest(unittest.TestCase):
    """MetaGPT Web API 测试类"""
    
    def setUp(self):
        """测试前准备"""
        app.config['TESTING'] = True
        app.config['DATA_DIR'] = os.path.join(os.path.dirname(__file__), "test_data")
        os.makedirs(app.config['DATA_DIR'], exist_ok=True)
        
        self.client = app.test_client()
        
        # 测试用JWT token
        self.test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X3VzZXIifQ.lEHjTGBc4-OM3ITWkBPOOCQ2d2zn97tDaVVa9CwwVVk"
        
        # 创建测试项目
        response = self.client.post(
            '/api/projects',
            headers={"Authorization": f"Bearer {self.test_token}"},
            json={
                "name": "测试项目",
                "requirement": "创建一个简单的TODO应用"
            }
        )
        result = json.loads(response.data)
        self.test_project_id = result.get("id")
    
    def tearDown(self):
        """测试后清理"""
        # 清理测试数据目录
        import shutil
        if os.path.exists(app.config['DATA_DIR']):
            shutil.rmtree(app.config['DATA_DIR'])
    
    # 项目API测试
    def test_list_projects(self):
        """测试获取项目列表"""
        response = self.client.get(
            '/api/projects',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
    
    def test_get_project(self):
        """测试获取项目详情"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("name"), "测试项目")
    
    def test_get_project_status(self):
        """测试获取项目状态"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/status',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("status", data)
        self.assertIn("activeStep", data)
    
    # 阶段管理API测试
    def test_get_project_phases(self):
        """测试获取项目阶段"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/phases',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("phases", data)
    
    @patch('threading.Thread')
    def test_execute_project_phase(self, mock_thread):
        """测试执行项目阶段"""
        # 模拟线程启动
        mock_thread.return_value.start.return_value = None
        
        response = self.client.post(
            f'/api/projects/{self.test_project_id}/execute/requirement_analysis',
            headers={"Authorization": f"Bearer {self.test_token}"},
            json={"action": "execute"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("action"), "execute")
        self.assertEqual(data.get("status"), "started")
    
    # 需求澄清API测试
    def test_generate_clarification_questions(self):
        """测试生成澄清问题"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/clarify',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("questions", data)
        self.assertGreater(len(data.get("questions", [])), 0)
    
    def test_submit_clarification_answers(self):
        """测试提交澄清问题答案"""
        # 先获取问题列表
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/clarify',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        questions = json.loads(response.data).get("questions", [])
        
        if questions:
            question_id = questions[0].get("id")
            
            # 提交答案
            response = self.client.post(
                f'/api/projects/{self.test_project_id}/clarify/answer',
                headers={"Authorization": f"Bearer {self.test_token}"},
                json={
                    "question_id": question_id,
                    "answer": "测试回答"
                }
            )
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data.get("success"))
    
    def test_get_clarification_questions(self):
        """测试获取澄清问题列表"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/clarify/questions',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("questions", data)
    
    # 代理日志API测试
    def test_get_agent_logs(self):
        """测试获取代理日志"""
        response = self.client.get(
            f'/api/projects/{self.test_project_id}/logs',
            headers={"Authorization": f"Bearer {self.test_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("logs", data)

if __name__ == '__main__':
    unittest.main() 