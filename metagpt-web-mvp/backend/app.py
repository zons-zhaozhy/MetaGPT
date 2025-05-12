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
from api.requirement_clarifier import clarify_bp
from migrate_db import migrate_database

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder="../frontend/dist", static_url_path="/")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-secret-key")
app.config["DATA_DIR"] = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
app.config["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")

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
    
    # 使用迁移脚本更新数据库结构
    migrate_database(db_path)
    
    # 连接到数据库
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
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
app.register_blueprint(clarify_bp)

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