"""REST API for Chrome Extension web clipping."""

import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from loguru import logger
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
    is_pdf: bool = Field(default=False, description="是否为 PDF 页面")
    file_name: str = Field(default="", description="用户指定的文件名（仅 PDF 有效）")

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


def _download_pdf(url: str, dest_path: Path) -> bool:
    """下载 PDF 到指定路径，返回是否成功。"""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as exc:
        logger.warning(f"[knowledge_clip] PDF download failed for {url}: {exc}")
        return False


def _file_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""
    import hashlib
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    """使用 pypdf 提取 PDF 文本，失败返回空字符串。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        parts = []
        for i, page in enumerate(reader.pages):
            if max_pages is not None and i >= max_pages:
                break
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning(f"[knowledge_clip] PDF text extraction failed for {pdf_path}: {exc}")
        return ""


async def _extract_pdf_metadata(pdf_path: Path, url: str = "", title_hint: str = "") -> dict[str, Any]:
    """使用 LLM 分析 PDF 第一页，提取文献 metadata。"""
    first_page_text = _extract_pdf_text(pdf_path, max_pages=1)
    if not first_page_text:
        return {}

    prompt = f"""Analyze the first page of an academic PDF and extract metadata.

Title hint: {title_hint or 'N/A'}
Source URL: {url or 'N/A'}

First page text:
---
{first_page_text[:4000]}
---

Return ONLY a valid JSON object with these fields (use empty string or null if unknown):
{{
  "title": "string",
  "authors": ["string"],
  "year": 2024,
  "venue": "string",
  "doi": "string",
  "summary": "One-sentence summary",
  "page_count": null
}}
"""
    try:
        from backend.agent.config_service import AgentConfigService
        from backend.data.database import Database
        config_service = AgentConfigService(Database())
        provider, model_id, _, max_tokens, temperature = config_service.get_default_provider_and_model()

        messages = [
            {"role": "system", "content": "You are a precise academic metadata extractor. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]
        response = await provider.chat(
            messages=messages,
            model=model_id,
            max_tokens=max_tokens,
            temperature=0.1,
        )
        content = response.content or ""
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (``` or ```json)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning(f"[knowledge_clip] Failed to extract PDF metadata via LLM: {exc}")
    return {}


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

    # ── PDF 统一处理：直接下载保存，不生成 web_clips ──
    if request.is_pdf:
        pdf_slug = _sanitize_filename(request.file_name or request.title or urlparse(request.url).netloc or "untitled")
        pdf_filename = f"{timestamp}_{pdf_slug}.pdf"
        pdf_path_relative = f"knowledge/raw/pdf_clips/{pdf_filename}"
        pdf_full_path = Path(workspace) / pdf_path_relative

        download_ok = _download_pdf(request.url, pdf_full_path)
        if not download_ok:
            raise HTTPException(status_code=502, detail="PDF 下载失败，请检查链接是否可访问")

        # 计算 SHA256 并提取/复用 metadata
        pdf_sha256 = _file_sha256(pdf_full_path)
        existing_meta = engine.get_document_meta(pdf_sha256)

        if existing_meta:
            meta = existing_meta
        else:
            meta = await _extract_pdf_metadata(pdf_full_path, url=request.url, title_hint=request.title)
            from pypdf import PdfReader
            try:
                page_count = len(PdfReader(str(pdf_full_path)).pages)
            except Exception:
                page_count = None
            meta["page_count"] = meta.get("page_count") or page_count
            meta["url"] = meta.get("url") or request.url
            meta["source_type"] = "pdf"
            engine.upsert_document_meta(
                pdf_sha256,
                {
                    "source_type": "pdf",
                    "title": meta.get("title") or request.title or pdf_slug,
                    "authors": meta.get("authors"),
                    "year": meta.get("year"),
                    "venue": meta.get("venue"),
                    "doi": meta.get("doi"),
                    "url": meta.get("url") or request.url,
                    "summary": meta.get("summary"),
                    "page_count": meta.get("page_count"),
                },
            )

        pdf_title = meta.get("title") or request.title or pdf_slug
        safe_title = _sanitize_filename(pdf_title)

        # 提取文本并写入一个专用 md，用于后续蒸馏
        pdf_text = _extract_pdf_text(pdf_full_path)
        extracted_filename = f"{timestamp}_{safe_title}_extracted.md"
        extracted_path_relative = f"knowledge/raw/pdf_clips/{extracted_filename}"

        fm_data = {
            "source": request.url,
            "title": pdf_title,
            "document_type": "pdf_clip",
            "pdf_path": pdf_path_relative,
            "clipped_at": datetime.now().isoformat(),
            "tags": request.tags,
            "extracted_by": "chrome_extension",
        }
        if request.user_note:
            fm_data["user_note"] = request.user_note

        if pdf_text:
            body = pdf_text
        else:
            body = (
                f"> 📄 PDF 已下载到 `{pdf_path_relative}`\n"
                f"> 源地址：[{request.title or request.url}]({request.url})\n"
            )

        full_content = _build_frontmatter(fm_data) + body
        engine.write_note(extracted_path_relative, full_content)

        # 可选：自动蒸馏
        task_id = None
        if request.action == "clip_and_distill":
            queue = _get_queue()
            output_path = f"knowledge/notes/pdf_clips/{timestamp}_{safe_title}_distilled.md"
            task_id = queue.enqueue(
                request_id=f"clip_pdf_{timestamp}_{safe_title}",
                source_path=extracted_path_relative,
                prompt="请将这篇 PDF 内容提炼成结构化的知识笔记。保留核心观点、关键代码和重要链接。",
                output_path=output_path,
                template="custom",
            )
            # 记录 source->note 映射到 metadata 表
            engine.upsert_document_meta(
                pdf_sha256,
                {
                    "source_type": "pdf",
                    "title": pdf_title,
                    "authors": meta.get("authors"),
                    "year": meta.get("year"),
                    "venue": meta.get("venue"),
                    "doi": meta.get("doi"),
                    "url": meta.get("url") or request.url,
                    "summary": meta.get("summary"),
                    "page_count": meta.get("page_count"),
                    "metadata_json": {"latest_distill_output": output_path},
                },
            )

        message = "PDF 已下载并保存到 Documents"
        if task_id:
            message += "，正在提取知识到 Notes"

        return {
            "success": True,
            "saved_path": pdf_path_relative,
            "task_id": task_id,
            "message": message,
            "metadata": {
                "sha256": pdf_sha256,
                "title": meta.get("title"),
                "authors": meta.get("authors"),
                "year": meta.get("year"),
                "venue": meta.get("venue"),
                "summary": meta.get("summary"),
            },
        }

    # ───────────────────────────────────────────────────────────────
    # Action: note（直接写 Documents / raw，作为随笔不进入知识图谱）
    # ───────────────────────────────────────────────────────────────
    if request.action == "note":
        note_path = f"knowledge/raw/quick_notes/{filename}"

        fm_data = {
            "source": request.url,
            "title": request.title or slug,
            "document_type": "quick_note",
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
        # 随笔不进入知识图谱，因此不调用 update_note 建立索引

        return {
            "success": True,
            "saved_path": note_path,
            "task_id": None,
            "message": "已保存到 Documents",
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
