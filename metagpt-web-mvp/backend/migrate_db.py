import os
import sqlite3
import uuid
from datetime import datetime

def migrate_database(db_path):
    """
    创建或更新数据库表结构
    """
    # 检查目录是否存在，不存在则创建
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        created_at TEXT
    )
    ''')
    
    # 创建项目表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT,
        requirement TEXT,
        status TEXT,
        created_at TEXT,
        updated_at TEXT,
        user_id TEXT,
        output_dir TEXT,
        clarification_completed INTEGER DEFAULT 0,
        clarification_completed_at TEXT,
        domain TEXT DEFAULT 'general',
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # 创建项目文件表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS project_files (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        name TEXT,
        path TEXT,
        type TEXT,
        size INTEGER,
        created_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建项目日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS project_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        agent_name TEXT,
        message TEXT,
        message_type TEXT,
        phase_id TEXT,
        created_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建项目阶段表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS project_phases (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        phase_id TEXT,
        name TEXT,
        description TEXT,
        status TEXT,
        started_at TEXT,
        completed_at TEXT,
        step INTEGER,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建澄清问题表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clarification_questions (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        round_id TEXT,
        question TEXT,
        priority INTEGER,
        status TEXT,
        created_at TEXT,
        needs_followup INTEGER DEFAULT 0,
        severity TEXT DEFAULT 'medium',
        is_followup INTEGER DEFAULT 0,
        parent_question_id TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (id),
        FOREIGN KEY (round_id) REFERENCES clarification_rounds (id),
        FOREIGN KEY (parent_question_id) REFERENCES clarification_questions (id)
    )
    ''')
    
    # 创建澄清问题回答表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clarification_answers (
        id TEXT PRIMARY KEY,
        question_id TEXT,
        project_id TEXT,
        answer TEXT,
        created_at TEXT,
        FOREIGN KEY (question_id) REFERENCES clarification_questions (id),
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建多轮澄清轮次表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clarification_rounds (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        round_id TEXT,
        round_number INTEGER,
        name TEXT,
        description TEXT,
        status TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 创建需求分析表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS requirement_analysis (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        clarity_score REAL,
        dimension_scores TEXT,
        ambiguous_points TEXT,
        consistency_issues TEXT,
        created_at TEXT,
        updated_at TEXT,
        domain TEXT DEFAULT 'general',
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # 提交更改
    conn.commit()
    
    # 检查是否需要添加新列
    try:
        # 检查projects表是否有clarification_completed列
        cursor.execute("SELECT clarification_completed FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE projects ADD COLUMN clarification_completed INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE projects ADD COLUMN clarification_completed_at TEXT")
        conn.commit()

    # 检查projects表是否有domain列
    try:
        cursor.execute("SELECT domain FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE projects ADD COLUMN domain TEXT DEFAULT 'general'")
        conn.commit()
        
    # 检查requirement_analysis表是否有consistency_issues列
    try:
        cursor.execute("SELECT consistency_issues FROM requirement_analysis LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE requirement_analysis ADD COLUMN consistency_issues TEXT")
        conn.commit()
        
    # 检查requirement_analysis表是否有domain列
    try:
        cursor.execute("SELECT domain FROM requirement_analysis LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE requirement_analysis ADD COLUMN domain TEXT DEFAULT 'general'")
        conn.commit()
        
    # 检查clarification_questions表是否有severity列
    try:
        cursor.execute("SELECT severity FROM clarification_questions LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE clarification_questions ADD COLUMN severity TEXT DEFAULT 'medium'")
        conn.commit()
        
    # 检查clarification_questions表是否有is_followup和parent_question_id列
    try:
        cursor.execute("SELECT is_followup FROM clarification_questions LIMIT 1")
    except sqlite3.OperationalError:
        # 不存在则添加
        cursor.execute("ALTER TABLE clarification_questions ADD COLUMN is_followup INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE clarification_questions ADD COLUMN parent_question_id TEXT")
        conn.commit()
    
    # 最后关闭连接
    conn.close()
    
    print(f"Database migrated successfully: {db_path}")

if __name__ == "__main__":
    db_path = "backend/data/metagpt-web.db"
    migrate_database(db_path) 