"""Background worker that consumes the knowledge distillation task queue.

Uses SubagentManager to execute distillation tasks with role-based agents
that have access to tools (read, write, kb_search, etc.).
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.bus import MessageBus
from backend.core.events.types import AgentEvent
from backend.services.knowledge_task_queue import KnowledgeTaskQueue, DistillTask
from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.utils.helpers import get_workspace_path


class KnowledgeTaskWorker:
    """Polls SQLite queue and runs distill jobs via SubagentManager, broadcasting progress via MessageBus."""

    def __init__(
        self,
        queue: KnowledgeTaskQueue,
        bus: MessageBus,
        engine: KnowledgeGraphEngine,
        workspace_root: Path,
        subagent_manager,  # SubagentManager instance
        poll_interval: float = 2.0,
    ):
        self.queue = queue
        self.bus = bus
        self.engine = engine
        self._workspace_root = Path(workspace_root)
        self.subagents = subagent_manager
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._concurrency_limit = asyncio.Semaphore(2)

    def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("KnowledgeTaskWorker started")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                task = self.queue.dequeue_for_run()
                if task:
                    asyncio.create_task(self._run_task(task))
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"KnowledgeTaskWorker loop error: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _run_task(self, task: DistillTask) -> None:
        async with self._concurrency_limit:
            logger.info(f"Running distill task {task.request_id}")

            # 动态获取当前 workspace_root
            try:
                current_workspace = get_workspace_path()
            except Exception as e:
                logger.warning(f"Failed to get workspace path, using fallback: {e}")
                current_workspace = self._workspace_root

            # 检查是否是 preview 任务（output_path 为 None）
            is_preview = task.output_path is None

            # 构建蒸馏任务描述
            template_instructions = ""
            if task.template and task.template != "custom":
                template_instructions = f"\nTemplate: {task.template}\nFollow the template guidelines for {task.template}."

            output_instruction = ""
            if task.output_path:
                output_instruction = f"\n\nOutput path: Save the extracted note to: `{task.output_path}`"
            else:
                output_instruction = "\n\n**Preview mode**: Do NOT write to a file. Instead, return the extracted Markdown content in your final response, starting with the exact raw Markdown you would have written."

            distill_task_desc = f"""You are tasked with distilling a document into a structured Markdown note.

**Source document**: `{task.source_path}`

**User request**: {task.prompt}
{template_instructions}
{output_instruction}

## Instructions
1. Use the `read` tool to read the source document
2. Analyse the content and extract key information based on the user's request
3. Optionally use `kb_search` to find related notes in the knowledge base
4. {'Use the `write` tool to save the extracted note as Markdown' if task.output_path else 'Return the extracted Markdown in your final response (do NOT write to a file)'}
   - Include YAML front-matter with source, extracted_at, and extraction_prompt
   - Use proper Markdown headings, lists, and tables
   - Add wiki-style links like [[Related Concept]] where appropriate
5. When done, report the output path (or the raw Markdown for preview) in your final response

