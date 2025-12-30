import httpx
import json
import logging
from app.core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import ProcessingTask, Document
from app.database import SessionLocal
import uuid
import datetime

settings = get_settings()
logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    def __init__(self, task_id: str, preset_template: str | None = None, modifications: str | None = None):
        self.task_id = task_id
        self.mcp_base_url = "http://mcp-server:3000/api/tools"
        self.preset_template = preset_template
        self.modifications = modifications
        
    async def run(self):
        async with SessionLocal() as db:
            task = await self._get_task(db, self.task_id)
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

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
                "analysis_type": "style"
            })
        else:
            template_style = {}
        
        plan = await self._call_tool("template_matcher", {
            "content_file_ids": [str(f) for f in task.content_file_ids], 
            "template_file_id": str(task.template_file_id) if task.template_file_id else "none",
            "keep_styles": True
        })
        
        result = await self._call_tool("document_generator", {
            "content": full_content,
            "template_file_id": str(task.template_file_id) if task.template_file_id else "none",
            "output_format": "docx",
            "preset_template": self.preset_template
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
            "modifications": self.modifications or task.requirements or "请根据需求修改文档"
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

async def process_task_background(task_id: str, preset_template: str | None = None, modifications: str | None = None):
    orchestrator = WorkflowOrchestrator(task_id, preset_template, modifications)
    await orchestrator.run()
