"""Compensate durable novel intent after attachment publication in one fixed workspace."""

import json
from pathlib import Path
from uuid import uuid4

from .discovery import BookDiscoveryService, _json
from .discovery_provider import resolve_discovery_model
from .expression_models import ExpressionConfig
from .persona_models import PersonaConfig
from .source import BookWorldError
from .storage import connect, workspace_identity


def automatic_intent(metadata: dict) -> bool:
    intent = metadata.get("book_world", {})
    return (
        isinstance(intent, dict)
        and intent.get("kind") == "novel"
        and intent.get("automatic") is True
    )


class AutoImportService:
    def __init__(self, workspace_root: str | Path, *, resolve_model=resolve_discovery_model):
        self.discovery = BookDiscoveryService(workspace_root)
        self.root = self.discovery.source.root
        self.db_path = self.discovery.db_path
        self.workspace_id = workspace_identity(self.root)
        self.resolve_model = resolve_model

    def get_job(self, item_id: int) -> dict | None:
        with connect(self.db_path) as db:
            row = db.execute(
                "SELECT * FROM book_auto_imports WHERE library_item_id=?", (item_id,)
            ).fetchone()
            canonical = (
                db.execute(
                    "SELECT b.status FROM book_builds b JOIN book_books k ON k.id=b.book_id JOIN book_source_versions s ON s.book_id=b.book_id AND s.id=b.source_version_id WHERE b.book_id=? AND b.source_version_id=? AND b.id=? AND b.stage='persona_published' AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND k.lifecycle_state='active' AND s.lifecycle_state='available'",
                    (row["book_id"], row["source_version_id"], row["persona_build_id"]),
                ).fetchone()
                if row
                else None
            )
            sets = (
                [
                    dict(entry)
                    for entry in db.execute(
                        "SELECT t.character_id,t.set_id,e.status,e.error_code,e.total_calls,c.name,(SELECT COUNT(*) FROM book_expression_materials m WHERE m.set_id=e.id AND m.review_state='accepted') AS accepted_materials FROM book_auto_expression_tasks t JOIN book_expression_sets e ON e.book_id=t.book_id AND e.source_version_id=t.source_version_id AND e.build_id=t.build_id AND e.character_id=t.character_id AND e.id=t.set_id JOIN book_characters c ON c.book_id=t.book_id AND c.source_version_id=t.source_version_id AND c.build_id=t.build_id AND c.id=t.character_id WHERE t.job_id=? ORDER BY c.name,t.character_id",
                        (row["id"],),
                    )
                ]
                if row
                else []
            )
        if row is None:
            return None
        return {
            "job_id": row["id"],
            "workspace_id": self.workspace_id,
            **{
                key: row[key]
                for key in (
                    "library_item_id",
                    "status",
                    "phase",
                    "generation",
                    "book_id",
                    "source_version_id",
                    "discovery_build_id",
                    "persona_build_id",
                    "actual_calls",
                    "error_code",
                    "error_detail",
                )
            },
            "strategy": json.loads(row["strategy_json"]) if row["strategy_json"] else None,
            "expression_sets": sets,
            "usage": json.loads(row["usage_json"]),
            "canon_available": canonical is not None,
            "canonical_status": canonical["status"] if canonical else None,
        }

    def scan(self) -> list[dict]:
        """Queue source-ready imports. This function itself never calls a model."""
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            items = db.execute(
                "SELECT id,metadata_json,chunk_status,pdf_sha256 FROM library_items ORDER BY id"
            ).fetchall()
            for item in items:
                if not automatic_intent(json.loads(item["metadata_json"] or "{}")):
                    previous = db.execute(
                        "SELECT * FROM book_auto_imports WHERE library_item_id=? AND status IN ('queued','running','interrupted','waiting_attachment')",
                        (item["id"],),
                    ).fetchone()
                    if previous is not None:
                        self._revoke_children(db, previous, cancel=True)
                        db.execute(
                            "UPDATE book_auto_imports SET status='cancelled',generation=generation+1 WHERE id=?",
                            (previous["id"],),
                        )
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO book_auto_imports(id,library_item_id,status) VALUES (?,?,'waiting_attachment')",
                    (str(uuid4()), item["id"]),
                )
        results = []
        for item in items:
            if not automatic_intent(json.loads(item["metadata_json"] or "{}")):
                continue
            job = self.get_job(item["id"])
            if job is None:
                continue
            if job["status"] != "waiting_attachment":
                results.append(job)
                continue
            if item["chunk_status"] != "completed":
                if item["chunk_status"] == "failed":
                    self._update(
                        job["job_id"],
                        expected_generation=job["generation"],
                        required_status="waiting_attachment",
                        require_intent=True,
                        status="failed",
                        error_code="attachment_failed",
                        error_detail="Retry attachment processing before retrying character construction",
                    )
                refreshed = self.get_job(item["id"])
                if refreshed is not None:
                    results.append(refreshed)
                continue
            try:
                source = self.discovery.source.prepare_source(item["id"])
                if source["status"] != "ready":
                    self._update(
                        job["job_id"],
                        expected_generation=job["generation"],
                        required_status="waiting_attachment",
                        require_intent=True,
                        status="needs_ocr",
                        error_code="needs_ocr",
                        error_detail="Complete OCR or select a readable attachment",
                    )
                else:
                    model = self.resolve_model()
                    strategy = {
                        "discovery": model.config.model_dump(),
                        "persona": PersonaConfig.from_model(model.config)
                        .model_copy(
                            update={"unit_char_limit": max(8000, model.config.unit_char_limit)}
                        )
                        .model_dump(),
                        "expression": ExpressionConfig.from_model(
                            model.config, model.context_window
                        ).model_dump(),
                        "context_window": model.context_window,
                        "model_record_id": model.model_record_id,
                    }
                    build = self.discovery.create_build(
                        item["id"], source["source_version_id"], model.config
                    )
                    self._update(
                        job["job_id"],
                        expected_generation=job["generation"],
                        required_status="waiting_attachment",
                        require_intent=True,
                        status="queued",
                        phase="discovery",
                        book_id=build["book_id"],
                        source_version_id=source["source_version_id"],
                        discovery_build_id=build["build_id"],
                        strategy_json=_json(strategy),
                        error_code=None,
                        error_detail=None,
                    )
            except BookWorldError as error:
                self._update(
                    job["job_id"],
                    expected_generation=job["generation"],
                    required_status="waiting_attachment",
                    require_intent=True,
                    status="waiting_attachment"
                    if error.code == "source_not_ready"
                    else "blocked_config"
                    if error.code == "blocked_config"
                    else "failed",
                    error_code=error.code,
                    error_detail=str(error),
                )
            refreshed = self.get_job(item["id"])
            if refreshed is not None:
                results.append(refreshed)
        return results

    async def run(self, job_id: str, *, expected_generation: int | None = None) -> None:
        from .automatic_execution import AutomaticExecution

        await AutomaticExecution(self).run(job_id, expected_generation=expected_generation)

    def bind_expression_task(self, job, scope, set_id: str) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM book_auto_imports WHERE id=? AND generation=? AND status='running'",
                (job["id"], job["generation"]),
            ).fetchone()
            if (
                row is None
                or (row["book_id"], row["source_version_id"], row["persona_build_id"])
                != scope.binding[:3]
            ):
                raise BookWorldError(
                    "stale_auto_import", "Expression task does not match current pipeline B"
                )
            db.execute(
                "INSERT OR IGNORE INTO book_auto_expression_tasks(job_id,book_id,source_version_id,build_id,character_id,set_id) VALUES (?,?,?,?,?,?)",
                (job["id"], *scope.binding, set_id),
            )

    @staticmethod
    def _revoke_children(db, row, *, cancel: bool) -> None:
        for build_id in (row["discovery_build_id"], row["persona_build_id"]):
            if not build_id:
                continue
            db.execute(
                "UPDATE book_builds SET status=?,cancel_requested=?,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE book_id=? AND source_version_id=? AND id=? AND lifecycle_state='active' AND status IN ('queued','running','failed','blocked_config','cancelled')",
                (
                    "cancelled" if cancel else "queued",
                    int(cancel),
                    row["book_id"],
                    row["source_version_id"],
                    build_id,
                ),
            )
            if not cancel:
                db.execute(
                    "UPDATE book_builds SET error_code=NULL,error_detail=NULL WHERE book_id=? AND source_version_id=? AND id=? AND lifecycle_state='active' AND status='queued'",
                    (row["book_id"], row["source_version_id"], build_id),
                )
                db.execute(
                    "UPDATE book_build_steps SET status='pending',attempts=0 WHERE book_id=? AND source_version_id=? AND build_id=? AND status IN ('running','failed')",
                    (row["book_id"], row["source_version_id"], build_id),
                )
        for entry in json.loads(row["expression_sets_json"]):
            expression = db.execute(
                "SELECT progress_json,status FROM book_expression_sets WHERE book_id=? AND source_version_id=? AND build_id=? AND character_id=? AND id=? AND lifecycle_state='active'",
                (
                    row["book_id"],
                    row["source_version_id"],
                    row["persona_build_id"],
                    entry["character_id"],
                    entry["set_id"],
                ),
            ).fetchone()
            if expression is None or expression["status"] in ("ready", "partial"):
                continue
            progress = json.loads(expression["progress_json"])
            if not cancel:
                for unit in progress:
                    if unit["status"] != "validated":
                        unit.update(status="pending", attempts=0)
            db.execute(
                "UPDATE book_expression_sets SET status=?,cancel_requested=?,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_json=?,window_calls=0 WHERE id=?",
                (
                    "cancelled" if cancel else "queued",
                    int(cancel),
                    _json(progress),
                    entry["set_id"],
                ),
            )

    def control(self, item_id: int, job_id: str, action: str) -> dict:
        if action not in ("cancel", "retry", "restart"):
            raise BookWorldError("invalid_request", "Choose cancellation or explicit retry")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM book_auto_imports WHERE library_item_id=? AND id=?",
                (item_id, job_id),
            ).fetchone()
            item = self.discovery.source._item(db, item_id)
            if row is None:
                raise BookWorldError("automatic_unavailable", "Reload the current import pipeline")
            if action == "retry" and row["status"] in ("queued", "running", "completed"):
                raise BookWorldError(
                    "invalid_automatic_state", "This pipeline is active or already completed"
                )
            metadata = json.loads(item["metadata_json"] or "{}")
            metadata["book_world"] = {"kind": "novel", "automatic": action != "cancel"}
            db.execute(
                "UPDATE library_items SET metadata_json=? WHERE id=?", (_json(metadata), item_id)
            )
            if action == "restart":
                self._revoke_children(db, row, cancel=True)
                db.execute(
                    "UPDATE book_auto_imports SET library_item_id=NULL,status='cancelled',generation=generation+1 WHERE id=?",
                    (job_id,),
                )
                db.execute(
                    "INSERT INTO book_auto_imports(id,library_item_id,status) VALUES (?,?,'waiting_attachment')",
                    (str(uuid4()), item_id),
                )
            else:
                if row["source_version_id"] and action == "retry":
                    self.discovery.source._source(db, item_id, row["source_version_id"])
                self._revoke_children(db, row, cancel=action == "cancel")
                db.execute(
                    "UPDATE book_auto_imports SET status=?,generation=generation+1,error_code=NULL,error_detail=NULL WHERE id=?",
                    (
                        "cancelled"
                        if action == "cancel"
                        else "queued"
                        if row["strategy_json"]
                        else "waiting_attachment",
                        job_id,
                    ),
                )
        result = self.get_job(item_id)
        assert result is not None
        return result

    def recover(self) -> list[str]:
        """First process entry revokes interrupted build leases and retains checkpoints."""
        recovered = []
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM book_auto_imports WHERE status IN ('running','interrupted') ORDER BY created_at,id"
            ).fetchall()
            for row in rows:
                item = db.execute(
                    "SELECT metadata_json FROM library_items WHERE id=?", (row["library_item_id"],)
                ).fetchone()
                allowed = item is not None and automatic_intent(json.loads(item[0] or "{}"))
                self._revoke_children(db, row, cancel=not allowed)
                db.execute(
                    "UPDATE book_auto_imports SET status=?,generation=generation+1,error_code=NULL,error_detail=NULL WHERE id=?",
                    ("queued" if allowed else "cancelled", row["id"]),
                )
                recovered.append(row["id"])
        return recovered

    def _update(
        self,
        job_id: str,
        *,
        expected_generation: int | None = None,
        required_status: str | None = None,
        require_intent: bool = False,
        **values,
    ) -> bool:
        fields = {
            "status",
            "phase",
            "book_id",
            "source_version_id",
            "discovery_build_id",
            "persona_build_id",
            "strategy_json",
            "expression_sets_json",
            "error_code",
            "error_detail",
        }
        if not values.keys() <= fields:
            raise ValueError("Unknown automatic import fields")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            if require_intent:
                intent = db.execute(
                    "SELECT i.metadata_json FROM book_auto_imports j JOIN library_items i ON i.id=j.library_item_id WHERE j.id=?",
                    (job_id,),
                ).fetchone()
                if intent is None or not automatic_intent(json.loads(intent[0] or "{}")):
                    return False
            result = db.execute(
                "UPDATE book_auto_imports SET "
                + ",".join(key + "=?" for key in values)
                + " WHERE id=? AND (? IS NULL OR generation=?) AND (? IS NULL OR status=?)",
                (
                    *values.values(),
                    job_id,
                    expected_generation,
                    expected_generation,
                    required_status,
                    required_status,
                ),
            )
            return result.rowcount == 1
