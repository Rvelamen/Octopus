"""Deterministic trait-lint wiring into the persona publication report.

Pairs the pure-function ``trait_completion_overreach`` linter in
``backend/services/book_world/proposition_alignment.py`` (T17
remaining_work item 1) with the persona publication pipeline so that
every published persona build's ``publication_report`` carries a
``trait_lint_warnings`` list. The list is purely additive; the existing
five publication keys (``failed_units`` / ``rejected_claims`` /
``unresolved_characters`` / ``published_characters`` /
``baseline_conflicts``) are unchanged.

These tests are deterministic, use only the existing ``book_library``
fixture and the ``PersonaProvider`` / ``ScriptedPersonaProvider`` /
``discovered`` / ``quote`` / ``review_all`` helpers from
``tests/test_book_persona.py``. No model calls; no canonical baseline
mutation.
"""

import json
import sqlite3

import pytest
from test_book_persona import (
    PersonaProvider,
    ScriptedPersonaProvider,
    discovered,
    quote,
    review_all,
)

from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.storage import connect

# The exact trait proposition / evidence pair from the T17 matrix v2
# baseline that motivates this wiring. Reused in the over-reach and
# aligned tests below.
_TRAIT_OVERREACH_PROPOSITION = "石猴勇敢果断，敢于率先跳入瀑布泉中探险。"
_TRAIT_OVERREACH_QUOTE_FRAGMENT = "我进去！我进去！"


