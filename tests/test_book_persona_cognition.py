"""Versioned persona prompts must publish new builds without rewriting old canon."""

import hashlib
import json
from pathlib import Path

import pytest
from test_book_persona import PersonaProvider, discovered

from backend.services.book_world.persona import BookPersonaService
from backend.services.book_world.persona_models import (
    EXTRACT_PROMPTS,
    REVIEW_PROMPTS,
    PersonaConfig,
)
from backend.services.book_world.storage import connect


def test_saved_strategy_values_and_calibrated_review_match_frozen_native_records():
    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    saved = json.loads((base / "real-model-persona-intent-v5-01.json").read_text(encoding="utf-8"))
    controls = json.loads(
        (base / "real-model-persona-evidence-controls-v1.json").read_text(encoding="utf-8")
    )

    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()

    assert digest(EXTRACT_PROMPTS["persona-extract-v5"]) == saved["prompt_sha256"]["extract"]
    assert digest(REVIEW_PROMPTS["persona-review-v4"]) == saved["prompt_sha256"]["review"]
    assert digest(REVIEW_PROMPTS["persona-review-v5"]) == controls["prompt_sha256"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extract_version,review_version",
    [
        ("persona-extract-v4", "persona-review-v4"),
        ("persona-extract-v5", "persona-review-v4"),
        ("persona-extract-v6", "persona-review-v5"),
    ],
)
async def test_persona_intent_prompts_create_independent_build_and_preserve_old_canon(
    book_library, extract_version, review_version
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
            "review_prompt_version": review_version,
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
@pytest.mark.parametrize("extract_version", ["persona-extract-v5", "persona-extract-v6"])
async def test_v5_retry_receives_bounded_field_cause_and_still_requires_independent_review(
    book_library, failure, extract_version
):
    from backend.core.providers.base import LLMResponse

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version=extract_version,
        review_prompt_version="persona-review-v5"
        if extract_version.endswith("v6")
        else "persona-review-v4",
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


@pytest.mark.asyncio
@pytest.mark.parametrize("complete_quotes", [False, True])
async def test_v6_review_verdict_controls_projection_even_when_full_input_has_more_support(
    book_library, complete_quotes
):
    from backend.core.providers.base import LLMResponse

    item, parent = await discovered(
        book_library, "人物甲说：我最看重诚信。\n\n人物甲说：我也重视勇气。"
    )
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version="persona-extract-v6",
        review_prompt_version="persona-review-v5",
    )
    build = service.request_build(item, parent, config)
    seen = []

    class Provider(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data["phase"])
            prompt = (
                EXTRACT_PROMPTS[config.prompt_version]
                if data["phase"] == "extract"
                else REVIEW_PROMPTS[config.review_prompt_version]
            )
            assert messages[0]["content"].startswith(prompt)
            value = json.loads((await super().chat(messages, **kwargs)).content)
            if data["phase"] == "extract":
                claim = value["claims"][0]
                claim["proposition"] = "人物甲重视诚信与勇气"
                if complete_quotes:
                    row = data["segments"][1]
                    claim["evidence"].append(
                        {
                            "segment_id": row["id"],
                            "local_start": 0,
                            "local_end": len(row["text"]),
                            "quote": row["text"],
                        }
                    )
            else:
                assert any("勇气" in row["text"] for row in data["segments"])
                evidence = data["proposals"]["claims"][0]["evidence"]
                assert any("勇气" in row["quote"] for row in evidence) == complete_quotes
                checked = value["claims"][0]
                checked.update(
                    supported=complete_quotes,
                    baseline_supported=True,
                    reason="保存引文支持全部子句"
                    if complete_quotes
                    else "勇气仅在未引用段落，保存引文不全",
                )
                # A claim veto must win even if independent acquisition flags are affirmative.
                checked["access"][0]["authorized"] = True
            return LLMResponse(content=json.dumps(value, ensure_ascii=False))

    await service.run(build["build_id"], Provider(), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    definition = service.get_agent_definition(item, build["build_id"], person["id"])
    assert seen == ["extract", "review"]
    assert bool(definition["baseline"]) == complete_quotes
    claims = service.get_character(item, build["build_id"], person["id"])["reader"]["claims"]
    assert claims[0]["support_state"] == ("accepted" if complete_quotes else "rejected")
    assert claims[0]["access"][0]["access_state"] == ("accepted" if complete_quotes else "revoked")


def test_v7_requires_deliberate_excerpt_without_mutating_legacy_schema():
    from backend.services.book_world.persona_models import PersonaBatch, persona_batch_schema

    original = PersonaBatch.model_json_schema()
    strict = persona_batch_schema("persona-extract-v7")
    access = strict["$defs"]["AccessProposal"]
    assert "approved_excerpt" in access["required"]
    assert "default" not in access["properties"]["approved_excerpt"]
    for version in ("persona-extract-v3", "persona-extract-v5", "persona-extract-v6"):
        assert persona_batch_schema(version) == original
    strict["$defs"]["AccessProposal"]["required"].clear()
    assert PersonaBatch.model_json_schema() == original


def test_v7_review_preserves_exact_fixed_control_prompt_and_old_versions():
    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    controls = json.loads(
        (base / "real-model-persona-scope-controls-v2.json").read_text(encoding="utf-8")
    )
    assert (
        hashlib.sha256(REVIEW_PROMPTS["persona-review-v6"].encode()).hexdigest()
        == controls["prompt_sha256"]
    )
    saved = json.loads(
        (base / "real-model-persona-evidence-v6-01.json").read_text(encoding="utf-8")
    )
    assert (
        hashlib.sha256(EXTRACT_PROMPTS["persona-extract-v6"].encode()).hexdigest()
        == saved["prompt_sha256"]["extract"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "omission,empty", [("never", False), ("never", True), ("first", False), ("always", False)]
)
async def test_v7_excerpt_choice_is_enforced_before_review_with_only_one_retry(
    book_library, omission, empty
):
    from backend.core.providers.base import LLMResponse

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1,
        model="fixture",
        unit_char_limit=4000,
        prompt_version="persona-extract-v7",
        review_prompt_version="persona-review-v6",
    )
    build = service.request_build(item, parent, config)
    seen = []

    class Provider(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data["phase"])
            value = json.loads((await super().chat(messages, **kwargs)).content)
            if data["phase"] == "extract":
                if seen.count("extract") == 2:
                    assert "extract" in data["previous_error"]
                    assert "claims.0.access.0.approved_excerpt" in data["previous_error"]
                if omission == "always" or (omission == "first" and seen.count("extract") == 1):
                    pass
                else:
                    claim = value["claims"][0]
                    claim["access"][0]["approved_excerpt"] = (
                        "" if empty else claim["evidence"][0]["quote"]
                    )
            return LLMResponse(content=json.dumps(value))

    await service.run(build["build_id"], Provider(), config)
    state = service.discovery.get_build(item, build["build_id"])
    with connect(service.db_path) as db:
        step = db.execute(
            "SELECT * FROM book_build_steps WHERE build_id=? AND stage='evidence'",
            (build["build_id"],),
        ).fetchone()
        if omission == "always":
            assert seen == ["extract", "extract"] and step["attempts"] == 2
            assert step["status"] == "failed" and state["failed_units"] == 1
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM book_claims WHERE build_id=?", (build["build_id"],)
                ).fetchone()[0]
                == 0
            )
        else:
            assert seen == (
                ["extract", "extract", "review"] if omission == "first" else ["extract", "review"]
            )
            assert state["failed_units"] == 0 and step["status"] == "validated"
            excerpts = [
                r[0]
                for r in db.execute(
                    "SELECT approved_excerpt FROM book_access_evidence WHERE build_id=?",
                    (build["build_id"],),
                )
            ]
            assert excerpts == ([""] if empty else ["人物甲说：我最看重诚信。"])
