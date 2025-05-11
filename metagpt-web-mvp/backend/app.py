import os
import sqlite3
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from dotenv import load_dotenv
import threading

from api.auth import auth_bp
from api.projects import projects_bp

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder="../frontend/dist", static_url_path="/")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-secret-key")
app.config["DATA_DIR"] = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))

# 确保数据目录存在
os.makedirs(app.config["DATA_DIR"], exist_ok=True)

# 添加数据库锁，确保线程安全
app.db_lock = threading.RLock()

# 初始化扩展
jwt = JWTManager(app)
CORS(app)
# 修复WebSocket连接问题，明确指定传输方式和路径
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', 
                   logger=True, engineio_logger=True,
                   path='/socket.io/')

# 注册WebSocket处理函数
from api.projects import register_socketio_handlers
register_socketio_handlers(socketio)

# 初始化数据库
def init_db():
    db_path = os.path.join(app.config["DATA_DIR"], "metagpt_web.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    # 创建项目表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        requirement TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        active_step INTEGER DEFAULT 0,
        current_phase TEXT DEFAULT 'pending',
        phases_completed TEXT DEFAULT '[]'
    )
    ''')
    
    # 创建项目文件表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS project_files (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建项目阶段表 - 增强支持状态持久化
    conn.execute('''
    CREATE TABLE IF NOT EXISTS project_phases (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        started_at TEXT,
        completed_at TEXT,
        artifacts TEXT DEFAULT '{}',
        feedback TEXT DEFAULT '{}',
        can_retry BOOLEAN DEFAULT 1,
        retry_count INTEGER DEFAULT 0,
        metadata TEXT DEFAULT '{}',
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 新增: 创建澄清问题表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS clarification_questions (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        question TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        priority INTEGER DEFAULT 0,
        needs_followup BOOLEAN DEFAULT 0,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 新增: 创建澄清问题回答表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS clarification_answers (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        answer TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (question_id) REFERENCES clarification_questions (id),
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 新增: 创建代理活动日志表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS agent_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        message TEXT NOT NULL,
        message_type TEXT DEFAULT 'log',
        timestamp TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects (id),
        FOREIGN KEY (phase_id) REFERENCES project_phases (id)
    )
    ''')
    
    # 新增: 创建智能体活动日志表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS agent_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        message TEXT NOT NULL,
        message_type TEXT DEFAULT 'log',
        timestamp TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects (id),
        FOREIGN KEY (phase_id) REFERENCES project_phases (id)
    )
    ''')
    
    # 新增: 创建智能体活动日志表
    conn.execute('''
    CREATE TABLE IF NOT EXISTS agent_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        message TEXT NOT NULL,
        message_type TEXT DEFAULT 'log',
        timestamp TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects (id),
        FOREIGN KEY (phase_id) REFERENCES project_phases (id)
    )
    ''')
    
    conn.commit()
    return conn

# 在请求前初始化数据库连接
@app.before_request
def before_request():
    if not hasattr(app, 'db') or app.db is None:
        app.db = init_db()

# 在请求后关闭数据库连接 - 为了避免在长连接场景下出现"Cannot operate on a closed database"错误
# 我们不再每次请求后关闭数据库，而是在应用关闭时关闭
@app.teardown_appcontext
def close_db(exception):
    # 不再在每次请求后关闭数据库连接
    pass

# 应用关闭时的清理函数
def shutdown_cleanup():
    if hasattr(app, 'db'):
        app.db.close()

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(projects_bp)

# 主页路由
@app.route("/")
def index():
    return app.send_static_file("index.html")

# 健康检查路由
@app.route("/api/health")
def health_check():
    return jsonify({"status": "healthy"})

# 错误处理
@app.errorhandler(404)
def not_found(e):
    return app.send_static_file("index.html")

if __name__ == "__main__":
    # 确保app.socketio在全局可用
    app.socketio = socketio
    try:
        socketio.run(app, host="0.0.0.0", port=5001, debug=True)
    except KeyboardInterrupt:
        print("服务器关闭中...")
        # 清理资源
        shutdown_cleanup()
    except Exception as e:
        print(f"服务器异常: {e}")
        shutdown_cleanup() 