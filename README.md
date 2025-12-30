# DocAI-MCP 智能文档编排系统

基于 AI 的智能文档处理系统，支持文档上传、AI 驱动的排版和内容填充、在线编辑与修改。

## 功能特性

- 文档上传与管理
- 预置模板库（简历、报告、合同、会议纪要等）
- AI 智能处理文档排版和内容填充
- OnlyOffice 在线编辑器集成
- 支持迭代修改文档
- 实时任务进度跟踪

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- 至少 4GB 可用内存

### 部署步骤

1. 进入部署目录：

```bash
cd deploy
```

2. 确认 `.env` 配置文件存在并已配置（已预配置）

3. 运行部署脚本：

```bash
./deploy.sh
```

4. 等待所有服务启动完成（约 2-3 分钟）

5. 访问系统：
   - 前端界面: http://localhost:3000
   - 后端 API: http://localhost:8000
   - MinIO 控制台: http://localhost:9001 (admin/password123)
   - OnlyOffice: http://localhost:8081

## 使用说明

### 1. 上传文档

- 在左侧边栏点击"上传文档"
- 选择内容文档（可多选）
- 可选择模板文档（可选）

### 2. 选择模板

- 从模板库中选择预置模板
- 或上传自定义模板文档

### 3. 发送需求

- 在聊天界面输入处理需求
- 例如："请帮我整理这份文档的格式"
- AI 会自动创建处理任务

### 4. 预览与编辑

- 任务完成后，点击"预览"按钮查看结果
- 在右侧编辑器中在线编辑文档
- 编辑会自动保存到 MinIO

### 5. 迭代修改

- 点击"修改结果"按钮进入修改模式
- 输入修改要求
- AI 会基于当前文档进行修改

### 6. 下载文档

- 在文档列表中点击"下载"按钮
- 或在编辑器中下载

## 服务管理

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f mcp-server
docker-compose logs -f frontend
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart [service_name]
```

### 清理数据

```bash
# 停止并删除所有容器和数据卷
docker-compose down -v
```

## 技术架构

- **前端**: Vue 3 + TypeScript + TailwindCSS
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **对象存储**: MinIO
- **文档编辑**: OnlyOffice Document Server
- **AI 服务**: 智谱 AI (GLM-4.5-Air)
- **消息队列**: Redis
- **MCP 协议**: Model Context Protocol

## 项目结构

```
DocAI-MCP/
├── backend/           # FastAPI 后端服务
├── frontend/          # Vue 3 前端应用
├── mcp-server/        # MCP 协议服务端
└── deploy/            # 部署配置
    ├── .env          # 环境配置
    ├── docker-compose.yml
    └── deploy.sh     # 部署脚本
```

## 常见问题

### Q: 服务启动失败怎么办？

A: 检查端口是否被占用，确保 3000、8000、8081、9000、9001、5432、6379 端口可用。

### Q: AI 响应很慢？

A: 智谱 AI 的响应速度取决于网络和 API 限制，请耐心等待。

### Q: OnlyOffice 加载失败？

A: 确保 OnlyOffice 服务已启动，检查 http://localhost:8081 是否可访问。

### Q: 如何更换 AI 模型？

A: 修改 `deploy/.env` 文件中的 `AI_MODEL_NAME` 和 `AI_API_KEY`。

## 开发说明

### 本地开发

1. 启动基础设施服务：

```bash
cd deploy
docker-compose up -d postgres redis minio onlyoffice
```

2. 启动后端：

```bash
cd ../backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

3. 启动 MCP Server：

```bash
cd ../mcp-server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

4. 启动前端：

```bash
cd ../frontend
npm install
npm run dev
```

## 许可证

MIT License
