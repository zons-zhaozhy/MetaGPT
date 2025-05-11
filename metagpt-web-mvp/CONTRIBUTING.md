# 开发者贡献指南

感谢您对MetaGPT Web项目的关注！本文档提供参与项目开发和贡献代码的相关指南。

## 开发环境设置

### 后端开发

1. 克隆仓库并创建虚拟环境
```bash
git clone <仓库地址>
cd metagpt-web-mvp
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

3. 设置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件设置环境变量
```

4. 运行开发服务器
```bash
flask run --debug
```

### 前端开发

1. 安装前端依赖
```bash
cd frontend
npm install
```

2. 设置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件设置API地址
```

3. 运行开发服务器
```bash
npm run serve
```

## 代码风格指南

### Python代码

- 遵循PEP 8风格指南
- 使用类型注解
- 编写docstring
- 运行pylint和flake8检查代码质量

### JavaScript/Vue代码

- 使用ESLint检查代码质量
- 遵循Vue风格指南
- 使用Prettier格式化代码

## 提交Pull Request

1. Fork本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的修改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开Pull Request

## 开发注意事项

### API开发

- 所有API应遵循RESTful设计原则
- 新增API应在`backend/api`目录下创建
- 确保添加适当的JWT验证和权限检查
- 编写测试用例

### 前端开发

- 组件应放在`frontend/src/components`目录下
- 页面应放在`frontend/src/views`目录下
- 使用Vue Router管理路由
- 保持组件的单一职责原则

## 测试

### 后端测试

```bash
cd backend
pytest
```

### 前端测试

```bash
cd frontend
npm run test
```

## 文档

- 更新API文档
- 更新用户指南
- 更新本README文件（如有必要）

## 许可证

与MetaGPT采用相同的许可证。 