async def _run_publication(library, text: str, extract, review):
    """Run a discovery → persona build → publication cycle.

    The persona service writes the publication report into
    ``book_build_steps``; we read it back via ``service.discovery``.
    """
    item, parent = await discovered(library, text)
    service = BookPersonaService(library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    return item, service, config, build["build_id"]


@pytest.mark.asyncio
async def test_trait_lint_warning_appears_when_trait_overreaches(book_library):
    """An over-reaching trait claim must produce one warning entry.

    The trait proposition asserts a completed action (``率先跳入...探险``)
    while the evidence quote only proves volunteered intent
    (``我进去！我进去！``). This is the exact T17 matrix-v2 failure
    mode; the publication summary must surface it for downstream
    consumers.
    """
    text = "人物甲：" + _TRAIT_OVERREACH_QUOTE_FRAGMENT

    def extract(data):
        alpha = data["characters"][0]["id"]
        # Use the full segment text as the quote so the alias check
        # (which requires the character name to appear in the
        # acquisition quote) passes.
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "brave",
                    "kind": "trait",
                    "owner_character_id": alpha,
                    "proposition": _TRAIT_OVERREACH_PROPOSITION,
                    "slot_key": "trait:胆识",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    item, service, config, build_id = await _run_publication(
        book_library, text, extract, review_all
    )
    final = service.discovery.get_build(item, build_id)
    warnings = final["publication_report"]["trait_lint_warnings"]
    assert len(warnings) == 1
    entry = warnings[0]
    assert entry["asserted_verb"] == "跳入"
    assert "率先" in entry["reason"]
    assert entry["matched_intent_marker"] in {"我进去", "应声", "高叫", "叫道"}
    assert entry["proposition"] == _TRAIT_OVERREACH_PROPOSITION
    assert entry["evidence_quote"] == text


@pytest.mark.asyncio
async def test_trait_lint_warning_absent_when_aligned(book_library):
    """A trait whose evidence quote records the completed action must
    not be flagged.

    Mirrors
    ``tests/test_book_proposition_alignment.py::test_aligned_trait_with_completed_action_in_quote_passes``:
    the quote literally contains the asserted completion verb
    (``跳入``), so the lint is silent.
    """
    text = "人物甲径跳入瀑布泉中"

    def extract(data):
        alpha = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "brave",
                    "kind": "trait",
                    "owner_character_id": alpha,
                    "proposition": _TRAIT_OVERREACH_PROPOSITION,
                    "slot_key": "trait:胆识",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    item, service, config, build_id = await _run_publication(
        book_library, text, extract, review_all
    )
    final = service.discovery.get_build(item, build_id)
    assert final["publication_report"]["trait_lint_warnings"] == []


@pytest.mark.asyncio
async def test_trait_lint_warning_absent_for_episode_claims(book_library):
    """An episode claim with the same over-reach phrasing must not be
    flagged.

    The lint is intentionally narrow: only ``kind='trait'`` is scanned.
    Episodes legitimately describe completed historical actions.
    """
    text = "人物甲：" + _TRAIT_OVERREACH_QUOTE_FRAGMENT

    def extract(data):
        alpha = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "leap",
                    "kind": "episode",
                    "owner_character_id": alpha,
                    "proposition": _TRAIT_OVERREACH_PROPOSITION,
                    # Episodes do not carry a slot_key; publication flow
                    # treats them as historical context only.
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    item, service, config, build_id = await _run_publication(
        book_library, text, extract, review_all
    )
    final = service.discovery.get_build(item, build_id)
    assert final["publication_report"]["trait_lint_warnings"] == []


@pytest.mark.asyncio
async def test_publication_summary_always_includes_trait_lint_warnings_key(book_library):
    """The publication summary must always carry
    ``trait_lint_warnings``.

    The key is purely additive on top of the existing five keys
    (``failed_units`` / ``rejected_claims`` / ``unresolved_characters``
    / ``published_characters`` / ``baseline_conflicts``) so downstream
    consumers (tests, ``discovery.get_build`` API, future
    revision-review prompt) can rely on a stable shape. The default is
    an empty list when no over-reaching traits exist.
    """
    item, parent = await discovered(book_library, "人物甲说：我最看重诚信。")
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    await service.run(build["build_id"], PersonaProvider(), config)
    final = service.discovery.get_build(item, build["build_id"])
    report = final["publication_report"]
    assert "trait_lint_warnings" in report
    assert report["trait_lint_warnings"] == []
    # The existing five keys remain untouched (additive guarantee).
    assert {
            "failed_units",
            "rejected_claims",
            "unresolved_characters",
            "published_characters",
            "baseline_conflicts",
        }.issubset(report.keys())


@pytest.mark.asyncio
async def test_trait_lint_warning_persists_in_frozen_publication_step(book_library):
    """The trait-lint warning must survive in the frozen publication
    row.

    Once a persona build is published, the ``book_build_steps`` row for
    ``stage='publication', unit_key='summary'`` is immutable: any
    UPDATE on ``result_json`` must raise ``sqlite3.IntegrityError``
    (mirrors
    ``tests/test_book_persona.py::test_published_canon_and_agent_definition_are_frozen_and_scoped``).
    After confirming the freeze, a fresh SELECT must still show the
    lint warning from before the freeze was attempted.
    """
    text = "人物甲：" + _TRAIT_OVERREACH_QUOTE_FRAGMENT

    def extract(data):
        alpha = data["characters"][0]["id"]
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "brave",
                    "kind": "trait",
                    "owner_character_id": alpha,
                    "proposition": _TRAIT_OVERREACH_PROPOSITION,
                    "slot_key": "trait:胆识",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    item, service, config, build_id = await _run_publication(
        book_library, text, extract, review_all
    )
    final = service.discovery.get_build(item, build_id)
    assert len(final["publication_report"]["trait_lint_warnings"]) == 1

    # The frozen publication row blocks tampering with result_json.
    with pytest.raises(sqlite3.IntegrityError), connect(service.db_path) as db:
        db.execute(
            "UPDATE book_build_steps SET result_json=? WHERE build_id=? AND stage='publication' AND unit_key='summary'",
            (json.dumps({}), build_id),
        )

    # A fresh SELECT still surfaces the original warning.
    with connect(service.db_path) as db:
        row = db.execute(
            "SELECT result_json FROM book_build_steps WHERE build_id=? AND stage='publication' AND unit_key='summary'",
            (build_id,),
        ).fetchone()
    report = json.loads(row["result_json"])
    assert len(report["trait_lint_warnings"]) == 1
    assert report["trait_lint_warnings"][0]["asserted_verb"] == "跳入"
