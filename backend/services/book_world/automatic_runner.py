"""Scan persisted intent in fixed workspaces; failed/cancelled jobs require user action."""

import asyncio
from contextlib import suppress
from pathlib import Path

from loguru import logger

from .automatic import AutoImportService
from .storage import workspace_identity
from .worker_pool import build_slot


class AutoImportRunner:
    _scanners: dict[tuple[asyncio.AbstractEventLoop, str], asyncio.Task] = {}
    _workers: dict[tuple[asyncio.AbstractEventLoop, str, str], asyncio.Task] = {}
    _controls: dict[tuple[asyncio.AbstractEventLoop, str, str], asyncio.Lock] = {}

    @classmethod
    def control_lock(cls, root: Path, job_id: str) -> asyncio.Lock:
        return cls._controls.setdefault(
            (asyncio.get_running_loop(), workspace_identity(root), job_id), asyncio.Lock()
        )

    @classmethod
    async def schedule(cls, service: AutoImportService, root: Path, job: dict) -> None:
        key = asyncio.get_running_loop(), workspace_identity(root), job["job_id"]
        async with cls.control_lock(root, job["job_id"]):
            if key in cls._workers and not cls._workers[key].done():
                return
            current = await asyncio.to_thread(service.get_job, job["library_item_id"])
            if (
                current is None
                or current["job_id"] != job["job_id"]
                or current["status"] != "queued"
                or current["generation"] != job["generation"]
            ):
                return

            async def work():
                try:
                    async with build_slot(root):
                        await service.run(job["job_id"], expected_generation=job["generation"])
                except Exception:
                    logger.error("Automatic book construction failed in a fixed workspace")
                finally:
                    if cls._workers.get(key) is asyncio.current_task():
                        cls._workers.pop(key, None)

            cls._workers[key] = asyncio.create_task(work())

    @classmethod
    def start(cls, root: str | Path) -> None:
        root = Path(root).resolve()
        key = asyncio.get_running_loop(), workspace_identity(root)
        if key in cls._scanners and not cls._scanners[key].done():
            return

        async def scan():
            service = await asyncio.to_thread(AutoImportService, root)
            await asyncio.to_thread(service.recover)
            try:
                while True:
                    try:
                        jobs = await asyncio.to_thread(service.scan)
                        for job in jobs:
                            if job["status"] == "queued":
                                await cls.schedule(service, root, job)
                    except Exception:
                        logger.warning(
                            "Automatic book scan deferred after an I/O or configuration failure"
                        )
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Automatic book intent scan stopped; persisted jobs retained")

        cls._scanners[key] = asyncio.create_task(scan())

    @classmethod
    async def stop_job(cls, root: Path, job_id: str) -> None:
        key = asyncio.get_running_loop(), workspace_identity(root), job_id
        task = cls._workers.get(key)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @classmethod
    async def shutdown(cls) -> None:
        tasks = [*cls._scanners.values(), *cls._workers.values()]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        cls._scanners.clear()
        cls._workers.clear()
