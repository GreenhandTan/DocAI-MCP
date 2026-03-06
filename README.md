# DocAI-MCP

一个基于 Web 的 AI 文档处理管理系统：用浏览器完成 **文档配置、客户端一键部署、设备注册/心跳、端口映射**管理，并提供实时流量监控与系统资源监控。

**极致轻量 · 开箱即用 · 功能强大**

[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-blue.svg)](https://fastapi.tiangolo.com/)
[![Vue3](https://img.shields.io/badge/Vue-3.x-green.svg)](https://vuejs.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-orange.svg)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)

[核心优势](#核心优势) · [功能特性](#功能特性) · [快速开始](#快速开始) · [端口放行](#端口放行) · [排障](#排障指南) · [开源协议](#开源协议)

---

## 核心优势

### 极致轻量

- **零依赖安装**：Docker Compose 一键部署，无需手动配置环境
- **资源占用低**：核心服务仅需 2GB RAM，适合各种云服务器
- **快速启动**：3 分钟内完成全部服务启动

### 开箱即用

- **预置模板库**：内置合同、报告、纪要等 20+ 专业模板
- **智能识别**：自动识别文档类型并推荐最佳处理方案
- **流式对话**：实时 AI 响应，支持多模型切换（OpenAI/智谱/MiniMax等）

### 功能强大

- **多格式支持**：Word、PDF、Markdown、HTML 互转
- **版本历史**：自动保存文档快照，一键回滚
- **批量处理**：支持批量上传、转换、导出、打包下载
- **可视化工作流**：拖拽式构建文档处理流程（DAG 执行引擎）
- **实时监控**：系统资源、任务状态、存储使用一目了然

---

## 功能特性

### 智能文档处理

- **AI 文档生成**：根据内容和模板智能生成标准文档
- **文档修改润色**：AI 辅助修改、格式化、内容优化
- **模板填充**：自动识别字段并填充内容
- **格式转换**：支持 DOCX ↔ PDF ↔ Markdown ↔ HTML

### 文档审查与分析

- **合规审查**：法律、财务、风险等多维度审查
- **智能批注**：AI 自动标注问题点并给出建议
- **风险评估**：自动评估文档风险等级（low/medium/high/critical）

### 音频转录

- **语音识别**：支持多语言音频转文字
- **说话人分离**：自动区分不同发言人
- **会议纪要生成**：自动生成格式化会议记录
- **行动项提取**：智能提取待办事项

### 在线编辑

- **OnlyOffice 集成**：原生 Office 文档在线编辑
- **多人协作**：实时同步，支持多用户编辑（带用户头像显示）
- **自动版本管理**：每次保存自动创建版本快照

### 可视化工作流

- **拖拽式编辑器**：无需编程构建复杂文档处理流程
- **预置节点**：内容提取、AI 分析、格式转换、文档生成、音频转录等 6 种节点
- **DAG 执行**：基于 Kahn 算法拓扑排序，高效执行工作流

### 多租户管理

- **用户认证**：JWT Token 安全认证（HS256）
- **订阅分级**：Free(1GB)/Pro(10GB)/Enterprise(100GB) 三档服务
- **存储配额**：根据订阅层级分配存储空间，实时监控使用量
- **权限控制**：细粒度文件访问权限管理

### 系统监控

- **实时统计**：用户数、文档数、任务数、成功率
- **历史趋势**：可视化展示系统运行数据（支持自定义天数）
- **资源监控**：存储使用、AI 调用量实时跟踪

### Webhook 通知

- **事件订阅**：task_completed、document_uploaded、review_completed 等
- **签名验证**：HMAC-SHA256 签名保证安全性
- **自动重试**：失败自动重试机制

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│  (Vue3 + TypeScript + TailwindCSS)                         │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP/WebSocket/SSE
┌──────────────────┴──────────────────────────────────────────┐
│                   Nginx (Frontend)                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────────┐
│           FastAPI Backend (Python 3.11+)                    │
│  ┌────────────┬──────────────┬──────────────────────┐      │
│  │  Auth API  │ Document API │  Workflow API         │      │
│  ├────────────┼──────────────┼──────────────────────┤      │
│  │ Template   │  Extended    │  OnlyOffice Callback  │      │
│  └────────────┴──────────────┴──────────────────────┘      │
└──────────────────┬──────────────────────────────────────────┘
                   │
         ┌─────────┼─────────────┬───────────────┐
         │         │             │               │
┌────────┴─────┐ ┌─┴──────────┐ ┌┴───────────┐  ┌┴──────────────┐
│ PostgreSQL   │ │   MinIO    │ │Redis (Cache)│  │ MCP Server    │
│  (Metadata)  │ │  (Storage) │ │             │  │ (AI Tools)    │
└──────────────┘ └────────────┘ └─────────────┘  └───────────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │  AI API (LLM)   │
                                          │  (OpenAI/智谱/  │
                                          │   MiniMax等)    │
                                          └─────────────────┘
```

---

## 快速开始

### 环境要求

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **操作系统**：Linux / Windows / macOS
- **最低配置**：2核 CPU / 4GB RAM / 20GB 磁盘

### 一键部署

```bash
# 1. 克隆项目
git clone https://github.com/your-org/docai-mcp.git
cd docai-mcp

# 2. 配置环境变量
cd deploy
cp .env.example .env
vim .env  # 修改必要配置（数据库密码、AI API Key 等）

# 3. 启动所有服务
bash deploy.sh

# 4. 查看服务状态
docker-compose ps

# 5. 访问系统
# 前端：http://localhost:3000
# 后端API：http://localhost:8000
# API文档：http://localhost:8000/docs
```

### Windows 系统

```cmd
# 使用批处理脚本
cd deploy
deploy.bat
```

### 环境变量说明

**必填项**：

```bash
# 数据库
POSTGRES_PASSWORD=your_secure_password

# AI 配置
AI_API_KEY=your_ai_api_key
AI_API_BASE_URL=https://api.openai.com/v1
AI_MODEL_NAME=gpt-4

# 对象存储
MINIO_ROOT_PASSWORD=your_minio_password

# JWT 密钥
JWT_SECRET=your_jwt_secret_key_min_32_chars
```

**可选项**：

```bash
# OnlyOffice 配置
ONLYOFFICE_PUBLIC_URL=http://localhost:8081
ONLYOFFICE_LANG=zh-CN

# Redis
REDIS_URL=redis://redis:6379/0

# 后端地址（容器间通信）
BACKEND_INTERNAL_URL=http://backend:8000
```

---

## 端口放行

确保以下端口在防火墙/安全组中开放：

| 端口 | 服务          | 说明          | 外部访问 |
| ---- | ------------- | ------------- | -------- |
| 3000 | Frontend      | Web 界面访问  | 必须     |
| 8000 | Backend API   | REST API 服务 | 必须     |
| 8081 | OnlyOffice    | 文档编辑器    | 建议     |
| 5432 | PostgreSQL    | 数据库        | 内部     |
| 9000 | MinIO API     | 对象存储      | 内部     |
| 9001 | MinIO Console | 管理界面      | 可选     |
| 6379 | Redis         | 缓存          | 内部     |
| 3001 | MCP Server    | AI工具服务    | 内部     |

**生产环境建议**：

- 仅开放 80/443 端口
- 通过 Nginx 反向代理访问所有服务
- 启用 SSL/TLS 加密
- 配置防火墙规则限制访问来源

```nginx
# Nginx 配置示例
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
    }

    location /onlyoffice/ {
        proxy_pass http://localhost:8081;
    }
}
```

---

## API 文档

系统启动后，访问以下地址查看完整 API 文档：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

### 核心接口示例

#### 1. 用户认证

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "username": "JohnDoe"
  }'

# 返回示例
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "user_id": "uuid-here",
    "email": "user@example.com",
    "username": "JohnDoe",
    "subscription_tier": "free"
  }
}

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

#### 2. 文件上传

```bash
# 单文件上传
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.docx" \
  -F "is_template=false"

# 批量上传
curl -X POST http://localhost:8000/api/v1/files/upload-batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "content_files=@doc1.pdf" \
  -F "content_files=@doc2.docx" \
  -F "template_file=@template.docx"
```

#### 3. AI 文档生成

```bash
# 创建生成任务
curl -X POST http://localhost:8000/api/v1/tasks/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "fill_template",
    "content_file_ids": ["content-uuid-1", "content-uuid-2"],
    "template_file_id": "template-uuid",
    "preset_template": "contract",
    "requirements": "生成正式的商务合同，强调保密条款",
    "ai_model": "gpt-4"
  }'

# 查询任务状态
curl -X GET http://localhost:8000/api/v1/tasks/TASK_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 4. 流式 AI 对话

```bash
# SSE 流式对话
curl -N -X POST http://localhost:8000/api/v1/ai/chat/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请帮我总结这份文档的核心要点",
    "file_ids": ["doc-uuid"],
    "template_file_id": "template-uuid",
    "model": "gpt-4",
    "history": [
      {"role": "user", "content": "你好"},
      {"role": "assistant", "content": "你好！我是AI文档助手"}
    ]
  }'

# 返回 SSE 流
data: {"type":"thinking","content":"正在思考..."}
data: {"type":"content","content":"这份文档主要包含..."}
data: {"type":"done","content":""}
```

#### 5. 文档版本管理

```bash
# 查看版本历史
curl -X GET http://localhost:8000/api/v1/files/FILE_ID/versions \
  -H "Authorization: Bearer YOUR_TOKEN"

# 创建版本快照
curl -X POST http://localhost:8000/api/v1/files/FILE_ID/create-version \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"change_description": "重大修改前的备份"}'

# 恢复到指定版本
curl -X POST http://localhost:8000/api/v1/files/FILE_ID/restore-version/VERSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 6. 批量下载

```bash
# 批量下载并打包为 ZIP
curl -X POST http://localhost:8000/api/v1/files/download-batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_ids": ["id1", "id2", "id3"]}' \
  --output documents.zip
```

---

## 使用指南

### 典型工作流

1. **注册/登录账户**
   - 访问系统首页
   - 使用邮箱注册账号
   - 登录后自动获得 1GB免费存储空间

2. **上传文档**
   - 点击"上传文件"按钮
   - 支持拖拽或选择文件
   - 可标记为模板文件

3. **选择处理模式**
   - **直接对话**：在聊天框中描述需求，AI 实时响应
   - **任务处理**：创建后台任务，生成新文档
   - **在线编辑**：使用 OnlyOffice 直接编辑

4. **选择模板** （可选）
   - 预置模板：简历、报告、合同、会议纪要等
   - 自定义模板：上传 DOCX 模板文件
   - 文本模板：粘贴长文本模板描述

5. **AI 处理**
   - 实时对话：可多轮迭代优化
   - 后台任务：自动调用 MCP 工具链
   - 查看结果：下载生成的文档

6. **文档管理**
   - 查看版本历史
   - 在线编辑修改
   - 批量导出下载

### 高级功能

#### 创建工作流

1. 进入"工作流"页面
2. 拖拽添加节点：
   - **内容提取**：从文件中提取文本
   - **文档分析**：AI 分析文档结构
   - **文档审查**：法律/合规审查
   - **AI 处理**：自定义 AI 处理逻辑
   - **文档生成**：生成新文档
3. 连接节点，构建处理流程
4. 保存并执行工作流

#### 配置 Webhook

1. 进入"设置" → "Webhook"
2. 点击"添加 Webhook"
3. 填写信息：
   - 名称：便于识别
   - URL：接收通知的地址
   - 事件：选择关注的事件类型
   - Secret：用于签名验证（可选）
4. 保存后，系统将在事件发生时推送通知

---

## 排障指南

### 常见问题

#### 1. 服务无法启动

```bash
# 检查 Docker 日志
docker-compose logs backend
docker-compose logs mcp-server
docker-compose logs postgres

# 重启服务
docker-compose restart

# 完全重建
docker-compose down -v
docker-compose up -d --build
```

#### 2. AI 调用失败

**症状**：聊天无响应、任务失败
**排查步骤**：

```bash
# 1. 检查环境变量
docker-compose exec backend env | grep AI_

# 2. 测试 AI API 连通性
curl -X POST $AI_API_BASE_URL/chat/completions \
  -H "Authorization: Bearer $AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"test"}]}'

# 3. 查看 MCP Server 日志
docker-compose logs mcp-server | tail -50
```

**常见原因** ：

- `AI_API_KEY` 未设置或错误
- `AI_API_BASE_URL` 格式错误（应为 https://api.openai.com/v1 或完整路径）
- 网络连接问题
- API 配额耗尽

#### 3. 文件上传失败

**症状**：上传进度卡住、返回 500 错误

```bash
# 1. 检查 MinIO 状态
docker-compose ps minio
docker-compose logs minio

# 2. 检查存储配额
curl -X GET http://localhost:8000/api/v1/subscription/info \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. 检查  bucket 是否创建
docker-compose exec minio mc ls myminio/
```

#### 4. OnlyOffice 无法编辑

**症状**：点击编辑按钮无响应、文档加载失败

```bash
# 1. 检查 OnlyOffice 服务
docker-compose ps onlyoffice

# 2. 检查配置
docker-compose exec backend env | grep ONLYOFFICE

# 3. 查看浏览器控制台错误
# 可能原因：混合内容警告（HTTP/HTTPS）、JWT 配置错误
```

**解决方案**：

- 确保 `ONLYOFFICE_PUBLIC_URL` 与浏览器访问地址一致
- 检查 `JWT_SECRET` 配置在所有服务中保持一致
- 如果使用 HTTPS，确保 OnlyOffice 也使用 HTTPS

#### 5. 401 认证失败

**症状**：所有 API 请求返回 401

```bash
# 1. 检查 Token 是否过期
# JWT Token 默认有效期 7 天

# 2. 重新登录获取新 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpass"}'

# 3. 检查 JWT_SECRET 配置
docker-compose exec backend env | grep JWT_SECRET
```

#### 6. 数据库连接失败

```bash
# 1. 检查 PostgreSQL 状态
docker-compose ps postgres

# 2. 测试数据库连接
docker-compose exec postgres psql -U docai -d docai_db -c "SELECT 1;"

# 3. 查看数据库日志
docker-compose logs postgres | tail -50

# 4. 重置数据库（警告：会清空所有数据）
docker-compose down -v
RESET_VOLUMES=1 bash deploy/deploy.sh
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f mcp-server
docker-compose logs -f onlyoffice

# 只看最近 100 行
docker-compose logs --tail=100 backend

# 查看带时间戳的日志
docker-compose logs -f -t backend
```

### 数据备份

```bash
# 备份 PostgreSQL 数据库
docker-compose exec postgres pg_dump -U docai docai_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 恢复数据库
cat backup_20260306_120000.sql | docker-compose exec -T postgres psql -U docai docai_db

# 备份 MinIO 数据
docker run --rm -v docai-mcp_minio_data:/data -v $(pwd):/backup \
  busybox tar czf /backup/minio_backup_$(date +%Y%m%d).tar.gz /data

# 恢复 MinIO 数据
docker run --rm -v docai-mcp_minio_data:/data -v $(pwd):/backup \
  busybox tar xzf /backup/minio_backup_20260306.tar.gz -C /
```

### 性能优化

```bash
# 1. 查看资源使用
docker stats

# 2. 清理未使用的资源
docker system prune -a

# 3. 优化 PostgreSQL 连接池
# 在 .env 中设置：
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# 4. 启用 Redis 缓存
# 缓存 AI 响应、文档元数据等
```

---

## 开发指南

### 本地开发环境

#### 后端开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example .env
vim .env

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

#### MCP Server 开发

```bash
cd mcp-server

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务器
python server.py
```

### 数据库迁移

```bash
cd backend

# 创建新迁移
alembic revision --autogenerate -m "Add new table"

# 查看迁移历史
alembic history

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 添加新的 MCP 工具

在 `mcp-server/server.py` 中添加新工具：

```python
@mcp.tool()
def my_custom_tool(
    file_id: str,
    param1: str,
    ai_model: str | None = None
) -> dict:
    """
    工具描述

    Args:
        file_id: 文件 ID
        param1: 参数说明
        ai_model: AI 模型名称

    Returns:
        处理结果
    """
    # 1. 获取文件
    doc = _get_document(file_id)

    # 2. 处理逻辑
    result = process_document(doc, param1)

    # 3. 调用 AI（如需要）
    if ai_model:
        ai_result = ai_client.generate_completion(
            f"Process: {result}",
            model=ai_model
        )

    # 4. 返回结果
    return {
        "status": "success",
        "result": result,
        "ai_result": ai_result
    }
```

### 代码风格

#### Python (PEP 8)

```bash
# 安装格式化工具
pip install black isort flake8

# 格式化代码
black backend/app
isort backend/app

# 代码检查
flake8 backend/app
```

#### TypeScript (ESLint + Prettier)

```bash
# 格式化代码
npm run lint:fix

# 类型检查
npm run type-check
```

---

## 技术栈

### 后端技术栈

- **FastAPI 0.109** - 现代高性能 Web 框架
- **SQLAlchemy 2.0** - ORM 框架
- **AsyncPG 0.29** - 异步 PostgreSQL 驱动
- **Pydantic 2.6** - 数据验证
- **python-jose 3.3** - JWT 认证
- **passlib 1.7** - 密码哈希
- **httpx 0.26** - 异步 HTTP 客户端
- **Alembic 1.13** - 数据库迁移

### 前端技术栈

- **Vue 3.4** - 渐进式 JavaScript 框架
- **TypeScript 5.3** - 类型安全
- **Vite 5.0** - 极速构建工具
- **TailwindCSS 3.4** - 实用优先的 CSS 框架
- **Axios** - HTTP 客户端
- **Lucide Icons** - 图标库

### 基础设施

- **PostgreSQL 15** - 关系型数据库
- **MinIO RELEASE.2024** - S3 兼容对象存储
- **Redis 7** - 缓存与消息队列
- **OnlyOffice Document Server** - 在线文档编辑器
- **Docker Compose** - 容器编排

### AI 服务

- **FastMCP** - Model Context Protocol 服务器
- **python-docx** - Word 文档处理
- **PyMuPDF** - PDF 文档处理
- **httpx** - AI API 调用

---

## 性能指标

### 资源占用

| 服务       | 空闲状态   | 负载状态   | 备注                  |
| ---------- | ---------- | ---------- | --------------------- |
| Backend    | ~256MB     | ~512MB     | 单实例支持 1000+ 并发 |
| MCP Server | ~128MB     | ~256MB     | CPU 密集型操作        |
| PostgreSQL | ~256MB     | ~512MB     | 根据数据量增长        |
| MinIO      | ~128MB     | ~256MB     | 根据文件数量增长      |
| Redis      | ~64MB      | ~128MB     | 内存数据库            |
| OnlyOffice | ~512MB     | ~1GB       | 文档编辑服务          |
| **总计**   | **~1.3GB** | **~2.5GB** | 推荐 4GB+ RAM         |

### 性能测试

```bash
# API 并发测试（使用 Apache Bench）
ab -n 1000 -c 100 http://localhost:8000/api/v1/files

# 文件上传性能
ab -n 100 -c 10 -p document.docx -T 'multipart/form-data' \
   http://localhost:8000/api/v1/files/upload

# AI 对话延迟
# 平均响应时间：< 2秒（取决于 AI 模型）
```

### 扩展性

- **水平扩展**：支持多实例部署（需配置负载均衡）
- **数据库**：支持 PostgreSQL 主从复制、读写分离
- **存储**：MinIO 支持分布式集群模式
- **缓存**：Redis 支持哨兵/集群模式

---

## 路线图

### v1.0 - 核心功能（已完成）

- [x] 用户认证与权限管理（JWT）
- [x] 文件上传下载管理
- [x] AI 文档生成与修改
- [x] 模板库管理（CRUD）
- [x] 文档版本历史
- [x] 多格式导出（PDF/Markdown/HTML）
- [x] 批量下载打包（ZIP）
- [x] OnlyOffice 在线编辑
- [x] 流式 AI 对话（SSE）
- [x] 文档审查（法律/合规/风险）
- [x] 音频转录与会议纪要
- [x] 基础工作流系统（DAG 执行）
- [x] 系统监控面板
- [x] Webhook 通知
- [x] 订阅层级管理

### v1.2 - 企业功能（开发中）

- [ ] OCR 文字识别
- [ ] 知识库与 RAG（检索增强生成）
- [ ] 文档 Diff 对比
- [ ] 定时任务调度
- [ ] 批量处理队列优化
- [ ] 多语言支持（i18n）

### 📋 v2.0 - 可视化与协作（规划中）

- [ ] 完整的拖拽式工作流编辑器（Vue Flow）
- [ ] 自定义 AI 节点与插件系统
- [ ] 工作流模板市场
- [ ] 实时协作编辑（WebSocket 同步）
- [ ] 评论与批注系统
- [ ] 权限管理增强（RBAC）

### v3.0 - 智能化（未来）

- [ ] AI Agent 自主决策
- [ ] 智能推荐系统
- [ ] 文档质量评分
- [ ] 自动化测试与验证
- [ ] 区块链存证集成

---

## 贡献指南

我们欢迎各种形式的贡献！

### 报告 Bug

在 [Issues](https://github.com/your-org/docai-mcp/issues) 中提交 Bug 报告，请包含：

1. **问题描述**：清晰简洁的描述
2. **复现步骤**：
   - 步骤 1
   - 步骤 2
   - 步骤 3
3. **预期行为**：应该发生什么
4. **实际行为**：实际发生了什么
5. **环境信息**：
   - OS: [例如 Ubuntu 22.04]
   - Docker 版本: [例如 24.0.1]
   - 浏览器: [例如 Chrome 120]
6. **日志/截图**：相关的错误日志或截图

### 提交功能建议

在 [Discussions](https://github.com/your-org/docai-mcp/discussions) 中提交功能建议：

- 描述希望添加的功能
- 说明为什么需要这个功能
- 提供可能的实现方案

### 提交 Pull Request

1. Fork 本仓库
2. 创建特性分支：
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. 提交更改：
   ```bash
   git commit -m 'feat: add amazing feature'
   ```
4. 推送到分支：
   ```bash
   git push origin feature/amazing-feature
   ```
5. 提交 Pull Request

### 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**：

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**：

```
feat(auth): add OAuth2 social login

- Implement GitHub OAuth2 flow
- Add Google OAuth2 flow
- Update user model to store provider info

Closes #123
```

### 代码审查

所有 PR 需要至少一位维护者的审查才能合并。

---

## 开源协议

本项目采用 **MIT License** 开源。

```
MIT License

Copyright (c) 2026 DocAI-MCP Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/) - 强大的 Python Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [OnlyOffice](https://www.onlyoffice.com/) - 开源文档编辑器
- [MinIO](https://min.io/) - 高性能对象存储
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI 工具标准化协议
- [PostgreSQL](https://www.postgresql.org/) - 世界上最先进的开源数据库
- [Redis](https://redis.io/) - 内存数据库
- [Docker](https://www.docker.com/) - 容器化平台

---

## 社区与支持

- **GitHub**: [github.com/your-org/docai-mcp](https://github.com/your-org/docai-mcp)
- **文档**: [docs.docai-mcp.com](https://docs.docai-mcp.com)
- **Discord**: [discord.gg/docai-mcp](https://discord.gg/docai-mcp)
- **邮箱**: support@docai-mcp.com
- **博客**: [blog.greenhandtan.top](https://greenhandtan.top)

### 获取帮助

1. 查看 [文档](https://docs.docai-mcp.com)
2. 搜索 [Issues](https://github.com/your-org/docai-mcp/issues)
3. 在 [Discussions](https://github.com/your-org/docai-mcp/discussions) 提问
4. 加入 Discord 社区

---

## 赞助

如果这个项目对你有帮助，欢迎赞助支持开发：

- **GitHub Sponsors**: [github.com/sponsors/your-username](https://github.com/sponsors/your-username)
- **爱发电**: [afdian.net/@your-username](https://afdian.net/@your-username)
- **微信赞赏码**: [查看二维码](docs/images/wechat-qr.png)

---

<p align="center">
  <sub>Built by Tan Xin and the DocAI-MCP Community</sub>
</p>

<p align="center">
  <a href="https://github.com/your-org/docai-mcp/stargazers">Star</a> ·
  <a href="https://github.com/your-org/docai-mcp/issues">Report Bug</a> ·
  <a href="https://github.com/your-org/docai-mcp/discussions">Discuss</a>
</p>