Be concise but complete. If information is not found in the document, state it explicitly.
""".strip()

            async def on_progress(
                req_id: str,
                stage: str,
                msg: str,
                progress: float,
                extra: dict | None = None,
            ) -> None:
                self.queue.update_status(
                    task.id,
                    stage=stage,
                    message=msg,
                    progress=progress,
                )
                data = {
                    "request_id": req_id,
                    "stage": stage,
                    "message": msg,
                    "progress": progress,
                }
                if extra:
                    data.update(extra)
                await self._broadcast_progress(data)

            # 初始化 extra_data，避免 preview 模式分支中未定义
            extra_data: dict = {}

            try:
                await on_progress(
                    task.request_id, "running", "Starting subagent...", 0.05
                )

                # 调用 subagent（同步模式，等待完成）
                task_id, future = await self.subagents.spawn_sync_task(
                    task=distill_task_desc,
                    label=f"Distill: {task.source_path}",
                    agent_role="knowledge-distiller",
                    origin_channel="desktop",
                    parent_tool_call_id=task.request_id,
                )

                await on_progress(
                    task.request_id,
                    "running",
                    f"Subagent {task_id} running...",
                    0.1,
                )

                # 等待 subagent 完成（最长 1 小时）
                result = await asyncio.wait_for(future, timeout=3600)

                output_path = task.output_path

                # ✅ 保存 iterations 到数据库
                if result and "iterations" in result:
                    try:
                        self.queue.save_iterations(task.id, result["iterations"])
                        logger.info(f"Saved {len(result['iterations'])} iterations for task {task.id}")
                    except Exception as e:
                        logger.warning(f"Failed to save iterations for task {task.id}: {e}")

                # ✅ 从 subagent 结果中提取 markdown 内容
                # 优先级：1) iterations[-1].reasoning（最后一个 iteration 的 reasoning 就是 markdown）
                #         2) result["summary"]（fallback，对话式回复）
                markdown_content: str | None = None
                source_path_for_frontmatter = task.source_path
                extracted_at = datetime.now().isoformat()

                if result and "iterations" in result and result["iterations"]:
                    # 从最后一个包含 reasoning 的 iteration 中提取 markdown
                    for i in range(len(result["iterations"]) - 1, -1, -1):
                        reasoning = result["iterations"][i].get("reasoning", "")
                        if reasoning and reasoning.strip():
                            markdown_content = reasoning.strip()
                            # 尝试从 reasoning 中提取 frontmatter 信息
                            src_match = re.search(r"source:\s*(.+?)(?:\n|$)", reasoning)
                            if src_match:
                                source_path_for_frontmatter = src_match.group(1).strip()
                            time_match = re.search(r"extracted_at:\s*(.+?)(?:\n|$)", reasoning)
                            if time_match:
                                extracted_at = time_match.group(1).strip()
                            break
                    if markdown_content is None:
                        logger.warning(f"Task {task.id}: No reasoning found in any iteration")

                # 如果 reasoning 为空，fallback 到 summary
                if markdown_content is None and result and result.get("summary"):
                    markdown_content = result["summary"].strip()
                    logger.info(f"Task {task.id}: Falling back to result['summary'] for markdown")

                # ✅ 清理 markdown_content 中的 code block 标记
                if markdown_content:
                    if markdown_content.startswith("```markdown"):
                        markdown_content = markdown_content[len("```markdown"):].rstrip("`").strip()
                    elif markdown_content.startswith("```"):
                        lines = markdown_content.split("\n", 1)
                        if len(lines) > 1:
                            markdown_content = lines[1].rstrip("`").strip()
                    # 如果内容只有 frontmatter 而没有正文，尝试从下一个 iteration 补充
                    if markdown_content.startswith("---") and markdown_content.count("\n") < 5:
                        logger.info(f"Task {task.id}: markdown content is too short, checking next iteration")
                        for i in range(len(result["iterations"]) - 2, -1, -1):
                            next_reasoning = result["iterations"][i].get("reasoning", "")
                            if next_reasoning and len(next_reasoning) > len(markdown_content):
                                # 合并内容
                                if next_reasoning.startswith("```markdown"):
                                    next_reasoning = next_reasoning[len("```markdown"):].rstrip("`").strip()
                                elif next_reasoning.startswith("```"):
                                    lines = next_reasoning.split("\n", 1)
                                    if len(lines) > 1:
                                        next_reasoning = lines[1].rstrip("`").strip()
                                # 提取纯 markdown 部分
                                if next_reasoning.startswith("---"):
                                    parts = next_reasoning.split("\n---\n", 1)
                                    if len(parts) > 1:
                                        markdown_content = next_reasoning
                                    else:
                                        markdown_content += "\n\n" + next_reasoning
                                else:
                                    markdown_content = next_reasoning
                                break

                # ✅ 根据是否有 output_path 决定写入文件还是发送给前端
                logger.info(f"Distill task {task.id}: Checking write fallback - output_path={output_path}, is_preview={is_preview}, has_markdown={markdown_content is not None}")

                if is_preview:
                    # Preview 模式：将 markdown 通过 progress 事件发送给前端
                    logger.info(f"Distill task {task.id}: Preview mode, sending markdown to frontend ({len(markdown_content) if markdown_content else 0} chars)")
                    if markdown_content:
                        extra_data = {"markdown": markdown_content}
                    else:
                        logger.warning(f"Distill task {task.id}: No markdown content to send for preview!")
                        extra_data = {"markdown": "", "warning": "No markdown content extracted"}
                else:
                    # 正式模式：写入文件
                    # 检查 subagent 是否已经调用了 write 工具
                    wrote_file = False
                    if result and "iterations" in result:
                        for iter_data in result["iterations"]:
                            for tool in iter_data.get("tools", []):
                                tool_name = tool.get("toolName", "")
                                if tool_name in ("write", "write_file"):
                                    wrote_file = True
                                    logger.info(f"Task {task.id}: Subagent already wrote file via {tool_name}")
                                    break
                            if wrote_file:
                                break

                    if not wrote_file and markdown_content:
                        # Subagent 没有写文件，我们代为写入
                        logger.info(f"Distill task {task.id}: Fallback writing {len(markdown_content)} chars to {output_path}")

                        # 添加 frontmatter（如果没有的话）
                        if not markdown_content.startswith("---"):
                            frontmatter = f"""---
