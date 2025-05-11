# MetaGPT Web MVP

MetaGPT Web是MetaGPT命令行工具的Web界面增强，提供直观的用户体验，包括需求提交、开发状态监控和结果查看等功能。

## 功能特点

- **需求输入**：用户友好的表单提交需求
- **状态监控**：实时展示开发进度和关键节点
- **结果浏览**：查看和下载生成的文档与代码

## 系统架构

- **前端**：Vue.js、Element Plus、ECharts 
- **后端**：Flask、SQLite
- **集成**：与现有MetaGPT系统通过命令行方式集成

## 快速开始

### 前提条件

- Docker和Docker Compose已安装
- MetaGPT已安装和配置

### 使用Docker Compose运行

1. 克隆仓库
```bash
git clone <仓库地址>
cd metagpt-web-mvp
```

2. 构建和启动容器
```bash
docker-compose up -d
```

3. 访问 Web 界面
```
http://localhost
```

4. 使用以下凭据登录
```
用户名: admin
密码: admin123
```

### 手动安装

#### 后端安装

1. 进入后端目录
```bash
cd metagpt-web-mvp/backend
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 创建 .env 文件
```bash
cp .env.example .env
# 编辑 .env 文件设置环境变量
```

5. 运行后端
```bash
flask run
```

#### 前端安装

1. 进入前端目录
```bash
cd metagpt-web-mvp/frontend
```

2. 安装依赖
```bash
npm install
```

3. 创建 .env 文件
```bash
cp .env.example .env
# 编辑 .env 文件设置API地址
```

4. 开发模式运行
```bash
npm run serve
```

5. 构建生产版本
```bash
npm run build
```

## 配置说明

### 后端配置

编辑 `.env` 文件修改以下配置：

- `JWT_SECRET_KEY`: JWT令牌加密密钥
- `ADMIN_PASSWORD`: 管理员密码
- `DATA_DIR`: 数据存储目录

### 前端配置

编辑 `.env` 文件修改以下配置：

- `VUE_APP_API_URL`: 后端API地址

## 项目结构

```
metagpt-web-mvp/
├── backend/              # Flask后端
│   ├── api/              # API路由
│   ├── models/           # 数据模型
│   ├── utils/            # 工具函数
│   ├── app.py            # 应用入口
│   ├── requirements.txt  # 依赖列表
│   └── Dockerfile        # 后端Docker配置
├── frontend/             # Vue.js前端
│   ├── public/           # 静态资源
│   ├── src/              # 源代码
│   │   ├── assets/       # 资源文件
│   │   ├── components/   # 组件
│   │   ├── views/        # 页面
│   │   ├── router/       # 路由
│   │   ├── utils/        # 工具函数
│   │   ├── App.vue       # 根组件
│   │   └── main.js       # 入口文件
│   ├── package.json      # 依赖配置
│   └── Dockerfile        # 前端Docker配置
├── data/                 # 数据存储
├── docker-compose.yml    # Docker Compose配置
└── README.md             # 项目说明
```

## 常见问题

1. **问**: 如何更改默认登录凭据？
   **答**: 编辑后端 `.env` 文件中的 `ADMIN_PASSWORD` 变量。

2. **问**: 如何与自定义的MetaGPT版本集成？
   **答**: 修改 `backend/api/projects.py` 文件中的 `execute_metagpt_task` 函数，调整命令行参数以匹配您的MetaGPT版本。

3. **问**: Web界面支持哪些浏览器？
   **答**: 支持所有现代浏览器，推荐使用Chrome、Firefox、Edge等最新版本。

## 许可证

与MetaGPT采用相同的许可证。 