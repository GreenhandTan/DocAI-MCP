import httpx
import json
import logging
from app.core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import ProcessingTask, Document, DocumentReview, Workflow, WorkflowExecution, AudioTranscription
from app.database import SessionLocal
import uuid
import datetime

settings = get_settings()
logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    def __init__(self, task_id: str, preset_template: str | None = None, modifications: str | None = None, ai_model: str | None = None):
        self.task_id = task_id
        self.mcp_base_url = "http://mcp-server:3000/api/tools"
        self.preset_template = preset_template
        self.modifications = modifications
        self.ai_model = ai_model
        
    async def run(self):
        async with SessionLocal() as db:
            task = await self._get_task(db, self.task_id)
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            if not self.ai_model and getattr(task, "ai_model", None):
                self.ai_model = task.ai_model

            try:
                await self._update_status(db, "processing")
                
                if task.task_type == "modify_document":
                    await self._handle_modify_task(db, task)
                else:
                    await self._handle_generation_task(db, task)
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Workflow failed: {e}")
                task.status = "failed"
                task.error_message = str(e)
                await db.commit()

    async def _handle_generation_task(self, db: AsyncSession, task: ProcessingTask):
        if not task.content_file_ids:
            raise Exception("No content files provided")
        
        content_analysis = []
        for file_id in task.content_file_ids:
            res = await self._call_tool("content_extractor", {"file_id": str(file_id), "format": "markdown"})
            content_analysis.append(res.get("content", ""))
        
        full_content = "\n\n".join(content_analysis)
        
        if task.template_file_id:
            template_style = await self._call_tool("document_analyzer", {
                "file_id": str(task.template_file_id), 
                "analysis_type": "style",
                **({"ai_model": self.ai_model} if self.ai_model else {})
            })
        else:
            template_style = {}
        
        plan = await self._call_tool("template_matcher", {
            "content_file_ids": [str(f) for f in task.content_file_ids], 
            "template_file_id": str(task.template_file_id) if task.template_file_id else "none",
            "keep_styles": True,
            **({"ai_model": self.ai_model} if self.ai_model else {})
        })
        
        result = await self._call_tool("document_generator", {
            "content": full_content,
            "template_file_id": str(task.template_file_id) if task.template_file_id else "none",
            "output_format": "docx",
            "preset_template": self.preset_template,
            **({"ai_model": self.ai_model} if self.ai_model else {})
        })
        
        logger.info(f"Document generator result: {result}")
        
        # 检查是否有错误
        if result.get("error"):
            raise Exception(f"Document generation failed: {result.get('error')}")
        
        result_file_id_str = result.get("result_file_id")
        
        if result_file_id_str:
            try:
                task.result_file_id = uuid.UUID(result_file_id_str)
                logger.info(f"Task {self.task_id} result_file_id set to: {result_file_id_str}")
            except ValueError as e:
                logger.error(f"Invalid result_file_id format: {result_file_id_str}, error: {e}")
                raise Exception(f"Invalid result_file_id format: {result_file_id_str}")
        else:
            logger.warning(f"No result_file_id returned for task {self.task_id}")
        
        task.status = "completed"
        task.completed_at = datetime.datetime.utcnow()

    async def _handle_modify_task(self, db: AsyncSession, task: ProcessingTask):
        if not task.content_file_ids:
            raise Exception("No file provided for modification")
        
        file_id = str(task.content_file_ids[0])
        
        result = await self._call_tool("document_modifier", {
            "file_id": file_id,
            "modifications": self.modifications or task.requirements or "请根据需求修改文档",
            **({"ai_model": self.ai_model} if self.ai_model else {})
        })
        
        logger.info(f"Document modifier result: {result}")
        
        # 检查是否有错误
        if result.get("error"):
            raise Exception(f"Document modification failed: {result.get('error')}")
        
        result_file_id_str = result.get("result_file_id")
        
        if result_file_id_str:
            try:
                task.result_file_id = uuid.UUID(result_file_id_str)
                logger.info(f"Task {self.task_id} result_file_id set to: {result_file_id_str}")
            except ValueError as e:
                logger.error(f"Invalid result_file_id format: {result_file_id_str}, error: {e}")
                raise Exception(f"Invalid result_file_id format: {result_file_id_str}")
        else:
            logger.warning(f"No result_file_id returned for task {self.task_id}")
        
        task.status = "completed"
        task.completed_at = datetime.datetime.utcnow()

    async def _call_tool(self, name: str, args: dict):
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.mcp_base_url}/{name}/invoke", json=args)
            resp.raise_for_status()
            return resp.json()

    async def _get_task(self, db: AsyncSession, task_id: str):
        stmt = select(ProcessingTask).where(ProcessingTask.id == uuid.UUID(task_id))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_status(self, db: AsyncSession, status: str):
        stmt = update(ProcessingTask).where(ProcessingTask.id == uuid.UUID(self.task_id)).values(status=status)
        await db.execute(stmt)
        await db.commit()

