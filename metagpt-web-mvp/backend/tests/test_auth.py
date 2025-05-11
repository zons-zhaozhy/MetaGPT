import unittest
import json
import os
import sys
from unittest.mock import patch

# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

class AuthAPITest(unittest.TestCase):
    """身份验证API测试类"""
    
    def setUp(self):
        """测试前准备"""
        app.config['TESTING'] = True
        app.config['JWT_SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()
    
    def test_login(self):
        """测试登录API"""
        with patch('api.auth.authenticate_user') as mock_auth:
            # 模拟认证成功
            mock_auth.return_value = True
            
            response = self.client.post(
                '/api/auth/login',
                json={"username": "test_user", "password": "test_password"}
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn("access_token", data)
            self.assertIn("token_type", data)
            
            # 模拟认证失败
            mock_auth.return_value = False
            
            response = self.client.post(
                '/api/auth/login',
                json={"username": "invalid_user", "password": "invalid_password"}
            )
            
            self.assertEqual(response.status_code, 401)
    
    def test_login_missing_fields(self):
        """测试登录缺少字段"""
        response = self.client.post(
            '/api/auth/login',
            json={"username": "test_user"}  # 缺少password字段
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_register(self):
        """测试注册API"""
        with patch('api.auth.register_user') as mock_register:
            # 模拟注册成功
            mock_register.return_value = "user_id_123"
            
            response = self.client.post(
                '/api/auth/register',
                json={
                    "username": "new_user",
                    "password": "new_password",
                    "email": "user@example.com"
                }
            )
            
            self.assertEqual(response.status_code, 201)
            data = json.loads(response.data)
            self.assertIn("id", data)
            self.assertEqual(data.get("username"), "new_user")
            
            # 模拟用户名已存在
            mock_register.return_value = None
            
            response = self.client.post(
                '/api/auth/register',
                json={
                    "username": "existing_user",
                    "password": "new_password",
                    "email": "user@example.com"
                }
            )
            
            self.assertEqual(response.status_code, 409)
    
    def test_protected_route(self):
        """测试受保护的路由需要JWT认证"""
        # 访问需要认证的路由，应该返回401
        response = self.client.get('/api/projects')
        self.assertEqual(response.status_code, 401)
        
        # 使用无效的令牌
        response = self.client.get(
            '/api/projects',
            headers={"Authorization": "Bearer invalid_token"}
        )
        self.assertEqual(response.status_code, 422)
        
        # 注意：测试有效令牌的情况在项目API测试中已包含

if __name__ == '__main__':
    unittest.main() 