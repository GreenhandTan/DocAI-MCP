from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from zhipuai import ZhipuAI
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import json
import httpx
import os
import asyncio
import io
import re

mcp = FastMCP("docai-mcp")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api/v1")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "glm-4.5-air")

class AIClient:
    def __init__(self):
        self.client = None
        if AI_API_KEY and "此处" not in AI_API_KEY:
            self.client = ZhipuAI(api_key=AI_API_KEY)
        self.model = AI_MODEL_NAME
        
    def generate_completion(self, prompt: str):
        if not self.client:
            return f"Mock AI Response (Key Missing): {prompt[:50]}..."
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI Error: {e}")
            return f"AI Error: {str(e)}"

ai_client = AIClient()

async def download_file_from_backend(file_id: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{BACKEND_URL}/files/{file_id}/download")
            if resp.status_code == 200:
                return resp.content
    except Exception as e:
        print(f"Failed to download file {file_id}: {e}")
    return None

async def upload_generated_document(file_content: bytes, filename: str) -> str:
    """上传生成的文档到后端，失败时抛出异常"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {'file': (filename, io.BytesIO(file_content), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
            resp = await client.post(f"{BACKEND_URL}/files/upload", files=files)
            
            if resp.status_code == 200:
                file_id = resp.json().get('fileId')
                if file_id:
                    print(f"Successfully uploaded document: {filename} -> {file_id}")
                    return file_id
                else:
                    raise Exception(f"Upload succeeded but no fileId returned: {resp.json()}")
            else:
                raise Exception(f"Upload failed with status {resp.status_code}: {resp.text}")
    except httpx.TimeoutException:
        raise Exception(f"Upload timeout for {filename}")
    except httpx.RequestError as e:
        raise Exception(f"Network error uploading {filename}: {str(e)}")
    except Exception as e:
        print(f"Failed to upload generated document: {e}")
        raise

def set_chinese_font(run, font_name='微软雅黑', size=12, bold=False, color=None):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color

def parse_ai_content_for_template(content: str, template_type: str) -> dict:
    """使用AI解析内容并提取结构化数据用于填充模板"""
    template_prompts = {
        'resume': """请从以下内容中提取简历信息，以JSON格式返回：
{
    "title": "个人简历",
    "personal_info": {"姓名": "", "电话": "", "邮箱": "", "地址": ""},
    "education": [{"学校": "", "专业": "", "学历": "", "时间": ""}],
    "work_experience": [{"公司": "", "职位": "", "时间": "", "职责": ""}],
    "skills": ["技能1", "技能2"],
    "self_evaluation": "自我评价内容"
}
如果某些信息不存在，请根据内容合理推断或留空。

原始内容：
""",
        'report': """请从以下内容中提取报告信息，以JSON格式返回：
{
    "title": "报告标题",
    "sections": {
        "项目概述": "内容",
        "项目目标": "内容",
        "实施过程": "内容",
        "主要成果": "内容",
        "存在问题": "内容",
        "改进建议": "内容",
        "总结": "内容"
    }
}
请根据原始内容填充各部分，如内容不足可合理扩展。

原始内容：
""",
        'meeting': """请从以下内容中提取会议纪要信息，以JSON格式返回：
{
    "title": "会议纪要",
    "meeting_time": "会议时间",
    "meeting_place": "会议地点",
    "attendees": "参会人员",
    "topics": "会议议题",
    "discussion": "讨论内容",
    "decisions": "决议事项",
    "actions": "后续行动"
}
请根据原始内容填充，如内容不足可合理推断。

原始内容：
""",
        'contract': """请从以下内容中提取合同信息，以JSON格式返回：
{
    "title": "合同协议",
    "party_a": {"名称": "", "地址": "", "联系人": "", "电话": ""},
    "party_b": {"名称": "", "地址": "", "联系人": "", "电话": ""},
    "content": "合同具体条款",
    "period": {"开始时间": "", "结束时间": ""},
    "payment": "付款条款",
    "breach": "违约责任",
    "dispute": "争议解决方式"
}
请根据原始内容填充。

原始内容：
""",
        'proposal': """请从以下内容中提取项目提案信息，以JSON格式返回：
{
    "title": "项目提案标题",
    "sections": {
        "项目背景": "内容",
        "项目目标": "内容",
        "项目内容": "内容",
        "实施方案": "内容",
        "时间计划": "内容",
        "预算说明": "内容",
        "预期成果": "内容",
        "风险评估": "内容"
    }
}
请根据原始内容填充。

原始内容：
"""
    }
    
    prompt = template_prompts.get(template_type, "")
    if not prompt:
        return {"raw_content": content}
    
    full_prompt = prompt + content
    ai_response = ai_client.generate_completion(full_prompt)
    
    try:
        # 提取JSON
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0].strip()
        return json.loads(ai_response)
    except json.JSONDecodeError:
        print(f"Failed to parse AI response as JSON: {ai_response[:200]}")
        return {"raw_content": content}

def create_document_from_content(content: str, template_type: str = 'default') -> bytes:
    """根据内容和模板类型创建文档，使用AI解析内容填充模板"""
    doc = Document()
    
    # 如果有实际内容，使用AI解析并填充
    if content and content.strip() and template_type != 'default':
        parsed_data = parse_ai_content_for_template(content, template_type)
        
        if template_type == 'resume':
            title = parsed_data.get('title', '个人简历')
            doc.add_heading(title, 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            
            # 个人信息
            doc.add_heading('个人信息', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            personal_info = parsed_data.get('personal_info', {})
            for key in ['姓名', '电话', '邮箱', '地址']:
                p = doc.add_paragraph()
                p.add_run(f'{key}：')
                set_chinese_font(p.runs[-1], bold=True)
                value = personal_info.get(key, '') or ''
                p.add_run(value if value else '[待填写]')
                set_chinese_font(p.runs[-1])
            doc.add_paragraph()
            
            # 教育背景
            doc.add_heading('教育背景', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            education_list = parsed_data.get('education', [])
            if education_list:
                for edu in education_list:
                    for key in ['学校', '专业', '学历', '时间']:
                        p = doc.add_paragraph()
                        p.add_run(f'{key}：')
                        set_chinese_font(p.runs[-1], bold=True)
                        value = edu.get(key, '') or ''
                        p.add_run(value if value else '[待填写]')
                        set_chinese_font(p.runs[-1])
                    doc.add_paragraph()
            else:
                p = doc.add_paragraph('[待填写教育背景]')
                set_chinese_font(p.runs[-1])
            
            # 工作经历
            doc.add_heading('工作经历', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            work_list = parsed_data.get('work_experience', [])
            if work_list:
                for work in work_list:
                    for key in ['公司', '职位', '时间', '职责']:
                        p = doc.add_paragraph()
                        p.add_run(f'{key}：')
                        set_chinese_font(p.runs[-1], bold=True)
                        value = work.get(key, '') or ''
                        p.add_run(value if value else '[待填写]')
                        set_chinese_font(p.runs[-1])
                    doc.add_paragraph()
            else:
                p = doc.add_paragraph('[待填写工作经历]')
                set_chinese_font(p.runs[-1])
            
            # 技能特长
            doc.add_heading('技能特长', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            skills = parsed_data.get('skills', [])
            if skills:
                p = doc.add_paragraph('• ' + '\n• '.join(skills))
                set_chinese_font(p.runs[-1])
            else:
                p = doc.add_paragraph('[待填写技能]')
                set_chinese_font(p.runs[-1])
            doc.add_paragraph()
            
            # 自我评价
            doc.add_heading('自我评价', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            self_eval = parsed_data.get('self_evaluation', '')
            p = doc.add_paragraph(self_eval if self_eval else '[待填写自我评价]')
            set_chinese_font(p.runs[-1])
        
        elif template_type == 'report':
            title = parsed_data.get('title', '项目报告')
            doc.add_heading(title, 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            
            sections = parsed_data.get('sections', {})
            section_order = ['项目概述', '项目目标', '实施过程', '主要成果', '存在问题', '改进建议', '总结']
            
            for section_name in section_order:
                doc.add_heading(section_name, level=1)
                set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
                section_content = sections.get(section_name, '')
                p = doc.add_paragraph(section_content if section_content else '[待填写内容]')
                set_chinese_font(p.runs[-1])
        
        elif template_type == 'meeting':
            title = parsed_data.get('title', '会议纪要')
            doc.add_heading(title, 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            
            # 基本信息
            for key, field in [('会议时间', 'meeting_time'), ('会议地点', 'meeting_place'), ('参会人员', 'attendees')]:
                p = doc.add_paragraph()
                p.add_run(f'{key}：')
                set_chinese_font(p.runs[-1], bold=True)
                value = parsed_data.get(field, '')
                p.add_run(value if value else '[待填写]')
                set_chinese_font(p.runs[-1])
            
            # 各部分内容
            for section_name, field in [('会议议题', 'topics'), ('讨论内容', 'discussion'), ('决议事项', 'decisions'), ('后续行动', 'actions')]:
                doc.add_heading(section_name, level=1)
                set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
                section_content = parsed_data.get(field, '')
                p = doc.add_paragraph(section_content if section_content else '[待填写]')
                set_chinese_font(p.runs[-1])
        
        elif template_type == 'contract':
            title = parsed_data.get('title', '合同协议')
            doc.add_heading(title, 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            
            # 甲方信息
            doc.add_heading('甲方信息', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            party_a = parsed_data.get('party_a', {})
            for key in ['名称', '地址', '联系人', '电话']:
                p = doc.add_paragraph()
                p.add_run(f'{key}：')
                set_chinese_font(p.runs[-1], bold=True)
                value = party_a.get(key, '')
                p.add_run(value if value else '[待填写]')
                set_chinese_font(p.runs[-1])
            doc.add_paragraph()
            
            # 乙方信息
            doc.add_heading('乙方信息', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            party_b = parsed_data.get('party_b', {})
            for key in ['名称', '地址', '联系人', '电话']:
                p = doc.add_paragraph()
                p.add_run(f'{key}：')
                set_chinese_font(p.runs[-1], bold=True)
                value = party_b.get(key, '')
                p.add_run(value if value else '[待填写]')
                set_chinese_font(p.runs[-1])
            doc.add_paragraph()
            
            # 其他部分
            for section_name, field in [('合同内容', 'content'), ('付款方式', 'payment'), ('违约责任', 'breach'), ('争议解决', 'dispute')]:
                doc.add_heading(section_name, level=1)
                set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
                section_content = parsed_data.get(field, '')
                p = doc.add_paragraph(section_content if section_content else '[待填写]')
                set_chinese_font(p.runs[-1])
            
            # 合同期限
            doc.add_heading('合同期限', level=1)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
            period = parsed_data.get('period', {})
            for key in ['开始时间', '结束时间']:
                p = doc.add_paragraph()
                p.add_run(f'{key}：')
                set_chinese_font(p.runs[-1], bold=True)
                value = period.get(key, '')
                p.add_run(value if value else '[待填写]')
                set_chinese_font(p.runs[-1])
        
        elif template_type == 'proposal':
            title = parsed_data.get('title', '项目提案')
            doc.add_heading(title, 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            
            sections = parsed_data.get('sections', {})
            section_order = ['项目背景', '项目目标', '项目内容', '实施方案', '时间计划', '预算说明', '预期成果', '风险评估']
            
            for section_name in section_order:
                doc.add_heading(section_name, level=1)
                set_chinese_font(doc.paragraphs[-1].runs[0], size=14, bold=True)
                section_content = sections.get(section_name, '')
                p = doc.add_paragraph(section_content if section_content else '[待填写内容]')
                set_chinese_font(p.runs[-1])
        
        else:
            # 如果有raw_content，直接输出
            raw = parsed_data.get('raw_content', content)
            doc.add_heading('文档', 0)
            set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
            p = doc.add_paragraph(raw)
            set_chinese_font(p.runs[-1])
    
    elif template_type == 'invoice':
        # 发票模板保持原样，需要用户手动填写
        doc.add_heading('发票', 0)
        set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
        
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        headers = ['商品/服务名称', '数量', '单价', '金额']
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            set_chinese_font(hdr_cells[i].paragraphs[0].runs[0], bold=True)
        
        for _ in range(3):
            row_cells = table.add_row().cells
            for i in range(4):
                row_cells[i].text = '[待填写]'
                set_chinese_font(row_cells[i].paragraphs[0].runs[0])
        
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.add_run('合计金额：')
        set_chinese_font(p.runs[-1], bold=True)
        p.add_run('[待填写]')
        
        p = doc.add_paragraph()
        p.add_run('开票日期：')
        set_chinese_font(p.runs[-1], bold=True)
        p.add_run('[待填写]')
    
    else:
        # default类型：直接输出内容
        doc.add_heading('文档', 0)
        set_chinese_font(doc.paragraphs[-1].runs[0], size=18, bold=True)
        
        if content and content.strip():
            # 将内容按段落分割并添加
            paragraphs = content.split('\n\n')
            for para_text in paragraphs:
                if para_text.strip():
                    # 检查是否是标题行
                    if para_text.startswith('#'):
                        # Markdown标题处理
                        level = len(para_text.split()[0].replace('#', '')) if para_text.startswith('#') else 1
                        level = min(level, 3)
                        title_text = para_text.lstrip('#').strip()
                        doc.add_heading(title_text, level=level)
                        if doc.paragraphs[-1].runs:
                            set_chinese_font(doc.paragraphs[-1].runs[0], size=14 - level, bold=True)
                    else:
                        p = doc.add_paragraph(para_text.strip())
                        set_chinese_font(p.runs[-1])
        else:
            p = doc.add_paragraph('[待填写内容]')
            set_chinese_font(p.runs[-1])
    
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()

def modify_document_with_content(original_content: bytes, modifications: str) -> bytes:
    try:
        doc = Document(io.BytesIO(original_content))
        
        prompt = f"""
        根据以下修改要求，对文档进行修改。请以结构化的方式返回修改指令：
        
        修改要求：{modifications}
        
        请以JSON格式返回修改内容，格式如下：
        {{
            "title": "新标题（如需修改）",
            "add_paragraphs": ["段落1内容", "段落2内容"],
            "replace_sections": {{"原文本": "新文本"}},
            "format_changes": {{"font_size": 12, "bold": true}}
        }}
        """
        
        ai_response = ai_client.generate_completion(prompt)
        
        try:
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0].strip()
            
            changes = json.loads(ai_response)
            
            if changes.get("title"):
                if doc.paragraphs:
                    doc.paragraphs[0].text = changes["title"]
                    set_chinese_font(doc.paragraphs[0].runs[0], size=18, bold=True)
            
            for para_text in changes.get("add_paragraphs", []):
                p = doc.add_paragraph(para_text)
                set_chinese_font(p.runs[-1])
            
            for old_text, new_text in changes.get("replace_sections", {}).items():
                for para in doc.paragraphs:
                    if old_text in para.text:
                        para.text = para.text.replace(old_text, new_text)
                        set_chinese_font(para.runs[0])
            
        except json.JSONDecodeError:
            p = doc.add_paragraph()
            p.add_run("AI 修改建议：")
            set_chinese_font(p.runs[-1], bold=True)
            p.add_run(ai_response)
            set_chinese_font(p.runs[-1])
        
        output = io.BytesIO()
        doc.save(output)
        return output.getvalue()
        
    except Exception as e:
        print(f"Error modifying document: {e}")
        return original_content

async def _analyze_document_logic(file_id: str, analysis_type: str):
    file_content = await download_file_from_backend(file_id)
    
    if not file_content:
        return {"error": "Failed to download document"}
    
    prompt = f"""
    请分析文档（ID: {file_id}）。
    分析类型：{analysis_type}
    
    如果分析类型是 'structure'，返回包含章节和层级的 JSON。
    如果分析类型是 'style'，返回包含字体、颜色、间距的 JSON。
    如果分析类型是 'content'，返回摘要。
    
    请以 JSON 格式返回结果。
    """
    
    ai_response = ai_client.generate_completion(prompt)
    
    try:
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0].strip()
        return json.loads(ai_response)
    except:
        return {"raw_analysis": ai_response}

async def _extract_content_logic(file_id: str, format: str):
    file_content = await download_file_from_backend(file_id)
    
    if not file_content:
        return f"无法提取内容：文档 {file_id} 下载失败"
    
    try:
        doc = Document(io.BytesIO(file_content))
        content = []
        for para in doc.paragraphs:
            if para.text.strip():
                content.append(para.text.strip())
        
        if format == "markdown":
            return "\n\n".join([f"{p}" for p in content])
        elif format == "plain":
            return "\n".join(content)
        else:
            return "\n\n".join(content)
    except Exception as e:
        return f"提取内容失败：{str(e)}"

async def _match_template_logic(content_file_ids: list[str], template_file_id: str, keep_styles: bool):
    prompt = f"""
    我有内容文件：{content_file_ids}
    和模板文件：{template_file_id}
    要求：将内容合并到模板中。保留样式：{keep_styles}。
    
    请提供合并策略计划，以 JSON 格式返回。
    """
    
    ai_response = ai_client.generate_completion(prompt)
    try:
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        return json.loads(ai_response)
    except:
        return {"plan": ai_response}

async def _generate_document_logic(content: str, template_file_id: str, output_format: str, preset_template: str | None = None) -> dict:
    template_type = 'default'
    
    if preset_template:
        preset_lower = preset_template.lower()
        if 'resume' in preset_lower or '简历' in preset_template:
            template_type = 'resume'
        elif 'report' in preset_lower or '报告' in preset_template:
            template_type = 'report'
        elif 'contract' in preset_lower or '合同' in preset_template:
            template_type = 'contract'
        elif 'meeting' in preset_lower or '会议' in preset_template:
            template_type = 'meeting'
        elif 'proposal' in preset_lower or '提案' in preset_template:
            template_type = 'proposal'
        elif 'invoice' in preset_lower or '发票' in preset_template:
            template_type = 'invoice'
    
    print(f"Generating document: template_type={template_type}, content_length={len(content) if content else 0}")
    
    try:
        doc_content = create_document_from_content(content, template_type)
        
        import time
        timestamp = int(time.time())
        filename = f"generated-{template_type}-{timestamp}.docx"
        file_id = await upload_generated_document(doc_content, filename)
        
        return {"result_file_id": file_id, "filename": filename, "template_type": template_type}
    except Exception as e:
        error_msg = f"Failed to generate/upload document: {str(e)}"
        print(error_msg)
        return {"error": error_msg}

async def _modify_document_logic(file_id: str, modifications: str) -> dict:
    file_content = await download_file_from_backend(file_id)
    
    if not file_content:
        return {"error": "Failed to download document for modification"}
    
    try:
        modified_content = modify_document_with_content(file_content, modifications)
        
        import time
        timestamp = int(time.time())
        filename = f"modified-{timestamp}.docx"
        new_file_id = await upload_generated_document(modified_content, filename)
        
        return {"result_file_id": new_file_id, "filename": filename}
    except Exception as e:
        error_msg = f"Failed to modify/upload document: {str(e)}"
        print(error_msg)
        return {"error": error_msg}

@mcp.tool()
async def document_analyzer(file_id: str, analysis_type: str = "structure") -> str:
    """分析文档结构、内容类型或样式。"""
    result = await _analyze_document_logic(file_id, analysis_type)
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
async def content_extractor(file_id: str, format: str = "markdown") -> str:
    """以指定格式从文档中提取内容。"""
    result = await _extract_content_logic(file_id, format)
    return result

@mcp.tool()
async def template_matcher(content_file_ids: list[str], template_file_id: str, keep_styles: bool = True) -> str:
    """将内容与模板匹配并生成布局计划。"""
    result = await _match_template_logic(content_file_ids, template_file_id, keep_styles)
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
async def document_generator(content: str, template_file_id: str, output_format: str = "docx", preset_template: str | None = None) -> str:
    """生成最终文档。"""
    result = await _generate_document_logic(content, template_file_id, output_format, preset_template)
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
async def document_modifier(file_id: str, modifications: str) -> str:
    """根据修改要求修改现有文档。"""
    result = await _modify_document_logic(file_id, modifications)
    return json.dumps(result, indent=2, ensure_ascii=False)

from fastapi import FastAPI
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

app = FastAPI()
mcp_server = Server("docai-mcp")

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="document_analyzer", description="分析文档结构、内容或样式", inputSchema={
            "type": "object", 
            "properties": {
                "file_id": {"type": "string"}, 
                "analysis_type": {"type": "string", "enum": ["structure", "style", "content"]}
            }
        }),
        Tool(name="content_extractor", description="提取文档内容", inputSchema={
            "type": "object", 
            "properties": {
                "file_id": {"type": "string"}, 
                "format": {"type": "string", "enum": ["markdown", "plain"]}
            }
        }),
        Tool(name="template_matcher", description="匹配模板并生成布局计划", inputSchema={
            "type": "object", 
            "properties": {
                "content_file_ids": {"type": "array", "items": {"type": "string"}}, 
                "template_file_id": {"type": "string"},
                "keep_styles": {"type": "boolean"}
            }
        }),
        Tool(name="document_generator", description="生成文档", inputSchema={
            "type": "object", 
            "properties": {
                "content": {"type": "string"}, 
                "template_file_id": {"type": "string"},
                "output_format": {"type": "string"},
                "preset_template": {"type": "string"}
            }
        }),
        Tool(name="document_modifier", description="修改现有文档", inputSchema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
                "modifications": {"type": "string"}
            }
        }),
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "document_analyzer":
        res = await _analyze_document_logic(arguments["file_id"], arguments.get("analysis_type", "structure"))
        return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
    elif name == "content_extractor":
        res = await _extract_content_logic(arguments["file_id"], arguments.get("format", "markdown"))
        return [TextContent(type="text", text=res)]
    elif name == "template_matcher":
        res = await _match_template_logic(arguments["content_file_ids"], arguments["template_file_id"], arguments.get("keep_styles", True))
        return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
    elif name == "document_generator":
        res = await _generate_document_logic(arguments["content"], arguments["template_file_id"], arguments.get("output_format", "docx"), arguments.get("preset_template"))
        return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
    elif name == "document_modifier":
        res = await _modify_document_logic(arguments["file_id"], arguments["modifications"])
        return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
    return []

@app.post("/api/tools/{name}/invoke")
async def invoke_tool(name: str, arguments: dict):
    if name == "document_analyzer":
        return await _analyze_document_logic(arguments["file_id"], arguments.get("analysis_type", "structure"))
    elif name == "content_extractor":
        return {"content": await _extract_content_logic(arguments["file_id"], arguments.get("format", "markdown"))}
    elif name == "template_matcher":
        return await _match_template_logic(arguments["content_file_ids"], arguments["template_file_id"], arguments.get("keep_styles", True))
    elif name == "document_generator":
        return await _generate_document_logic(arguments["content"], arguments["template_file_id"], arguments.get("output_format", "docx"), arguments.get("preset_template"))
    elif name == "document_modifier":
        return await _modify_document_logic(arguments["file_id"], arguments["modifications"])
    raise HTTPException(status_code=404, detail="Tool not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
