from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required
import os
import time
import uuid
import threading
import subprocess
from datetime import datetime
import shutil
import json
import sqlite3
from flask_socketio import emit

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')

# 辅助函数：扫描目录
def scan_directory(directory):
    """扫描目录，返回文件路径和修改时间的字典"""
    result = {}
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            mod_time = os.path.getmtime(file_path)
            result[file_path] = mod_time
    return result

# 辅助函数：解析MetaGPT日志获取状态信息
def parse_and_update_status(log_line, project_id):
    """解析MetaGPT日志行并更新项目状态"""
    # 日志示例分析（根据MetaGPT实际日志格式调整）
    active_step = None
    status = None
    
    # 需求分析阶段
    if "开始需求分析" in log_line or "Requirements Analysis" in log_line:
        active_step = 1
        status = "需求分析中"
    # 架构设计阶段
    elif "开始架构设计" in log_line or "System Design" in log_line:
        active_step = 2
        status = "架构设计中"
    # 编码实现阶段
    elif "开始编码实现" in log_line or "Implementation" in log_line:
        active_step = 3
        status = "编码实现中"
    # 测试验证阶段
    elif "开始测试验证" in log_line or "Testing" in log_line:
        active_step = 4
        status = "测试验证中"
    # 完成
    elif "任务完成" in log_line or "Task Completed" in log_line:
        active_step = 5
        status = "已完成"
    # 失败
    elif "任务失败" in log_line or "Task Failed" in log_line:
        status = "失败"
    
    # 更新数据库中的项目状态
    if active_step is not None or status is not None:
        update_fields = []
        params = []
        
        if active_step is not None:
            update_fields.append("active_step = ?")
            params.append(active_step)
        
        if status is not None:
            update_fields.append("status = ?")
            params.append(status)
        
        if update_fields:
            query = f"UPDATE projects SET {', '.join(update_fields)} WHERE id = ?"
            params.append(project_id)
            
            try:
                with current_app.app_context():
                    conn = current_app.db
                    conn.execute(query, params)
                    conn.commit()
            except Exception as e:
                print(f"Error updating project status: {e}")

# 辅助函数：更新项目文件状态
def update_project_status(project_id, file_path):
    """根据新生成的文件更新项目状态"""
    try:
        filename = os.path.basename(file_path)
        # 简单的文件类型推断
        file_type = "unknown"
        if filename.endswith((".py", ".js", ".html", ".css", ".java", ".cpp", ".ts")):
            file_type = "code"
        elif filename.endswith((".md", ".txt", ".pdf", ".docx")):
            file_type = "document"
        elif filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            file_type = "image"
        
        # 检查文件是否已存在于数据库中
        file_id = str(uuid.uuid4())
        conn = current_app.db
        existing = conn.execute(
            "SELECT id FROM project_files WHERE project_id = ? AND file_path = ?",
            (project_id, file_path)
        ).fetchone()
        
        if existing:
            return
        
        # 添加到数据库
        created_at = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO project_files (id, project_id, filename, file_path, file_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, project_id, filename, file_path, file_type, created_at)
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating project file status: {e}")

# 辅助函数：监控MetaGPT输出
def monitor_output(process, project_id, output_dir, app):
    """监控MetaGPT进程输出和输出目录变化"""
    files_status = {}
    
    try:
        while process.poll() is None:
            # 检查新文件
            current_files = scan_directory(output_dir)
            for file_path, mod_time in current_files.items():
                if file_path not in files_status or mod_time > files_status[file_path]:
                    files_status[file_path] = mod_time
                    # 使用传入的app对象创建上下文
                    with app.app_context():
                        update_project_status(project_id, file_path)
            
            # 获取并解析日志
            stdout_line = process.stdout.readline()
            if stdout_line:
                with app.app_context():
                    parse_and_update_status(stdout_line, project_id)
            
            time.sleep(2)
        
        # 进程结束后，检查退出状态
        exit_code = process.returncode
        
        with app.app_context():
            conn = app.db
            if exit_code != 0:
                # 处理失败的情况
                conn.execute(
                    "UPDATE projects SET status = ? WHERE id = ?",
                    ("失败", project_id)
                )
            else:
                # 处理成功完成的情况
                conn.execute(
                    "UPDATE projects SET status = ?, active_step = ? WHERE id = ?",
                    ("已完成", 5, project_id)
                )
            conn.commit()
                
    except Exception as e:
        print(f"Error in monitoring process: {e}")
        # 更新项目状态为失败
        try:
            with app.app_context():
                conn = app.db
                conn.execute(
                    "UPDATE projects SET status = ? WHERE id = ?",
                    ("失败", project_id)
                )
                conn.commit()
        except Exception as inner_e:
            print(f"Failed to update project status after error: {inner_e}")

