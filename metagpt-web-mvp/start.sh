#!/bin/bash

# 创建必要的目录
mkdir -p data

# 检查是否有Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "错误: 未安装Docker，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误: 未安装Docker Compose，请先安装Docker Compose"
    exit 1
fi

# 构建和启动容器
echo "正在启动MetaGPT Web..."
docker-compose up -d

# 检查是否成功启动
if [ $? -eq 0 ]; then
    echo "MetaGPT Web已成功启动！"
    echo "请访问 http://localhost 使用以下凭据登录:"
    echo "用户名: admin"
    echo "密码: admin123"
else
    echo "启动失败，请查看日志以获取更多信息"
    docker-compose logs
fi 