async def process_task_background(task_id: str, preset_template: str | None = None, modifications: str | None = None, ai_model: str | None = None):
    orchestrator = WorkflowOrchestrator(task_id, preset_template, modifications, ai_model)
    await orchestrator.run()


# ==================== 文档审查处理 ====================

async def process_review_background(review_id: str, ai_model: str | None = None):
    """处理文档审查任务"""
    mcp_base_url = "http://mcp-server:3000/api/tools"
    
    async with SessionLocal() as db:
        stmt = select(DocumentReview).where(DocumentReview.id == uuid.UUID(review_id))
        result = await db.execute(stmt)
        review = result.scalar_one_or_none()
        
        if not review:
            logger.error(f"Review {review_id} not found")
            return
        
        try:
            # 更新状态为处理中
            review.status = "processing"
            await db.commit()
            
            # 调用 MCP 审查工具
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{mcp_base_url}/document_reviewer/invoke",
                    json={
                        "file_id": str(review.document_id),
                        "review_type": review.review_type,
                        "ai_model": ai_model or review.ai_model
                    }
                )
                resp.raise_for_status()
                result_data = resp.json()
            
            # 保存审查结果
            review.annotations = json.dumps(result_data.get("annotations", []), ensure_ascii=False)
            review.summary = result_data.get("summary", "")
            review.risk_level = result_data.get("risk_level", "low")
            review.status = "completed"
            review.completed_at = datetime.datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Review failed: {e}")
            review.status = "failed"
            review.error_message = str(e)
        
        await db.commit()


# ==================== 工作流执行 ====================

async def execute_workflow_background(execution_id: str):
    """执行工作流"""
    mcp_base_url = "http://mcp-server:3000/api/tools"
    
    async with SessionLocal() as db:
        # 获取执行记录
        stmt = select(WorkflowExecution).where(WorkflowExecution.id == uuid.UUID(execution_id))
        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()
        
        if not execution:
            logger.error(f"Execution {execution_id} not found")
            return
        
        # 获取工作流定义
        stmt = select(Workflow).where(Workflow.id == execution.workflow_id)
        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            logger.error(f"Workflow {execution.workflow_id} not found")
            execution.status = "failed"
            execution.error_message = "Workflow not found"
            await db.commit()
            return
        
        try:
            execution.status = "running"
            await db.commit()
            
            nodes = json.loads(workflow.nodes) if workflow.nodes else []
            edges = json.loads(workflow.edges) if workflow.edges else []
            
            # 构建 DAG 执行顺序
            node_order = _build_execution_order(nodes, edges)
            
            node_results = {}
            current_data = {
                "file_ids": [str(fid) for fid in (execution.input_file_ids or [])],
                "content": ""
            }
            
            for node_id in node_order:
                node = next((n for n in nodes if n["id"] == node_id), None)
                if not node:
                    continue
                
                execution.current_node = node_id
                await db.commit()
                
                # 执行节点
                node_result = await _execute_node(node, current_data, mcp_base_url)
                node_results[node_id] = node_result
                
                # 更新当前数据供下个节点使用
                if node_result.get("content"):
                    current_data["content"] = node_result["content"]
                if node_result.get("file_id"):
                    current_data["file_ids"] = [node_result["file_id"]]
                if node_result.get("result_file_id"):
                    current_data["file_ids"] = [node_result["result_file_id"]]
            
            # 保存结果
            execution.node_results = json.dumps(node_results, ensure_ascii=False)
            if current_data.get("file_ids"):
                execution.output_file_id = uuid.UUID(current_data["file_ids"][0])
            execution.status = "completed"
            execution.completed_at = datetime.datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            execution.status = "failed"
            execution.error_message = str(e)
        
        await db.commit()


def _build_execution_order(nodes: list, edges: list) -> list:
    """根据边构建拓扑排序的执行顺序"""
    # 构建邻接表和入度表
    graph = {n["id"]: [] for n in nodes}
    in_degree = {n["id"]: 0 for n in nodes}
    
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source in graph and target in in_degree:
            graph[source].append(target)
            in_degree[target] += 1
    
    # Kahn's algorithm
    queue = [n for n, degree in in_degree.items() if degree == 0]
    order = []
    
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    return order