def run_metagpt_api(project_id, requirement, output_dir, app):
    """运行MetaGPT API并处理结果"""
    try:
        # 创建新的数据库连接，而不是使用主线程的连接
        db_path = os.path.join(app.config["DATA_DIR"], "metagpt_web.db")
        conn = None
        
        try:
            # 记录开始处理的日志
            log_message = f"开始MetaGPT处理流程，需求：{requirement[:50]}..."
            log_agent_activity(project_id, "requirement_analysis", "SystemAgent", log_message, "system", db_path)
            
            # 发送WebSocket通知
            if hasattr(app, 'socketio'):
                app.socketio.emit('agent_log', {
                    'project_id': project_id,
                    'phase_id': 'requirement_analysis',
                    'agent_name': 'SystemAgent',
                    'message': log_message,
                    'message_type': 'system',
                    'timestamp': datetime.now().isoformat()
                }, room=project_id)
            
            # 更新项目状态为"需求分析中"
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE projects SET status = ?, active_step = ? WHERE id = ?",
                ("需求分析中", 1, project_id)
            )
            conn.commit()
            
            # 阶段进度通知
            progress_steps = [
                {"step": "需求分析", "message": "正在分析需求并生成用户故事..."},
                {"step": "架构设计", "message": "正在设计系统架构和组件..."},
                {"step": "任务拆分", "message": "正在拆分开发任务..."},
                {"step": "编码实现", "message": "正在生成代码实现..."},
                {"step": "测试验证", "message": "正在生成测试用例..."}
            ]
            
            # 导入MetaGPT软件公司模块
            from metagpt.software_company import generate_repo
            
            # 在后台线程中定期发送进度更新
            stop_progress_thread = threading.Event()
            
            def send_progress_updates():
                step_index = 0
                while not stop_progress_thread.is_set() and step_index < len(progress_steps):
                    step = progress_steps[step_index]
                    
                    # 记录进度日志
                    log_agent_activity(
                        project_id, 
                        f"phase_{step_index+1}", 
                        "MetaGPTAgent", 
                        step["message"], 
                        "log", 
                        db_path
                    )
                    
                    # 发送WebSocket通知
                    if hasattr(app, 'socketio'):
                        app.socketio.emit('agent_log', {
                            'project_id': project_id,
                            'phase_id': f"phase_{step_index+1}",
                            'agent_name': "MetaGPTAgent",
                            'message': step["message"],
                            'message_type': 'log',
                            'timestamp': datetime.now().isoformat()
                        }, room=project_id)
                    
                    # 更新数据库状态
                    try:
                        progress_conn = sqlite3.connect(db_path)
                        progress_conn.execute(
                            "UPDATE projects SET status = ? WHERE id = ?",
                            (step["step"], project_id)
                        )
                        progress_conn.commit()
                        progress_conn.close()
                    except Exception as e:
                        print(f"Error updating progress: {e}")
                    
                    step_index += 1
                    time.sleep(30)  # 每30秒更新一次进度
            
            # 启动进度更新线程
            progress_thread = threading.Thread(target=send_progress_updates)
            progress_thread.daemon = True
            progress_thread.start()
            
            try:
                # 执行MetaGPT生成
                generate_repo(
                    idea=requirement,
                    investment=3.0,
                    project_path=output_dir,
                    implement=True
                )
            finally:
                # 停止进度更新线程
                stop_progress_thread.set()
                if progress_thread.is_alive():
                    progress_thread.join(timeout=2)
            
            # 记录完成日志
            log_agent_activity(
                project_id, 
                "completion", 
                "SystemAgent", 
                "MetaGPT处理完成，正在整理生成文件...", 
                "system", 
                db_path
            )
            
            # 发送WebSocket通知
            if hasattr(app, 'socketio'):
                app.socketio.emit('agent_log', {
                    'project_id': project_id,
                    'phase_id': 'completion',
                    'agent_name': 'SystemAgent',
                    'message': "MetaGPT处理完成，正在整理生成文件...",
                    'message_type': 'system',
                    'timestamp': datetime.now().isoformat()
                }, room=project_id)
            
            # 扫描生成的文件并更新项目状态
            files_status = scan_directory(output_dir)
            
            # 更新文件记录
            file_count = 0
            for file_path, _ in files_status.items():
                filename = os.path.basename(file_path)
                # 简单的文件类型推断
                file_type = "unknown"
                if filename.endswith((".py", ".js", ".html", ".css", ".java", ".cpp", ".ts")):
                    file_type = "code"
                elif filename.endswith((".md", ".txt", ".pdf", ".docx")):
                    file_type = "document"
                elif filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                    file_type = "image"
                
                # 检查文件是否已存在于数据库中
                file_id = str(uuid.uuid4())
                existing = conn.execute(
                    "SELECT id FROM project_files WHERE project_id = ? AND file_path = ?",
                    (project_id, file_path)
                ).fetchone()
                
                if not existing:
                    # 添加到数据库
                    created_at = datetime.now().isoformat()
                    conn.execute(
                        "INSERT INTO project_files (id, project_id, filename, file_path, file_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (file_id, project_id, filename, file_path, file_type, created_at)
                    )
                    file_count += 1
                    
                    # 每10个文件发送一次进度通知
                    if file_count % 10 == 0:
                        # 发送WebSocket通知
                        if hasattr(app, 'socketio'):
                            app.socketio.emit('agent_log', {
                                'project_id': project_id,
                                'phase_id': 'file_processing',
                                'agent_name': 'SystemAgent',
                                'message': f"已处理 {file_count} 个文件...",
                                'message_type': 'log',
                                'timestamp': datetime.now().isoformat()
                            }, room=project_id)
            
            # 更新项目状态为完成
            conn.execute(
                "UPDATE projects SET status = ?, active_step = ? WHERE id = ?",
                ("已完成", 5, project_id)
            )
            conn.commit()
            
            # 发送完成通知
            log_agent_activity(
                project_id, 
                "completion", 
                "SystemAgent", 
                f"项目生成完成！共生成 {file_count} 个文件。", 
                "system", 
                db_path
            )
            
            # 发送WebSocket通知
            if hasattr(app, 'socketio'):
                app.socketio.emit('agent_log', {
                    'project_id': project_id,
                    'phase_id': 'completion',
                    'agent_name': 'SystemAgent',
                    'message': f"项目生成完成！共生成 {file_count} 个文件。",
                    'message_type': 'system',
                    'timestamp': datetime.now().isoformat()
                }, room=project_id)
                
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in running MetaGPT API: {e}")
        print(f"详细错误: {error_details}")
        
        # 记录错误日志
        log_agent_activity(
            project_id, 
            "error", 
            "SystemAgent", 
            f"MetaGPT处理出错: {str(e)}", 
            "error", 
            db_path
        )
        
        # 发送WebSocket错误通知
        if hasattr(app, 'socketio'):
            app.socketio.emit('agent_log', {
                'project_id': project_id,
                'phase_id': 'error',
                'agent_name': 'SystemAgent',
                'message': f"MetaGPT处理出错: {str(e)}",
                'message_type': 'error',
                'timestamp': datetime.now().isoformat()
            }, room=project_id)
        
        # 更新项目状态为失败
        try:
            # 重新连接数据库
            db_path = os.path.join(app.config["DATA_DIR"], "metagpt_web.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                ("失败", project_id)
            )
            conn.commit()
            conn.close()
        except Exception as inner_e:
            print(f"Failed to update project status after error: {inner_e}")

