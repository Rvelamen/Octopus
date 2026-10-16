"""A separate knowledge review can only remove canonical permissions."""

import hashlib
import json
from pathlib import Path

import pytest
from test_book_persona import PersonaProvider, discovered

from backend.core.providers.base import LLMResponse
from backend.services.book_world.persona import BookPersonaService
from backend.services.book_world.persona_models import PersonaConfig
from backend.services.book_world.storage import connect


class KnowledgeProvider(PersonaProvider):
    def __init__(self, *, scope="whole", canonical=True, invalid=None, cancel=None):
        super().__init__()
        self.scope, self.canonical, self.invalid, self.cancel = scope, canonical, invalid, cancel
        self.phases = []

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.phases.append(data["phase"])
        if data["phase"] != "review_acquisition":
            value = json.loads((await super().chat(messages, **kwargs)).content)
            if data["phase"] == "extract":
                claim = value["claims"][0]
                claim["access"][0]["approved_excerpt"] = claim["evidence"][0]["quote"]
            else:
                value["claims"][0]["access"][0].update(
                    authorized=self.canonical, excerpt_safe=self.canonical
                )
            return LLMResponse(content=json.dumps(value))
        self.inputs.append(data)
        if self.cancel:
            self.cancel()
        claim = data["proposals"]["claims"][0]
        recipient = {
            "local_key": claim["local_key"],
            "character_id": claim["access"][0]["character_id"],
            "knowledge_scope": self.scope,
            "unknown_parts": [] if self.scope == "whole" else ["未证明本人知道全部内容"],
            "knowledge_evidence": [claim["access"][0]["acquisition"]],
            "reason": "只审本人所知，不以事实成立代替获知。",
            "excerpt_safe": self.scope == "whole",
            "excerpt_reason": "安全部分与本人所知分别判断。",
        }
        if self.invalid == "foreign":
            recipient["knowledge_evidence"][0] = {
                **recipient["knowledge_evidence"][0],
                "segment_id": "another-source",
            }
        elif self.invalid == "contradiction":
            recipient["unknown_parts"] = ["还有本人未知部分"]
        elif self.invalid == "empty_proof":
            recipient["knowledge_evidence"] = []
        recipients = [] if self.invalid == "missing" else [recipient]
        if self.invalid == "duplicate":
            recipients.append(recipient)
        return LLMResponse(content=json.dumps({"recipients": recipients}))


def config():
    return PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version="persona-extract-v7",
        review_prompt_version="persona-review-v7",
    )


def test_acquisition_prompt_matches_frozen_diagnostic_without_promoting_default():
    from backend.services.book_world.persona_acquisition import ACQUISITION_PROMPT

    path = (
        Path(__file__).resolve().parents[1]
        / "docs/plans/book-character-agents/validation/real-model-persona-acquisition-controls-v4.json"
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert hashlib.sha256(ACQUISITION_PROMPT.encode()).hexdigest() == saved["prompt_sha256"]
    assert (
        PersonaConfig(provider_id=1, model="fixture").review_prompt_version == "persona-review-v3"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope,canonical", [("partial", True), ("unproven", True), ("whole", True), ("whole", False)]
)
async def test_knowledge_review_is_a_monotone_veto_and_reader_only_audit(
    book_library, scope, canonical
):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    settings = config()
    build = service.request_build(item, parent, settings)
    provider = KnowledgeProvider(scope=scope, canonical=canonical)
    await service.run(build["build_id"], provider, settings)
    assert provider.phases == ["extract", "review", "review_acquisition"]
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    detail = service.get_character(item, build["build_id"], person["id"])
    claim = detail["reader"]["claims"][0]
    access = claim["access"][0]
    allowed = scope == "whole" and canonical
    assert claim["support_state"] == "accepted"
    assert access["access_state"] == ("accepted" if allowed else "revoked")
    assert access["knowledge_review"]["knowledge_scope"] == scope
    assert access["knowledge_review"]["reason"]
    assert access["knowledge_review"]["knowledge_evidence"][0]["quote"]
    definition = service.get_agent_definition(item, build["build_id"], person["id"])
    assert bool(definition["baseline"]) == allowed
    assert "knowledge_review" not in json.dumps(definition)
    assert "unknown_parts" not in json.dumps(definition)
    with connect(service.db_path) as db:
        step = json.loads(
            db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence'",
                (build["build_id"],),
            ).fetchone()[0]
        )
    assert step["canonical_review"]["claims"][0]["access"][0]["authorized"] == canonical
    assert step["review"]["claims"][0]["access"][0]["authorized"] == allowed
    assert step["acquisition_review"]["recipients"][0]["knowledge_scope"] == scope


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", ["missing", "duplicate", "foreign", "contradiction", "empty_proof"]
)
async def test_invalid_knowledge_review_stops_after_one_repair_and_publishes_no_claim(
    book_library, invalid
):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    settings = config()
    build = service.request_build(item, parent, settings)
    provider = KnowledgeProvider(invalid=invalid)
    await service.run(build["build_id"], provider, settings)
    assert provider.phases == ["extract", "review", "review_acquisition"] * 2
    assert service.discovery.get_build(item, build["build_id"])["failed_units"] == 1
    with connect(service.db_path) as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM book_claims WHERE build_id=?", (build["build_id"],)
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT attempts FROM book_build_steps WHERE build_id=? AND stage='evidence'",
                (build["build_id"],),
            ).fetchone()[0]
            == 2
        )


@pytest.mark.asyncio
async def test_cancel_during_knowledge_review_cannot_save_late_proof_or_claim(book_library):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    settings = config()
    build = service.request_build(item, parent, settings)
    provider = KnowledgeProvider(cancel=lambda: service.control(item, build["build_id"], "cancel"))
    await service.run(build["build_id"], provider, settings)
    assert provider.phases == ["extract", "review", "review_acquisition"]
    assert service.discovery.get_build(item, build["build_id"])["status"] == "cancelled"
    with connect(service.db_path) as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM book_claims WHERE build_id=?", (build["build_id"],)
            ).fetchone()[0]
            == 0
        )
        assert (
            "acquisition_review"
            not in db.execute(
                "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='evidence'",
                (build["build_id"],),
            ).fetchone()[0]
        )