source: {source_path_for_frontmatter}
extracted_at: {extracted_at}
extraction_prompt: |
  {task.prompt}
---

"""
                            markdown_content = frontmatter + markdown_content

                        try:
                            full_path = Path(output_path)
                            if not full_path.is_absolute():
                                full_path = Path(current_workspace) / full_path
                            full_path.parent.mkdir(parents=True, exist_ok=True)
                            full_path.write_text(markdown_content, encoding="utf-8")
                            logger.info(f"✅ Wrote distilled content to {output_path} (subagent didn't call write tool)")
                        except Exception as e:
                            logger.error(f"❌ Failed to write distilled content: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    elif not wrote_file:
                        logger.warning(f"Distill task {task.id}: No write tool called AND no markdown content - cannot fallback!")

                    # 更新索引
                    output_full_for_index = Path(output_path)
                    if not output_full_for_index.is_absolute():
                        output_full_for_index = Path(current_workspace) / output_full_for_index
                    if output_full_for_index.exists():
                        self.engine.update_note(output_path)
                        logger.info(f"Updated index for {output_path}")
                    else:
                        logger.warning(f"Output file {output_path} does not exist after distillation!")

                self.queue.update_status(
                    task.id,
                    status="completed",
                    stage="completed",
                    message="Done",
                    progress=1.0,
                    result_path=output_path,
                )
                if not extra_data:
                    extra_data = {"output_path": output_path}
                await on_progress(
                    task.request_id,
                    "completed",
                    "Done",
                    1.0,
                    extra_data,
                )

            except asyncio.TimeoutError:
                err_msg = "Distillation timed out (1h limit)"
                logger.error(f"Distillation task {task.request_id} timed out")
                self.queue.update_status(
                    task.id,
                    status="failed",
                    stage="failed",
                    message=err_msg,
                    error=err_msg,
                )
                await on_progress(task.request_id, "failed", err_msg, 0.0, {"error": err_msg})
            except Exception as e:
                logger.error(f"Distillation task {task.request_id} failed: {e}")
                self.queue.update_status(
                    task.id,
                    status="failed",
                    stage="failed",
                    message=str(e),
                    error=str(e),
                )
                await on_progress(
                    task.request_id,
                    "failed",
                    str(e),
                    0.0,
                    {"error": str(e)},
                )

    async def _broadcast_progress(self, data: dict) -> None:
        try:
            event = AgentEvent(
                event_type="knowledge_distill_progress",
                channel="desktop",
                data=data,
            )
            await self.bus.publish_event(event)
        except Exception as e:
            logger.error(f"Failed to broadcast distill progress: {e}")
