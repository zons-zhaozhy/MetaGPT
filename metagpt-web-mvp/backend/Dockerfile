FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装MetaGPT
# 注意：根据实际需要调整MetaGPT的安装方式
RUN pip install --no-cache-dir metagpt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV DATA_DIR=/app/data

# 启动应用
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"] 