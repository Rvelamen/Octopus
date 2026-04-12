"""REST API for Chrome Extension web clipping."""

import re
import yaml
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.services.knowledge_task_queue import KnowledgeTaskQueue
from backend.utils.helpers import get_workspace_path

router = APIRouter(prefix="/api/knowledge")


class ClipRequest(BaseModel):
    url: str = Field(..., description="原始网页 URL")
    title: str = Field(default="", description="页面标题")
    content: str = Field(default="", description="插件提取的 markdown / 纯文本正文")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    user_note: str = Field(default="", description="用户备注 / 感想")
    action: str = Field(default="clip", description="clip | clip_and_distill | note")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("clip", "clip_and_distill", "note"):
            raise ValueError("action must be one of: clip, clip_and_distill, note")
        return v


def _sanitize_filename(name: str) -> str:
    """将标题/主机名转换为安全的文件名字符串。"""
    name = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', name)
    return name[:60] or "untitled"


def _build_frontmatter(data: dict) -> str:
    """将 dict 序列化为 YAML frontmatter。"""
    yaml_body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{yaml_body}---\n"


def _get_queue() -> KnowledgeTaskQueue:
    """获取当前 workspace 的 KnowledgeTaskQueue 实例。"""
    workspace_root = str(get_workspace_path())
    task_queue_db = Path(workspace_root) / "knowledge" / ".distill_tasks.db"
    return KnowledgeTaskQueue(task_queue_db)


@router.post("/clip")
async def knowledge_clip(request: ClipRequest):
    """
    Chrome Extension 网页剪藏入口。

    - action=clip:            保存到 knowledge/raw/web_clips/，不蒸馏
    - action=clip_and_distill: 保存到 raw，并自动 enqueue 蒸馏任务到 notes
    - action=note:            直接保存到 knowledge/notes/quick_notes/
    """
    workspace = str(get_workspace_path())
    engine = KnowledgeGraphEngine(workspace)

    slug = _sanitize_filename(request.title or urlparse(request.url).netloc)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{slug}.md"

    # ───────────────────────────────────────────────────────────────
    # Action: note（直接写 Notes）
    # ───────────────────────────────────────────────────────────────
    if request.action == "note":
        note_path = f"knowledge/notes/quick_notes/{filename}"

        fm_data = {
            "source": request.url,
            "title": request.title or slug,
            "created_at": datetime.now().isoformat(),
            "tags": request.tags,
            "extracted_by": "chrome_extension",
        }

        body_parts = []
        if request.user_note:
            body_parts.append(f"> 💭 {request.user_note}\n")
        if request.content.strip():
            body_parts.append(request.content)
        else:
            body_parts.append(f"> 源地址：{request.url}")

        full_content = _build_frontmatter(fm_data) + "\n".join(body_parts)
        engine.write_note(note_path, full_content)
        engine.update_note(note_path)

        return {
            "success": True,
            "saved_path": note_path,
            "task_id": None,
            "message": "已保存到 Notes",
        }

    # ───────────────────────────────────────────────────────────────
    # Action: clip / clip_and_distill（写 Documents / raw）
    # ───────────────────────────────────────────────────────────────
    raw_path = f"knowledge/raw/web_clips/{filename}"

    fm_data = {
        "source": request.url,
        "title": request.title or slug,
        "document_type": "web_clip",
        "clipped_at": datetime.now().isoformat(),
        "tags": request.tags,
        "extracted_by": "chrome_extension",
    }
    if request.user_note:
        fm_data["user_note"] = request.user_note

    # 正文组装
    body = request.content.strip()
    if not body or len(body) < 50:
        # 内容为空或太短，生成 stub
        body = (
            f"> 📄 当前页面内容较短或为非文本类型\n"
            f"> 源地址：[{request.title or request.url}]({request.url})\n"
        )

    full_content = _build_frontmatter(fm_data) + body
    engine.write_note(raw_path, full_content)

    # 可选：自动蒸馏
    task_id = None
    if request.action == "clip_and_distill":
        queue = _get_queue()
        output_path = f"knowledge/notes/web_clips/{timestamp}_{slug}_distilled.md"
        task_id = queue.enqueue(
            request_id=f"clip_{timestamp}_{slug}",
            source_path=raw_path,
            prompt="请将这篇网页内容提炼成结构化的知识笔记。保留核心观点、关键代码和重要链接。",
            output_path=output_path,
            template="custom",
        )

    message = "已收藏到 Documents"
    if task_id:
        message += "，正在提取知识到 Notes"

    return {
        "success": True,
        "saved_path": raw_path,
        "task_id": task_id,
        "message": message,
    }
