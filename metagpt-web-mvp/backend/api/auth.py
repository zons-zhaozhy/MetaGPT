from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import os
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 简单的用户存储，仅用于MVP演示
# 在实际产品中应使用数据库存储和密码哈希
USERS = {
    'admin': {
        'password': os.environ.get('ADMIN_PASSWORD', 'admin123'),
        'name': 'Administrator'
    }
}

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录API"""
    data = request.json
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
    
    username = data['username']
    password = data['password']
    
    if username not in USERS or USERS[username]['password'] != password:
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # 创建JWT令牌
    expires = datetime.timedelta(days=1)
    access_token = create_access_token(
        identity=username,
        additional_claims={'name': USERS[username]['name']},
        expires_delta=expires
    )
    
    return jsonify({
        'token': access_token,
        'user': {
            'username': username,
            'name': USERS[username]['name']
        }
    })

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_user():
    """获取当前用户信息"""
    current_user = get_jwt_identity()
    
    if current_user not in USERS:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'username': current_user,
        'name': USERS[current_user]['name']
    }) 