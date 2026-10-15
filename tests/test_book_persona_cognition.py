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
@pytest.mark.parametrize("extract_version", ["persona-extract-v4", "persona-extract-v5"])
async def test_persona_intent_prompts_create_independent_build_and_preserve_old_canon(
    book_library, extract_version
):
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
            "prompt_version": extract_version,
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
@pytest.mark.parametrize("failure", ["owner", "excerpt", "review"])
async def test_v5_retry_receives_bounded_field_cause_and_still_requires_independent_review(
    book_library, failure
):
    from backend.core.providers.base import LLMResponse

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version="persona-extract-v5",
        review_prompt_version="persona-review-v4",
    )
    build = service.request_build(item, parent, config)
    sent = []

    class Provider(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            sent.append(data["phase"])
            reply = await super().chat(messages, **kwargs)
            value = json.loads(reply.content)
            if data["phase"] == "extract" and sent.count("extract") == 1:
                if failure == "owner":
                    value["claims"][0]["owner_character_id"] = None
                elif failure == "excerpt":
                    value["claims"][0]["approved_excerpt"] = "SECRET-TEST-FIELD-INPUT"
            elif data["phase"] == "review" and sent.count("review") == 1 and failure == "review":
                value["claims"][0]["access"] = []
            if data["phase"] == "extract" and sent.count("extract") == 2:
                error = data["previous_error"]
                assert len(error) <= 300 and "SECRET-TEST-FIELD-INPUT" not in error
                if failure == "owner":
                    assert "extract" in error and "claims.0" in error and "personal claims" in error
                elif failure == "excerpt":
                    assert "extract" in error and "claims.0.approved_excerpt" in error
                    assert "extra_forbidden" in error and "Extra inputs" in error
                else:
                    assert "review" in error and "add or omit access" in error
            return LLMResponse(content=json.dumps(value))

    await service.run(build["build_id"], Provider(), config)
    expected = (
        ["extract", "review", "extract", "review"]
        if failure == "review"
        else ["extract", "extract", "review"]
    )
    assert sent == expected
    state = service.discovery.get_build(item, build["build_id"])
    assert state["stage"] == "persona_published" and state["failed_units"] == 0


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
