"""Finite checkpoint stages under one durable import authorization generation."""

import asyncio
import json

from .automatic import automatic_intent
from .discovery import _json
from .discovery_models import DiscoveryConfig
from .expressions import CharacterExpressionService, ExpressionConfig
from .persona import BookPersonaService, PersonaConfig
from .source import BookWorldError
from .storage import connect


class AutomaticExecution:
    def __init__(self, service):
        self.service = service
        self.db_path = service.db_path

    def _claim(self, job_id: str, expected_generation: int | None = None):
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM book_auto_imports WHERE id=?", (job_id,)).fetchone()
            if (
                row is None
                or row["status"] != "queued"
                or expected_generation is not None
                and row["generation"] != expected_generation
            ):
                return None
            try:
                self._authorized(db, row)
            except BookWorldError as error:
                db.execute(
                    "UPDATE book_auto_imports SET status='failed',generation=generation+1,error_code=?,error_detail=? WHERE id=?",
                    (error.code, str(error), job_id),
                )
                return None
            db.execute(
                "UPDATE book_auto_imports SET status='running',generation=generation+1,error_code=NULL,error_detail=NULL WHERE id=?",
                (job_id,),
            )
            return {**dict(row), "generation": row["generation"] + 1}

    def _authorized(self, db, row) -> None:
        item = db.execute(
            "SELECT metadata_json FROM library_items WHERE id=?", (row["library_item_id"],)
        ).fetchone()
        if item is None or not automatic_intent(json.loads(item[0] or "{}")):
            raise BookWorldError("stale_auto_import", "Automatic import intent was revoked")
        source = self.service.discovery.source._source(
            db, row["library_item_id"], row["source_version_id"]
        )
        if source["book_id"] != row["book_id"]:
            raise BookWorldError("stale_auto_import", "Import source binding changed")

    def _call(self, job, phase: str, usage: dict | None = None) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM book_auto_imports WHERE id=? AND generation=? AND status='running'",
                (job["id"], job["generation"]),
            ).fetchone()
            if row is None:
                raise BookWorldError("stale_auto_import", "Automatic import generation was revoked")
            self._authorized(db, row)
            if usage is None:
                db.execute(
                    "UPDATE book_auto_imports SET actual_calls=actual_calls+1 WHERE id=?",
                    (job["id"],),
                )
            else:
                totals = json.loads(row["usage_json"])
                for key, value in usage.items():
                    if type(value) in (int, float) and value >= 0:
                        totals[key] = totals.get(key, 0) + value
                db.execute(
                    "UPDATE book_auto_imports SET usage_json=? WHERE id=?",
                    (_json(totals), job["id"]),
                )

    async def run(self, job_id: str, *, expected_generation: int | None = None) -> None:
        job = await asyncio.to_thread(self._claim, job_id, expected_generation)
        if job is None:
            return
        strategy = json.loads(job["strategy_json"])
        config = DiscoveryConfig.model_validate(strategy["discovery"])

        def update(**values):
            if not self.service._update(job_id, expected_generation=job["generation"], **values):
                raise BookWorldError("stale_auto_import", "Import generation changed")

        try:
            model = await asyncio.to_thread(
                self.service.resolve_model,
                original_config=config,
                model_record_id=strategy.get("model_record_id"),
            )
            if model.config != config:
                raise BookWorldError(
                    "config_changed", "Restore the original import model and strategy to continue"
                )
            execution = self

            class CountedProvider:
                async def chat(self, messages, **kwargs):
                    phase = json.loads(messages[-1]["content"]).get("phase", "discovery")
                    await asyncio.to_thread(execution._call, job, phase)
                    response = await model.provider.chat(messages, **kwargs)
                    await asyncio.to_thread(execution._call, job, phase, response.usage or {})
                    return response

            provider = CountedProvider()
            discovery = self.service.discovery
            current = await asyncio.to_thread(
                discovery.get_build, job["library_item_id"], job["discovery_build_id"]
            )
            if current["stage"] != "discovery_complete":
                await discovery.run(job["discovery_build_id"], provider, config)
                current = await asyncio.to_thread(
                    discovery.get_build, job["library_item_id"], job["discovery_build_id"]
                )
            if current["stage"] != "discovery_complete":
                await asyncio.to_thread(
                    update,
                    status="cancelled" if current["status"] == "cancelled" else "failed",
                    error_code=current.get("error_code") or "discovery_incomplete",
                    error_detail="Discovery did not complete; inspect rejected checkpoints before retrying",
                )
                return
            personas = await asyncio.to_thread(BookPersonaService, self.service.root)
            pconfig = PersonaConfig.model_validate(strategy["persona"])
            if not job["persona_build_id"]:
                published = await asyncio.to_thread(
                    personas.request_build,
                    job["library_item_id"],
                    job["discovery_build_id"],
                    pconfig,
                )
                job["persona_build_id"] = published["build_id"]
                await asyncio.to_thread(
                    update, persona_build_id=published["build_id"], phase="persona"
                )
            current = await asyncio.to_thread(
                discovery.get_build, job["library_item_id"], job["persona_build_id"]
            )
            if current["stage"] != "persona_published":
                await personas.run(job["persona_build_id"], provider, pconfig)
                current = await asyncio.to_thread(
                    discovery.get_build, job["library_item_id"], job["persona_build_id"]
                )
            if current["stage"] != "persona_published":
                await asyncio.to_thread(
                    update,
                    status="cancelled" if current["status"] == "cancelled" else "failed",
                    error_code=current.get("error_code") or "persona_incomplete",
                    error_detail="Canonical publication incomplete; review evidence and retry",
                )
                return
            await asyncio.to_thread(update, phase="expression")
            expressions = await asyncio.to_thread(CharacterExpressionService, self.service.root)
            econfig = ExpressionConfig.model_validate(strategy["expression"])
            sets = json.loads(job["expression_sets_json"])
            people = []
            cursor = 0
            while True:
                page = await asyncio.to_thread(
                    discovery.list_characters,
                    job["library_item_id"],
                    job["persona_build_id"],
                    offset=cursor,
                    limit=50,
                )
                people.extend(page["characters"])
                if page.get("next_offset") is None:
                    break
                cursor = page["next_offset"]
            partial = False
            for person in people:
                if person["agent_status"] not in ("ready", "sparse"):
                    continue
                scope = await asyncio.to_thread(
                    expressions.knowledge.bind_character,
                    job["library_item_id"],
                    job["persona_build_id"],
                    person["id"],
                )
                entry = next(
                    (entry for entry in sets if entry["character_id"] == person["id"]), None
                )
                if entry is None:
                    expression = await asyncio.to_thread(expressions.create_set, scope, econfig)
                    entry = {"character_id": person["id"], "set_id": expression["set_id"]}
                    sets.append(entry)
                    await asyncio.to_thread(
                        self.service.bind_expression_task, job, scope, entry["set_id"]
                    )
                    await asyncio.to_thread(update, expression_sets_json=_json(sets))
                expression = await asyncio.to_thread(expressions.get_set, scope, entry["set_id"])
                if expression["status"] == "queued":
                    await expressions.run(entry["set_id"], provider, econfig)
                    expression = await asyncio.to_thread(
                        expressions.get_set, scope, entry["set_id"]
                    )
                partial = partial or expression["status"] not in ("ready", "partial")
            await asyncio.to_thread(
                update,
                status="partial" if partial else "completed",
                phase="complete",
                error_code="expression_incomplete" if partial else None,
                error_detail="Canon remains available; continue or retry expression tasks independently"
                if partial
                else None,
            )
        except BookWorldError as error:
            if error.code != "stale_auto_import":
                await asyncio.to_thread(
                    self.service._update,
                    job_id,
                    expected_generation=job["generation"],
                    status="blocked_config"
                    if error.code in ("blocked_config", "config_changed")
                    else "failed",
                    error_code=error.code,
                    error_detail=str(error),
                )
        except asyncio.CancelledError:
            await asyncio.shield(
                asyncio.to_thread(
                    self.service._update,
                    job_id,
                    expected_generation=job["generation"],
                    status="interrupted",
                    error_code="service_interrupted",
                    error_detail="Restart resumes only authorized checkpoint stages",
                )
            )
            raise
        except Exception:
            await asyncio.to_thread(
                self.service._update,
                job_id,
                expected_generation=job["generation"],
                status="failed",
                error_code="automatic_failed",
                error_detail="Automatic construction failed; inspect checkpoints and retry",
            )