# 修改execute_metagpt_task函数，实时推送状态更新
def execute_metagpt_task(project_id, requirement, output_dir):
    """执行MetaGPT任务并监控输出"""
    try:
        # 保存当前应用上下文，这是关键修复
        app = current_app._get_current_object()
        
        # 发送状态通知
        if hasattr(app, 'socketio'):
            app.socketio.emit('agent_log', {
                'project_id': project_id,
                'phase_id': 'system',
                'agent_name': 'SystemAgent',
                'message': f"开始处理需求: {requirement[:50]}...",
                'message_type': 'system',
                'timestamp': datetime.now().isoformat()
            }, room=project_id)
        
        # 更新项目状态
        app.db.execute(
            "UPDATE projects SET status = ? WHERE id = ?",
            ("需求分析中", project_id)
        )
        app.db.commit()
        
        # 记录日志
        log_agent_activity(
            project_id,
            'requirement_analysis',
            'SystemAgent',
            f"开始处理MetaGPT任务，需求: {requirement[:100]}...",
            'system',
            None
        )
        
        # 启动线程执行MetaGPT API调用
        monitoring_thread = threading.Thread(
            target=run_metagpt_api,
            args=(project_id, requirement, output_dir, app),
            daemon=True
        )
        monitoring_thread.start()
        
        print(f"启动MetaGPT任务，需求: {requirement}, 输出目录: {output_dir}")
        return True
    except Exception as e:
        print(f"Error executing MetaGPT task: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        
        # 更新项目状态为失败
        try:
            with current_app.app_context():
                conn = current_app.db
                conn.execute(
                    "UPDATE projects SET status = ? WHERE id = ?",
                    ("失败", project_id)
                )
                conn.commit()
                
                # 记录错误日志
                log_agent_activity(
                    project_id,
                    'system',
                    'SystemAgent',
                    f"任务执行失败: {str(e)}",
                    'error',
                    None
                )
                
                # 发送错误通知
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('agent_log', {
                        'project_id': project_id,
                        'phase_id': 'system',
                        'agent_name': 'SystemAgent',
                        'message': f"任务执行失败: {str(e)}",
                        'message_type': 'error',
                        'timestamp': datetime.now().isoformat()
                    }, room=project_id)
        except Exception as inner_e:
            print(f"更新失败状态时出错: {inner_e}")
            
        return False

# API路由
@projects_bp.route('', methods=['GET'])
@jwt_required()
def list_projects():
    """获取项目列表"""
    try:
        projects = current_app.db.execute(
            'SELECT id, name, created_at, status, active_step FROM projects ORDER BY created_at DESC'
        ).fetchall()
        
        return jsonify([
            {
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'status': row[3],
                'active_step': row[4]
            } for row in projects
        ])
    except Exception as e:
        print(f"Error listing projects: {e}")
        return jsonify({'error': 'Failed to fetch projects'}), 500

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """创建新项目"""
    try:
        data = request.json
        
        if not data or 'name' not in data or 'requirement' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        project_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # 创建项目目录
        output_dir = os.path.join(current_app.config['DATA_DIR'], project_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存项目信息到数据库
        current_app.db.execute(
            'INSERT INTO projects (id, name, requirement, created_at, status, active_step) VALUES (?, ?, ?, ?, ?, ?)',
            (project_id, data['name'], data['requirement'], created_at, 'pending', 0)
        )
        current_app.db.commit()
        
        # 异步执行MetaGPT任务
        success = execute_metagpt_task(project_id, data['requirement'], output_dir)
        
        if not success:
            return jsonify({'error': 'Failed to start MetaGPT task'}), 500
        
        return jsonify({
            'id': project_id,
            'name': data['name'],
            'created_at': created_at,
            'status': 'pending',
            'active_step': 0
        }), 201
    except Exception as e:
        print(f"Error creating project: {e}")
        return jsonify({'error': 'Failed to create project'}), 500

@projects_bp.route('/<project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """获取项目详情"""
    try:
        # 确保数据库连接可用
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            'SELECT id, name, requirement, created_at, status, active_step FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found', 'project_id': project_id}), 404
        
        # 确保项目目录存在
        output_dir = os.path.join(current_app.config['DATA_DIR'], project_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # 检查是否已有相关阶段记录
        phases_count = conn.execute(
            "SELECT COUNT(*) FROM project_phases WHERE project_id = ?",
            (project_id,)
        ).fetchone()[0]
        
        # 如果没有阶段记录，创建默认阶段
        if phases_count == 0:
            # 定义默认阶段
            default_phases = [
                {"phase_id": "requirement_analysis", "name": "需求分析"},
                {"phase_id": "architecture_design", "name": "架构设计"},
                {"phase_id": "implementation", "name": "编码实现"},
                {"phase_id": "testing", "name": "测试验证"},
                {"phase_id": "deployment", "name": "部署交付"}
            ]
            
            # 检查表结构是否包含metadata列
            has_metadata = False
            try:
                conn.execute("SELECT metadata FROM project_phases LIMIT 1")
                has_metadata = True
            except sqlite3.OperationalError:
                has_metadata = False
            
            # 创建阶段记录
            for phase in default_phases:
                phase_id = str(uuid.uuid4())
                if has_metadata:
                    conn.execute(
                        """
                        INSERT INTO project_phases 
                        (id, project_id, phase_id, status, metadata) 
                        VALUES (?, ?, ?, 'pending', ?)
                        """,
                        (
                            phase_id, 
                            project_id, 
                            phase["phase_id"],
                            json.dumps({"name": phase["name"]})
                        )
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO project_phases 
                        (id, project_id, phase_id, status) 
                        VALUES (?, ?, ?, 'pending')
                        """,
                        (
                            phase_id, 
                            project_id, 
                            phase["phase_id"]
                        )
                    )
            conn.commit()
        
        # 返回项目信息
        return jsonify({
            'id': project[0],
            'name': project[1],
            'requirement': project[2],
            'created_at': project[3],
            'status': project[4],
            'active_step': project[5]
        })
    except Exception as e:
        print(f"Error getting project: {e}")
        # 返回更详细的错误信息
        import traceback
        error_details = traceback.format_exc()
        print(f"Detailed error: {error_details}")
        return jsonify({'error': f'Failed to fetch project: {str(e)}'}), 500

@projects_bp.route('/<project_id>/status', methods=['GET'])
@jwt_required()
def get_project_status(project_id):
    """获取项目状态"""
    try:
        project = current_app.db.execute(
            'SELECT status, active_step FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        # 获取已生成的文件
        files = current_app.db.execute(
            'SELECT id, filename, file_type, created_at FROM project_files WHERE project_id = ? ORDER BY created_at',
            (project_id,)
        ).fetchall()
        # 读取阶段状态文件
        output_dir = os.path.join(current_app.config['DATA_DIR'], project_id)
        state_file = os.path.join(output_dir, "metagpt_state.json")
        phase_info = {}
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                phase_info = {
                    "current_phase": state.get("current_phase", "pending"),
                    "phases_completed": state.get("phases_completed", []),
                    "artifacts": state.get("artifacts", {}),
                    "timestamps": state.get("timestamps", {})
                }
        return jsonify({
            'status': project[0],
            'activeStep': project[1],
            'files': [
                {
                    'id': row[0],
                    'filename': row[1],
                    'type': row[2],
                    'time': row[3]
                } for row in files
            ],
            **phase_info
        })
    except Exception as e:
        print(f"Error getting project status: {e}")
        return jsonify({'error': 'Failed to fetch project status'}), 500

@projects_bp.route('/<project_id>/files', methods=['GET'])
@jwt_required()
def list_project_files(project_id):
    """获取项目文件列表"""
    try:
        files = current_app.db.execute(
            'SELECT id, filename, file_path, file_type, created_at FROM project_files WHERE project_id = ? ORDER BY created_at',
            (project_id,)
        ).fetchall()
        
        return jsonify([
            {
                'id': row[0],
                'filename': row[1],
                'path': row[2],
                'type': row[3],
                'created_at': row[4]
            } for row in files
        ])
    except Exception as e:
        print(f"Error listing project files: {e}")
        return jsonify({'error': 'Failed to fetch project files'}), 500

@projects_bp.route('/<project_id>/files/<file_id>/view', methods=['GET'])
@jwt_required()
def view_file(project_id, file_id):
    """查看文件内容"""
    try:
        file_info = current_app.db.execute(
            'SELECT file_path FROM project_files WHERE id = ? AND project_id = ?',
            (file_id, project_id)
        ).fetchone()
        
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        file_path = file_info[0]
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': 'File does not exist'}), 404
        
        # 对于图片等二进制文件，直接发送文件
        if file_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf')):
            return send_file(file_path)
        
        # 对于文本文件，读取内容并返回
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'content': content
        })
    except Exception as e:
        print(f"Error viewing file: {e}")
        return jsonify({'error': 'Failed to view file'}), 500

@projects_bp.route('/<project_id>/files/<file_id>/download', methods=['GET'])
@jwt_required()
def download_file(project_id, file_id):
    """下载文件"""
    try:
        file_info = current_app.db.execute(
            'SELECT file_path, filename FROM project_files WHERE id = ? AND project_id = ?',
            (file_id, project_id)
        ).fetchone()
        
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        file_path = file_info[0]
        filename = file_info[1]
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': 'File does not exist'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"Error downloading file: {e}")
        return jsonify({'error': 'Failed to download file'}), 500

@projects_bp.route('/<project_id>/download', methods=['GET'])
@jwt_required()
def download_project(project_id):
    """下载整个项目"""
    try:
        project = current_app.db.execute(
            'SELECT name FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        project_name = project[0]
        output_dir = os.path.join(current_app.config['DATA_DIR'], project_id)
        
        # 检查项目目录是否存在
        if not os.path.exists(output_dir):
            return jsonify({'error': 'Project directory does not exist'}), 404
        
        # 创建临时目录用于打包
        temp_dir = os.path.join(current_app.config['DATA_DIR'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建一个zip文件
        zip_path = os.path.join(temp_dir, f"{project_name}.zip")
        
        # 打包项目目录
        shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', output_dir)
        
        return send_file(zip_path, as_attachment=True, download_name=f"{project_name}.zip")
    except Exception as e:
        print(f"Error downloading project: {e}")
        return jsonify({'error': 'Failed to download project'}), 500

# 新增：获取项目阶段信息API
@projects_bp.route('/<project_id>/phases', methods=['GET'])
@jwt_required()
def get_project_phases(project_id):
    """获取项目各阶段状态"""
    try:
        # 使用应用的数据库锁来保证线程安全
        with current_app.db_lock:
            conn = current_app.db
            
            # 检查表结构是否包含metadata列
            has_metadata = False
            try:
                conn.execute("SELECT metadata FROM project_phases LIMIT 1")
                has_metadata = True
            except sqlite3.OperationalError:
                has_metadata = False
                
            # 检查项目是否存在
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ?", 
                (project_id,)
            ).fetchone()
            
            if not project:
                # 如果UUID格式有效，创建一个临时项目
                try:
                    uuid_obj = uuid.UUID(project_id)
                    # 创建临时项目
                    current_time = datetime.now().isoformat()
                    conn.execute(
                        """
                        INSERT INTO projects
                        (id, name, requirement, created_at, status, active_step)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            f"临时项目 {project_id[:8]}",
                            "后续补充需求",
                            current_time,
                            "pending",
                            0
                        )
                    )
                    conn.commit()
                    
                    # 创建项目目录
                    output_dir = os.path.join(current_app.config['DATA_DIR'], project_id)
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 重新获取项目
                    project = conn.execute(
                        "SELECT * FROM projects WHERE id = ?", 
                        (project_id,)
                    ).fetchone()
                except ValueError:
                    # 无效的UUID
                    return jsonify({"error": "Invalid project ID format"}), 400
            
            # 获取所有项目阶段
            phases = conn.execute(
                "SELECT * FROM project_phases WHERE project_id = ? ORDER BY phase_id",
                (project_id,)
            ).fetchall()
            
            # 如果没有阶段记录，创建默认阶段
            if not phases:
                # 定义默认阶段
                default_phases = [
                    {"phase_id": "requirement_analysis", "name": "需求分析"},
                    {"phase_id": "architecture_design", "name": "架构设计"},
                    {"phase_id": "implementation", "name": "编码实现"},
                    {"phase_id": "testing", "name": "测试验证"},
                    {"phase_id": "deployment", "name": "部署交付"}
                ]
                
                # 创建阶段记录
                for phase in default_phases:
                    phase_id = str(uuid.uuid4())
                    if has_metadata:
                        conn.execute(
                            """
                            INSERT INTO project_phases 
                            (id, project_id, phase_id, status, metadata) 
                            VALUES (?, ?, ?, 'pending', ?)
                            """,
                            (
                                phase_id, 
                                project_id, 
                                phase["phase_id"],
                                json.dumps({"name": phase["name"]})
                            )
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO project_phases 
                            (id, project_id, phase_id, status) 
                            VALUES (?, ?, ?, 'pending')
                            """,
                            (
                                phase_id, 
                                project_id, 
                                phase["phase_id"]
                            )
                        )
                
                conn.commit()
                
                # 重新获取阶段
                phases = conn.execute(
                    "SELECT * FROM project_phases WHERE project_id = ? ORDER BY phase_id",
                    (project_id,)
                ).fetchall()
            
            # 将结果转换为字典列表
            result = []
            for phase in phases:
                # 检查metadata字段是否存在，适应旧数据
                phase_data = {
                    "id": phase[0],
                    "project_id": phase[1],
                    "phase_id": phase[2],
                    "status": phase[3],
                    "started_at": phase[4],
                    "completed_at": phase[5],
                    "artifacts": json.loads(phase[6] if phase[6] else '{}'),
                    "feedback": json.loads(phase[7] if phase[7] else '{}'),
                    "can_retry": bool(phase[8]) if len(phase) > 8 else True,
                    "retry_count": phase[9] if len(phase) > 9 else 0,
                    "metadata": {"name": get_phase_name(phase[2])}  # 默认使用阶段ID的名称
                }
                
                # 如果存在metadata列，尝试使用它
                if has_metadata and len(phase) > 10 and phase[10]:
                    try:
                        phase_data["metadata"] = json.loads(phase[10])
                    except (json.JSONDecodeError, TypeError):
                        # 解析失败时使用默认值
                        pass
                
                result.append(phase_data)
            
            return jsonify({
                "project_id": project_id,
                "phases": result
            })
    except Exception as e:
        print(f"Error in get_project_phases: {e}")
        return jsonify({"error": str(e)}), 500

# 修改：分阶段执行API，修复应用上下文问题和状态不一致问题
@projects_bp.route('/<project_id>/execute/<phase>', methods=['POST'])
@jwt_required()
def execute_project_phase(project_id, phase):
    """执行或控制项目特定阶段"""
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
        requirement = project[2]
        
        # 检查阶段是否存在
        phase_row = conn.execute(
            "SELECT * FROM project_phases WHERE project_id = ? AND phase_id = ?",
            (project_id, phase)
        ).fetchone()
        
        if not phase_row:
            return jsonify({"error": "Phase not found"}), 404
        
        # 获取请求参数
        data = request.json or {}
        action = data.get('action', 'execute')  # 默认为执行
        
        # 根据不同动作执行不同操作
        if action == 'execute':
            # 如果阶段已经在运行，返回错误
            if phase_row[3] == 'running':
                return jsonify({"error": "Phase is already running"}), 400
            
            # 更新阶段状态为运行中
            current_time = datetime.now().isoformat()
            conn.execute(
                """
                UPDATE project_phases 
                SET status = 'running', started_at = ?, retry_count = retry_count + 1
                WHERE id = ?
                """,
                (current_time, phase_row[0])
            )
            
            # 更新项目状态
            step = get_phase_step(phase)
            conn.execute(
                "UPDATE projects SET active_step = ?, current_phase = ?, status = '执行中' WHERE id = ?",
                (step, phase, project_id)
            )
            
            conn.commit()
            
            # 创建项目输出目录
            output_dir = os.path.join(current_app.config["DATA_DIR"], project_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存阶段状态文件路径
            state_file = os.path.join(output_dir, f"{phase}_state.json")
            
            # 启动异步任务执行阶段
            from flask import current_app as app
            threading.Thread(
                target=run_phase_with_app_context,
                args=(app._get_current_object(), os.path.join(app.config["DATA_DIR"], "metagpt_web.db"), project_id, phase, state_file, requirement)
            ).start()
            
            return jsonify({
                "project_id": project_id,
                "phase": phase,
                "action": action,
                "status": "started"
            })
        
        elif action == 'pause':
            # 暂停阶段执行
            if phase_row[3] != 'running':
                return jsonify({"error": "Phase is not running"}), 400
            
            # 更新阶段状态
            conn.execute(
                "UPDATE project_phases SET status = 'paused' WHERE id = ?",
                (phase_row[0],)
            )
            conn.commit()
            
            # TODO: 实际暂停执行的逻辑
            
            return jsonify({
                "project_id": project_id,
                "phase": phase,
                "action": action,
                "status": "paused"
            })
        
        elif action == 'resume':
            # 恢复阶段执行
            if phase_row[3] != 'paused':
                return jsonify({"error": "Phase is not paused"}), 400
            
            # 更新阶段状态
            conn.execute(
                "UPDATE project_phases SET status = 'running' WHERE id = ?",
                (phase_row[0],)
            )
            conn.commit()
            
            # TODO: 实际恢复执行的逻辑
            
            return jsonify({
                "project_id": project_id,
                "phase": phase,
                "action": action,
                "status": "resumed"
            })
        
        elif action == 'skip':
            # 跳过阶段
            conn.execute(
                "UPDATE project_phases SET status = 'skipped', completed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), phase_row[0])
            )
            
            # 更新项目状态到下一阶段
            next_phase = get_next_phase(phase)
            if next_phase:
                step = get_phase_step(next_phase)
                conn.execute(
                    "UPDATE projects SET active_step = ?, current_phase = ? WHERE id = ?",
                    (step, next_phase, project_id)
                )
            
            conn.commit()
            
            return jsonify({
                "project_id": project_id,
                "phase": phase,
                "action": action,
                "status": "skipped",
                "next_phase": next_phase
            })
        
        elif action == 'abort':
            # 终止阶段
            conn.execute(
                "UPDATE project_phases SET status = 'aborted', completed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), phase_row[0])
            )
            
            # 更新项目状态
            conn.execute(
                "UPDATE projects SET status = '已中断' WHERE id = ?",
                (project_id,)
            )
            
            conn.commit()
            
            # TODO: 实际终止执行的逻辑
            
            return jsonify({
                "project_id": project_id,
                "phase": phase,
                "action": action,
                "status": "aborted"
            })
        
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 新增：获取下一个阶段ID
def get_next_phase(phase):
    """获取下一个阶段ID"""
    phases = [
        "requirement_analysis",
        "architecture_design",
        "implementation",
        "testing",
        "deployment"
    ]
    
    try:
        idx = phases.index(phase)
        if idx < len(phases) - 1:
            return phases[idx + 1]
    except ValueError:
        pass
    
    return None

# 需求澄清相关API
@projects_bp.route('/<project_id>/clarify', methods=['GET'])
@jwt_required()
def generate_clarification_questions(project_id):
    """生成澄清问题"""
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
        requirement = project[2]
        
        # 检查是否已经有问题，避免重复生成
        existing_questions = conn.execute(
            "SELECT COUNT(*) FROM clarification_questions WHERE project_id = ?",
            (project_id,)
        ).fetchone()[0]
        
        # 如果已经有问题，直接返回它们
        if existing_questions > 0:
            questions = conn.execute(
                "SELECT id, question, priority, status, created_at FROM clarification_questions WHERE project_id = ? ORDER BY priority",
                (project_id,)
            ).fetchall()
            
            result = [
                {
                    "id": q[0],
                    "question": q[1],
                    "priority": q[2],
                    "status": q[3],
                    "created_at": q[4]
                } for q in questions
            ]
            
            return jsonify({
                "project_id": project_id,
                "questions": result,
                "from_cache": True
            })
        
        # 生成新问题
        # TODO: 使用LLM生成澄清问题
        # 这里简单模拟几个问题
        questions = [
            "您能具体描述一下项目的目标用户群体吗？",
            "系统需要支持哪些主要功能？",
            "您对系统的性能有什么特殊要求？",
            "是否需要考虑特定的安全性需求？"
        ]
        
        # 保存问题到数据库
        result = []
        current_time = datetime.now().isoformat()
        
        for i, question in enumerate(questions):
            question_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO clarification_questions 
                (id, project_id, question, created_at, status, priority) 
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (question_id, project_id, question, current_time, i)
            )
            
            result.append({
                "id": question_id,
                "question": question,
                "priority": i,
                "status": "pending",
                "created_at": current_time
            })
        
        conn.commit()
        
        return jsonify({
            "project_id": project_id,
            "questions": result,
            "from_cache": False
        })
        
    except Exception as e:
        print(f"Error generating clarification questions: {e}")
        # 更详细的错误记录
        import traceback
        error_details = traceback.format_exc()
        print(f"Detailed error: {error_details}")
        return jsonify({"error": str(e)}), 500

@projects_bp.route('/<project_id>/clarify/answer', methods=['POST'])
@jwt_required()
def submit_clarification_answers(project_id):
    """提交澄清问题的回答"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Missing request body"}), 400
        
        question_id = data.get('question_id')
        answer = data.get('answer')
        
        if not question_id or not answer:
            return jsonify({"error": "Missing required fields"}), 400
        
        conn = current_app.db
        
        # 检查问题是否存在
        question = conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ? AND project_id = ?",
            (question_id, project_id)
        ).fetchone()
        
        if not question:
            return jsonify({"error": "Question not found"}), 404
        
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
        
        # 更新项目需求
        # 获取现有需求
        project = conn.execute(
            "SELECT requirement FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()
        
        existing_requirement = project[0] if project else ""
        
        # 拼接问题和回答到需求中
        updated_requirement = f"{existing_requirement}\n\n问题：{question[2]}\n回答：{answer}"
        
        conn.execute(
            "UPDATE projects SET requirement = ? WHERE id = ?",
            (updated_requirement, project_id)
        )
        
        conn.commit()
        
        # 判断是否需要生成后续问题（模拟）
        needs_followup = False
        if "更多" in answer or "详细" in answer or len(answer) > 100:
            needs_followup = True
            
            # 更新问题需要后续跟进
            conn.execute(
                "UPDATE clarification_questions SET needs_followup = 1 WHERE id = ?",
                (question_id,)
            )
            conn.commit()
        
        return jsonify({
            "success": True,
            "answer_id": answer_id,
            "needs_followup": needs_followup
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 获取项目澄清问题列表
@projects_bp.route('/<project_id>/clarify/questions', methods=['GET'])
@jwt_required()
def get_clarification_questions(project_id):
    """获取项目的澄清问题列表"""
    try:
        # 使用应用的数据库连接而不是创建新连接
        conn = current_app.db
        
        # 检查项目是否存在
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", 
            (project_id,)
        ).fetchone()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        # 获取所有问题
        questions = conn.execute(
            "SELECT * FROM clarification_questions WHERE project_id = ? ORDER BY priority",
            (project_id,)
        ).fetchall()
        
        # 获取所有回答
        answers = conn.execute(
            "SELECT * FROM clarification_answers WHERE project_id = ?",
            (project_id,)
        ).fetchall()
        
        # 构建问题-回答映射
        answers_map = {}
        for answer in answers:
            q_id = answer[1]  # question_id
            if q_id not in answers_map:
                answers_map[q_id] = []
            
            answers_map[q_id].append({
                "id": answer[0],
                "answer": answer[3],
                "created_at": answer[4]
            })
        
        # 构建结果
        result = []
        for q in questions:
            result.append({
                "id": q[0],
                "question": q[2],
                "created_at": q[3],
                "status": q[4],
                "priority": q[5],
                "needs_followup": bool(q[6]) if len(q) > 6 else False,
                "answers": answers_map.get(q[0], [])
            })
        
        # 如果没有问题，返回空列表
        if not questions:
            return jsonify({
                "project_id": project_id,
                "questions": []
            })
        
        return jsonify({
            "project_id": project_id,
            "questions": result
        })
            
    except Exception as e:
        print(f"Error getting clarification questions: {e}")
        return jsonify({"error": f"Failed to fetch clarification questions: {str(e)}"}), 500

# 新增函数：带有应用上下文的阶段执行
def run_phase_with_app_context(app, db_path, project_id, phase, state_file, requirement):
    """在应用上下文中执行阶段任务"""
    try:
        # 记录日志
        log_agent_activity(
            project_id, 
            phase, 
            "SystemAgent", 
            f"开始执行{get_phase_name(phase)}阶段", 
            "system", 
            db_path
        )
        
        # 创建输出目录
        output_dir = os.path.join(app.config["DATA_DIR"], project_id, phase)
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存阶段状态
        save_phase_state(state_file, {
            "status": "running",
            "phase": phase,
            "started_at": datetime.now().isoformat()
        })
        
        # 根据不同阶段执行不同操作
        if phase == "requirement_analysis":
            # 记录智能体活动
            log_agent_activity(
                project_id, 
                phase, 
                "ProductManager", 
                "开始分析需求", 
                "log", 
                db_path
            )
            
            # 模拟工作过程
            time.sleep(3)
            
            # 生成需求文档
            requirement_doc = f"""# 需求分析文档

## 项目概述
{requirement}

## 功能需求
1. 功能点1
2. 功能点2
3. 功能点3

## 非功能需求
- 性能要求
- 安全要求
- 兼容性要求
"""
            
            # 保存需求文档
            requirement_doc_path = os.path.join(output_dir, "需求分析.md")
            with open(requirement_doc_path, "w") as f:
                f.write(requirement_doc)
                
            # 记录生成物
            log_agent_activity(
                project_id, 
                phase, 
                "ProductManager", 
                f"生成需求文档: {requirement_doc_path}", 
                "artifact", 
                db_path
            )
            
            # 更新阶段状态
            artifacts = [
                {
                    "name": "需求分析.md",
                    "path": requirement_doc_path,
                    "type": "document"
                }
            ]
            
        elif phase == "architecture_design":
            # 记录智能体活动
            log_agent_activity(
                project_id, 
                phase, 
                "Architect", 
                "开始设计系统架构", 
                "log", 
                db_path
            )
            
            # 模拟工作过程
            time.sleep(4)
            
            # 生成架构文档
            architecture_doc = f"""# 系统架构设计

## 架构概述
基于需求分析，设计三层架构系统。

## 组件设计
- 前端UI组件
- 业务逻辑组件
- 数据访问组件

## 技术选型
- 前端: React + Ant Design
- 后端: Flask + SQLite
- 部署: Docker容器
"""
            
            # 保存架构文档
            architecture_doc_path = os.path.join(output_dir, "架构设计.md")
            with open(architecture_doc_path, "w") as f:
                f.write(architecture_doc)
                
            # 记录生成物
            log_agent_activity(
                project_id, 
                phase, 
                "Architect", 
                f"生成架构文档: {architecture_doc_path}", 
                "artifact", 
                db_path
            )
            
            # 更新阶段状态
            artifacts = [
                {
                    "name": "架构设计.md",
                    "path": architecture_doc_path,
                    "type": "document"
                }
            ]
            
        elif phase == "implementation":
            # 记录多个代理活动
            log_agent_activity(
                project_id, 
                phase, 
                "ProjectManager", 
                "安排编码任务", 
                "log", 
                db_path
            )
            
            log_agent_activity(
                project_id, 
                phase, 
                "Engineer", 
                "开始编写代码", 
                "log", 
                db_path
            )
            
            # 模拟工作过程
            time.sleep(5)
            
            # 生成示例代码
            sample_code = """
def main():
    print("Hello, MetaGPT!")
    
    # 初始化应用
    app = initialize_app()
    
    # 启动服务
    app.run()
    
if __name__ == "__main__":
    main()
"""
            
            # 保存示例代码
            code_path = os.path.join(output_dir, "main.py")
            with open(code_path, "w") as f:
                f.write(sample_code)
                
            # 记录生成物
            log_agent_activity(
                project_id, 
                phase, 
                "Engineer", 
                f"生成代码文件: {code_path}", 
                "artifact", 
                db_path
            )
            
            # 更新阶段状态
            artifacts = [
                {
                    "name": "main.py",
                    "path": code_path,
                    "type": "code"
                }
            ]
            
        elif phase == "testing":
            # 记录智能体活动
            log_agent_activity(
                project_id, 
                phase, 
                "QAEngineer", 
                "开始测试验证", 
                "log", 
                db_path
            )
            
            # 模拟工作过程
            time.sleep(3)
            
            # 生成测试报告
            test_report = f"""# 测试报告

## 测试概述
对系统进行了单元测试和集成测试。

## 测试结果
- 单元测试: 通过
- 集成测试: 通过
- 性能测试: 良好

## 发现问题
无严重问题，有2个小bug已修复。
"""
            
            # 保存测试报告
            test_report_path = os.path.join(output_dir, "测试报告.md")
            with open(test_report_path, "w") as f:
                f.write(test_report)
                
            # 记录生成物
            log_agent_activity(
                project_id, 
                phase, 
                "QAEngineer", 
                f"生成测试报告: {test_report_path}", 
                "artifact", 
                db_path
            )
            
            # 更新阶段状态
            artifacts = [
                {
                    "name": "测试报告.md",
                    "path": test_report_path,
                    "type": "document"
                }
            ]
            
        else:  # deployment
            # 记录智能体活动
            log_agent_activity(
                project_id, 
                phase, 
                "DevOpsEngineer", 
                "准备部署环境", 
                "log", 
                db_path
            )
            
            # 模拟工作过程
            time.sleep(2)
            
            # 生成部署文档
            deployment_doc = f"""# 部署文档

## 部署环境
- Docker容器化部署
- Nginx作为反向代理

## 部署步骤
1. 构建Docker镜像
2. 配置Nginx
3. 启动容器

## 监控方案
使用Prometheus + Grafana进行系统监控。
"""
            
            # 保存部署文档
            deployment_doc_path = os.path.join(output_dir, "部署文档.md")
            with open(deployment_doc_path, "w") as f:
                f.write(deployment_doc)
                
            # 记录生成物
            log_agent_activity(
                project_id, 
                phase, 
                "DevOpsEngineer", 
                f"生成部署文档: {deployment_doc_path}", 
                "artifact", 
                db_path
            )
            
            # 更新阶段状态
            artifacts = [
                {
                    "name": "部署文档.md",
                    "path": deployment_doc_path,
                    "type": "document"
                }
            ]
        
        # 更新数据库
        conn = sqlite3.connect(db_path)
        
        # 更新阶段状态
        phase_id = conn.execute(
            "SELECT id FROM project_phases WHERE project_id = ? AND phase_id = ?",
            (project_id, phase)
        ).fetchone()[0]
        
        conn.execute(
            """
            UPDATE project_phases 
            SET status = 'completed', completed_at = ?, artifacts = ? 
            WHERE id = ?
            """,
            (datetime.now().isoformat(), json.dumps(artifacts), phase_id)
        )
        
        # 更新项目状态
        next_phase = get_next_phase(phase)
        if next_phase:
            # 还有下一阶段
            next_step = get_phase_step(next_phase)
            conn.execute(
                "UPDATE projects SET active_step = ?, current_phase = ? WHERE id = ?",
                (next_step, next_phase, project_id)
            )
        else:
            # 已完成所有阶段
            conn.execute(
                "UPDATE projects SET status = '已完成', active_step = 5 WHERE id = ?",
                (project_id,)
            )
        
        conn.commit()
        conn.close()
        
        # 保存阶段状态
        save_phase_state(state_file, {
            "status": "completed",
            "phase": phase,
            "completed_at": datetime.now().isoformat(),
            "artifacts": artifacts
        })
        
        # 记录完成日志
        log_agent_activity(
            project_id, 
            phase, 
            "SystemAgent", 
            f"{get_phase_name(phase)}阶段已完成", 
            "system", 
            db_path
        )
        
    except Exception as e:
        # 记录错误
        error_message = str(e)
        print(f"Error in phase execution: {error_message}")
        
        try:
            # 更新数据库状态为失败
            conn = sqlite3.connect(db_path)
            
            conn.execute(
                "UPDATE project_phases SET status = 'failed' WHERE project_id = ? AND phase_id = ?",
                (project_id, phase)
            )
            
            conn.execute(
                "UPDATE projects SET status = '执行出错' WHERE id = ?",
                (project_id,)
            )
            
            conn.commit()
            conn.close()
            
            # 保存阶段状态
            save_phase_state(state_file, {
                "status": "failed",
                "phase": phase,
                "error": error_message
            })
            
            # 记录错误日志
            log_agent_activity(
                project_id, 
                phase, 
                "SystemAgent", 
                f"执行出错: {error_message}", 
                "error", 
                db_path
            )
            
        except Exception as inner_e:
            print(f"Error updating failure status: {inner_e}")

# 保存阶段状态文件
def save_phase_state(state_file, state):
    """保存阶段状态到文件"""
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving phase state: {e}")

# 获取阶段名称
def get_phase_name(phase_id):
    """获取阶段名称"""
    phase_names = {
        "requirement_analysis": "需求分析",
        "architecture_design": "架构设计",
        "implementation": "编码实现",
        "testing": "测试验证",
        "deployment": "部署交付"
    }
    return phase_names.get(phase_id, phase_id)

# 添加智能体活动日志记录函数
def log_agent_activity(project_id, phase_id, agent_name, message, message_type="log", db_path=None):
    """记录智能体活动日志，支持在异步线程中调用"""
    try:
        # 创建新的数据库连接
        if db_path:
            conn = sqlite3.connect(db_path)
        else:
            from flask import current_app
            conn = current_app.db
        
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # 插入日志记录
        conn.execute(
            """
            INSERT INTO agent_logs 
            (id, project_id, phase_id, agent_name, message, message_type, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, project_id, phase_id, agent_name, message, message_type, timestamp)
        )
        conn.commit()
        
        # 如果是外部创建的连接，关闭连接
        if db_path:
            conn.close()
        
        # 发送WebSocket事件
        from flask import current_app
        if hasattr(current_app, 'socketio'):
            current_app.socketio.emit('agent_log', {
                'project_id': project_id,
                'phase_id': phase_id,
                'agent_name': agent_name,
                'message': message,
                'message_type': message_type,
                'timestamp': timestamp
            }, room=project_id)
            
    except Exception as e:
        print(f"Error logging agent activity: {e}")

# 添加获取智能体日志API
@projects_bp.route('/<project_id>/logs', methods=['GET'])
@jwt_required()
def get_agent_logs(project_id):
    """获取项目智能体活动日志"""
    try:
        # 获取过滤参数
        phase_id = request.args.get('phase_id')
        agent_name = request.args.get('agent_name')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        conn = current_app.db
        
        # 构建查询条件
        query = "SELECT * FROM agent_logs WHERE project_id = ?"
        params = [project_id]
        
        if phase_id:
            query += " AND phase_id = ?"
            params.append(phase_id)
            
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
            
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # 执行查询
        logs = conn.execute(query, params).fetchall()
        
        # 转换结果
        result = []
        for log in logs:
            result.append({
                "id": log[0],
                "project_id": log[1],
                "phase_id": log[2],
                "agent_name": log[3],
                "message": log[4],
                "message_type": log[5],
                "timestamp": log[6]
            })
        
        return jsonify({
            "project_id": project_id,
            "logs": result,
            "count": len(result)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 添加WebSocket处理函数
def register_socketio_handlers(socketio):
    """注册WebSocket事件处理函数"""
    
    @socketio.on('connect')
    def handle_connect():
        print("Socket.IO: Client connected")
        # 返回连接成功消息，帮助客户端确认连接状态
        from flask_socketio import emit
        emit('connect_response', {'status': 'connected', 'message': 'WebSocket connection established'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print("Socket.IO: Client disconnected")
    
    @socketio.on('join')
    def handle_join(data):
        """加入项目房间，接收特定项目的实时更新"""
        from flask_socketio import join_room, emit
        
        try:
            project_id = data.get('project_id')
            if not project_id:
                print("Socket.IO: Missing project_id in join request")
                emit('error', {'message': 'Missing project_id'})
                return
                
            # 记录详细日志
            print(f"Socket.IO: Client attempting to join room: {project_id}")
            
            # 加入房间
            join_room(project_id)
            print(f"Socket.IO: Client successfully joined room: {project_id}")
            
            # 发送加入成功确认
            emit('joined', {
                'project_id': project_id,
                'status': 'joined',
                'message': f'Successfully joined project room: {project_id}'
            })
            
            # 发送一条测试消息到项目房间
            socketio.emit('agent_log', {
                'project_id': project_id,
                'phase_id': 'system',
                'agent_name': 'SystemAgent',
                'message': 'WebSocket连接已建立，实时更新已激活',
                'message_type': 'system',
                'timestamp': datetime.now().isoformat()
            }, room=project_id)
            
        except Exception as e:
            import traceback
            print(f"Socket.IO error in handle_join: {e}")
            print(traceback.format_exc())
            emit('error', {'message': f'Error joining room: {str(e)}'})
    
    @socketio.on('leave')
    def handle_leave(data):
        """离开项目房间"""
        from flask_socketio import leave_room, emit
        
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('error', {'message': 'Missing project_id'})
                return
                
            print(f"Socket.IO: Client leaving room: {project_id}")
            leave_room(project_id)
            
            # 发送离开确认
            emit('left', {
                'project_id': project_id,
                'status': 'left',
                'message': f'Successfully left project room: {project_id}'
            })
            
        except Exception as e:
            print(f"Socket.IO error in handle_leave: {e}")
            emit('error', {'message': f'Error leaving room: {str(e)}'})

# 辅助函数：获取阶段对应的步骤号
def get_phase_step(phase):
    """将阶段ID转换为步骤号"""
    phase_steps = {
        "requirement_analysis": 1,
        "architecture_design": 2,
        "task_assignment": 3,
        "coding": 4,
        "testing": 5
    }
    return phase_steps.get(phase, 0) 