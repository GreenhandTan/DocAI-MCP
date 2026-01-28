# DocAI-MCP 智能文档编排系统

DocAI-MCP 是一个面向“文档上传 → AI 总结/填充 → 在线编辑 → 迭代修改”的一体化系统，内置 MCP（Model Context Protocol）工具链，用于把文档处理能力模块化编排到任务/工作流里。

- 作者：Tan Xin（greenhandtan）
- 博客：https://greenhandtan.top

## 当前系统能力概览（基于仓库现状）

### 已实现的核心能力
- **文档管理**：上传/列表/下载（MinIO 对象存储 + PostgreSQL 元数据）  
- **聊天式处理（SSE 流式）**：前端本地保存会话历史，后端以 SSE 方式流式转发模型输出  
- **模板总结/按模板输出**
  - 预置模板类型：简历/报告/会议纪要/合同/提案
  - 自定义模板：支持上传模板文件（doc/docx）或直接粘贴“长文本模板描述”（会自动压缩成可执行模板后注入提示词）
- **异步任务编排**：创建任务 → 后台调用 MCP 工具链执行 → 产出新文档并回传 fileId
- **OnlyOffice 在线编辑**：在线预览/编辑 docx，保存回调可回写 MinIO；支持配置中文界面（`ONLYOFFICE_LANG=zh-CN`）

### 扩展功能（/features 页面）
- **AI 审查**：通用/法律/合规/风险（后端创建审查任务，后台调 MCP `document_reviewer`）
- **工作流编排**：可创建并执行 DAG 工作流，支持执行状态查询（当前以 API 为主，前端提供基础编辑/执行 UI）
- **语音转会议纪要**：API 与前端流程已接入；但 MCP 侧 ASR 在未配置 `WHISPER_API_URL` 时为演示模式（仅返回提示，不会真实转录）

### 重要说明（影响体验/预期）
- **上下文与二次总结**：聊天上下文由前端本地（localStorage）保存，后端不存会话；只要不清理浏览器存储即可多轮迭代。
- **二次读取 404**：如果每次部署都 `down -v` 会清空 Postgres/MinIO 数据卷，旧的 `fileId` 将失效。部署脚本已调整为默认不清空数据卷。

## 技术架构

- **前端**：Vue 3 + TypeScript + TailwindCSS（nginx 静态部署）
- **后端**：FastAPI + SQLAlchemy + PostgreSQL
- **对象存储**：MinIO（uploads/outputs buckets）
- **文档编辑**：OnlyOffice Document Server（JWT + callback 回写）
- **任务/缓存**：Redis
- **MCP 工具服务**：mcp-server（FastAPI + FastMCP），封装 content_extractor / template_matcher / document_generator / document_modifier 等工具
- **AI 服务**：OpenAI-compatible Chat Completions（由 `AI_API_BASE_URL` 配置，支持多模型）

## 快速开始（Docker 一键部署）

### 前置要求
- Docker Desktop / Docker Engine
- Docker Compose（`docker compose` 或 `docker-compose`）

### 启动
在项目根目录执行：

```bash
bash deploy/deploy.sh
```

等待容器启动后访问：
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- MinIO 控制台：http://localhost:9001
- OnlyOffice：http://localhost:8081

### 数据是否保留（非常重要）
部署脚本默认不会删除数据卷（避免重启/重建后文件丢失导致 404）。如需清理全部数据：

```bash
RESET_VOLUMES=1 bash deploy/deploy.sh
```

Windows 下对应：
```bat
set RESET_VOLUMES=1
deploy\deploy.bat
```

## 配置说明（deploy/.env）

### AI 相关（必须）
- `AI_API_KEY`：上游模型服务 key
- `AI_API_BASE_URL`：上游 OpenAI-compatible 地址（支持基础路径或完整 `/chat/completions`）
- `AI_MODEL_NAME`：默认模型名（前端也可选择模型）

### OnlyOffice 相关
- `ONLYOFFICE_API_URL`：后端用于回调/联通 OnlyOffice 的内部地址
- `ONLYOFFICE_PUBLIC_URL`：前端加载 DocsAPI 的地址（如需要改域名/反代）
- `ONLYOFFICE_LANG`：OnlyOffice 界面语言（默认 `zh-CN`）

### 存储/数据库
- `MINIO_*` / `POSTGRES_*` / `REDIS_URL`：基础设施配置

## 使用指南（推荐工作流）

1) 上传文档（PDF/DOCX/TXT）  
2) 选择模板：
   - 预置模板：直接点选
   - 自定义模板（文件）：上传 doc/docx
   - 自定义模板（文本）：粘贴模板描述，适合“很长的规范/格式要求”
3) 在聊天框描述需求（可多轮迭代），系统将：
   - 在聊天中给出总结/结构化输出（带上下文）
   - 若选择了文件/模板操作，会创建后台任务并产出新文档
4) 任务完成后，可进入 OnlyOffice 在线编辑并下载

## 项目结构

```
DocAI-MCP/
├── backend/            # FastAPI 后端服务
├── frontend/           # Vue 3 前端应用
├── mcp-server/         # MCP 工具服务端（FastMCP + FastAPI）
└── deploy/             # Docker Compose 与一键脚本
```

## 许可证与署名要求

本项目采用 MIT License（见 [LICENSE](./LICENSE)）。

你可以自由商用、二次开发、分发与转载；但必须：
- **保留 LICENSE 与版权声明**
- 在你的产品/文档/发行说明中**注明原作者：Tan Xin（greenhandtan）**并附上博客链接：https://greenhandtan.top
