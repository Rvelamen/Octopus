"""Versioned persona prompts must publish new builds without rewriting old canon."""

import json

import pytest
from test_book_persona import PersonaProvider, discovered

from backend.services.book_world.persona import BookPersonaService
from backend.services.book_world.persona_models import (
    EXTRACT_PROMPTS,
    REVIEW_PROMPTS,
    PersonaConfig,
)
from backend.services.book_world.storage import connect


@pytest.mark.asyncio
async def test_persona_intent_prompts_create_independent_build_and_preserve_old_canon(book_library):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    old = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    legacy = service.request_build(item, parent, old)
    await service.run(legacy["build_id"], PersonaProvider(), old)
    with connect(service.db_path) as db:
        before = [
            tuple(r)
            for r in db.execute(
                "SELECT * FROM book_claims WHERE build_id=? ORDER BY id", (legacy["build_id"],)
            )
        ]
    config = old.model_copy(
        update={
            "prompt_version": "persona-extract-v4",
            "review_prompt_version": "persona-review-v4",
        }
    )
    build = service.request_build(item, parent, config)
    assert build["build_id"] != legacy["build_id"]
    assert service.request_build(item, parent, config)["build_id"] == build["build_id"]
    sent = []

    class Provider(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            expected = (
                EXTRACT_PROMPTS[config.prompt_version]
                if data["phase"] == "extract"
                else REVIEW_PROMPTS[config.review_prompt_version]
            )
            assert messages[0]["content"].startswith(expected)
            sent.append(data["phase"])
            return await super().chat(messages, **kwargs)

    await service.run(build["build_id"], Provider(), config)
    assert sent == ["extract", "review"]
    assert service.discovery.get_build(item, build["build_id"])["stage"] == "persona_published"
    with connect(service.db_path) as db:
        after = [
            tuple(r)
            for r in db.execute(
                "SELECT * FROM book_claims WHERE build_id=? ORDER BY id", (legacy["build_id"],)
            )
        ]
    assert before == after


@pytest.mark.asyncio
async def test_saved_legacy_persona_build_still_uses_original_prompts(book_library):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version="persona-extract-v3",
        review_prompt_version="persona-review-v3",
    )
    build = service.request_build(item, parent, config)
    sent = []

    class Provider(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            expected = (
                EXTRACT_PROMPTS[config.prompt_version]
                if data["phase"] == "extract"
                else REVIEW_PROMPTS[config.review_prompt_version]
            )
            assert messages[0]["content"].startswith(expected)
            sent.append(data["phase"])
            return await super().chat(messages, **kwargs)

    await service.run(build["build_id"], Provider(), config)
    assert sent == ["extract", "review"]