async def _execute_node(node: dict, input_data: dict, mcp_base_url: str) -> dict:
    """执行单个工作流节点"""
    node_type = node.get("type", "")
    config = node.get("config", {})
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        if node_type == "content_extractor":
            file_id = input_data.get("file_ids", [None])[0]
            if not file_id:
                return {"error": "No file_id provided"}
            resp = await client.post(
                f"{mcp_base_url}/content_extractor/invoke",
                json={"file_id": file_id, "format": config.get("format", "markdown")}
            )
            return resp.json()
        
        elif node_type == "document_analyzer":
            file_id = input_data.get("file_ids", [None])[0]
            if not file_id:
                return {"error": "No file_id provided"}
            resp = await client.post(
                f"{mcp_base_url}/document_analyzer/invoke",
                json={
                    "file_id": file_id, 
                    "analysis_type": config.get("analysis_type", "structure"),
                    "ai_model": config.get("ai_model")
                }
            )
            return resp.json()
        
        elif node_type == "document_reviewer":
            file_id = input_data.get("file_ids", [None])[0]
            if not file_id:
                return {"error": "No file_id provided"}
            resp = await client.post(
                f"{mcp_base_url}/document_reviewer/invoke",
                json={
                    "file_id": file_id,
                    "review_type": config.get("review_type", "general"),
                    "ai_model": config.get("ai_model")
                }
            )
            return resp.json()
        
        elif node_type == "document_generator":
            content = input_data.get("content", "")
            resp = await client.post(
                f"{mcp_base_url}/document_generator/invoke",
                json={
                    "content": content,
                    "template_file_id": config.get("template_file_id", "none"),
                    "output_format": config.get("output_format", "docx"),
                    "preset_template": config.get("preset_template"),
                    "ai_model": config.get("ai_model")
                }
            )
            return resp.json()
        
        elif node_type == "audio_transcriber":
            file_id = input_data.get("file_ids", [None])[0]
            if not file_id:
                return {"error": "No file_id provided"}
            resp = await client.post(
                f"{mcp_base_url}/audio_transcriber/invoke",
                json={
                    "file_id": file_id,
                    "ai_model": config.get("ai_model")
                }
            )
            return resp.json()
        
        elif node_type == "ai_processor":
            # 自定义 AI 处理节点
            content = input_data.get("content", "")
            prompt = config.get("prompt", "请处理以下内容：") + "\n\n" + content
            resp = await client.post(
                f"{mcp_base_url}/ai_processor/invoke",
                json={
                    "prompt": prompt,
                    "ai_model": config.get("ai_model")
                }
            )
            return resp.json()
        
        else:
            return {"error": f"Unknown node type: {node_type}"}


# ==================== 音频转录处理 ====================

async def process_transcription_background(transcription_id: str, generate_minutes: bool = True, ai_model: str | None = None):
    """处理音频转录任务"""
    mcp_base_url = "http://mcp-server:3000/api/tools"
    
    async with SessionLocal() as db:
        stmt = select(AudioTranscription).where(AudioTranscription.id == uuid.UUID(transcription_id))
        result = await db.execute(stmt)
        transcription = result.scalar_one_or_none()
        
        if not transcription:
            logger.error(f"Transcription {transcription_id} not found")
            return
        
        try:
            transcription.status = "processing"
            await db.commit()
            
            # 调用 MCP 音频转录工具
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{mcp_base_url}/audio_transcriber/invoke",
                    json={
                        "file_id": str(transcription.audio_file_id),
                        "generate_minutes": generate_minutes,
                        "ai_model": ai_model or transcription.ai_model
                    }
                )
                resp.raise_for_status()
                result_data = resp.json()
            
            # 保存转录结果
            transcription.transcript = result_data.get("transcript", "")
            if result_data.get("speakers"):
                transcription.speakers = json.dumps(result_data["speakers"], ensure_ascii=False)
            transcription.summary = result_data.get("summary", "")
            if result_data.get("action_items"):
                transcription.action_items = json.dumps(result_data["action_items"], ensure_ascii=False)
            if result_data.get("result_file_id"):
                transcription.result_file_id = uuid.UUID(result_data["result_file_id"])
            
            transcription.status = "completed"
            transcription.completed_at = datetime.datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            transcription.status = "failed"
            transcription.error_message = str(e)
        
        await db.commit()
