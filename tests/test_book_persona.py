"""Canonical publication and logical-agent boundaries in a disposable workspace."""

import json

import pytest

from backend.core.providers.base import LLMResponse
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.persona import BookPersonaService, PersonaConfig
from backend.services.book_world.source import BookSourceService, BookWorldError


async def discovered(library, text="人物甲说：我最看重诚信。", people=(("人物甲", "active"),)):
    path = library.workspace_root / "persona-story.txt"
    path.write_bytes(text.encode("utf-8"))
    item = library.create_item(pdf_path=path, metadata={"title": "原著样本", "item_type": "book"})
    library.import_text_attachment(item["id"], path)
    source = BookSourceService(library.workspace_root).prepare_source(item["id"])
    service = BookDiscoveryService(library.workspace_root)
    config = DiscoveryConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.create_build(item["id"], source["source_version_id"], config)

    class IdentityProvider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            rows = data["segments"]
            identities = []
            for name, presence in people:
                row = next(row for row in rows if name in row["text"])
                existing = next(
                    (item for item in data["known_characters"] if item["name"] == name), None
                )
                identities.append(
                    {
                        "name": name,
                        "local_character_key": name,
                        "presence": presence,
                        "identity": "existing" if existing else "new",
                        **({"existing_character_id": existing["id"]} if existing else {}),
                        "evidence": {
                            "segment_id": row["id"],
                            "local_start": row["text"].index(name),
                            "local_end": row["text"].index(name) + len(name),
                            "quote": name,
                        },
                    }
                )
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [
                            {
                                "segment_ids": [row["id"] for row in rows],
                                "characters": identities,
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )

    await service.run(build["build_id"], IdentityProvider(), config)
    return item["id"], build["build_id"]


class PersonaProvider:
    def __init__(self):
        self.inputs = []

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.inputs.append(data)
        if data["phase"] == "extract":
            character = data["characters"][0]
            span = {
                "segment_id": data["segments"][0]["id"],
                "local_start": 0,
                "local_end": len("人物甲说：我最看重诚信。"),
                "quote": "人物甲说：我最看重诚信。",
            }
            result = {
                "claims": [
                    {
                        "local_key": "value",
                        "kind": "trait",
                        "owner_character_id": character["id"],
                        "proposition": "人物甲重视诚信",
                        "slot_key": "value:诚信",
                        "evidence": [span],
                        "access": [
                            {
                                "character_id": character["id"],
                                "route": "firsthand",
                                "acquisition": span,
                            }
                        ],
                    }
                ]
            }
        else:
            result = {
                "identities": [{"character_id": data["characters"][0]["id"], "confirmed": True}],
                "claims": [
                    {
                        "local_key": "value",
                        "supported": True,
                        "identity_consistent": True,
                        "temporal_state": "current",
                        "baseline_supported": True,
                        "correction_supported": False,
                        "reason": "原文明确说明其价值观",
                        "access": [
                            {
                                "character_id": data["characters"][0]["id"],
                                "authorized": True,
                                "excerpt_safe": True,
                            }
                        ],
                    }
                ],
            }
        return LLMResponse(content=json.dumps(result, ensure_ascii=False))


@pytest.mark.asyncio
async def test_published_persona_has_only_its_evidence_and_no_generic_tools(book_library):
    item_id, parent_id = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item_id, parent_id, config)
    assert build["build_id"] != parent_id
    assert service.request_build(item_id, parent_id, config)["build_id"] == build["build_id"]
    catalog = BookDiscoveryService(book_library.workspace_root).list_characters(
        item_id, build["build_id"]
    )
    character_id = catalog["characters"][0]["id"]
    with pytest.raises(BookWorldError):
        service.get_agent_definition(item_id, build["build_id"], character_id)
    provider = PersonaProvider()
    await service.run(build["build_id"], provider, config)
    agent = service.get_agent_definition(item_id, build["build_id"], character_id)
    assert agent["baseline"]["value:诚信"]["proposition"] == "人物甲重视诚信"
    assert agent["persona"]["motivation"] == "unknown"
    assert agent["tools"] == []
    assert agent["scope"]["character_id"] == character_id
    assert agent["scope"]["build_id"] == build["build_id"]
    assert [entry["phase"] for entry in provider.inputs] == ["extract", "review"]
    assert (
        BookDiscoveryService(book_library.workspace_root).get_build(item_id, parent_id)["stage"]
        == "discovery_complete"
    )


class ScriptedPersonaProvider:
    def __init__(self, extract, review):
        self.extract, self.review = extract, review
        self.inputs = []

    async def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        self.inputs.append(data)
        result = self.extract(data) if data["phase"] == "extract" else self.review(data)
        return LLMResponse(content=json.dumps(result, ensure_ascii=False))


def quote(row, text):
    return {
        "segment_id": row["id"],
        "quote": text,
        "local_start": row["text"].index(text),
        "local_end": row["text"].index(text) + len(text),
    }


def review_all(data, **overrides):
    return {
        "identities": [
            {"character_id": person["id"], "confirmed": True} for person in data["characters"]
        ],
        "claims": [
            {
                "local_key": claim["local_key"],
                "supported": True,
                "identity_consistent": True,
                "temporal_state": "current",
                "baseline_supported": True,
                "correction_supported": True,
                "reason": "固定样本明确支持",
                "access": [
                    {
                        "character_id": grant["character_id"],
                        "authorized": True,
                        "excerpt_safe": True,
                    }
                    for grant in claim.get("access", [])
                ],
                **overrides,
            }
            for claim in data["proposals"]["claims"]
        ],
    }


@pytest.mark.asyncio
async def test_secret_world_fact_is_not_granted_and_unsafe_quote_is_omitted(book_library):
    text = "人物甲说：我最看重诚信。旁白：人物乙暗中藏起钥匙，人物甲并不知道。"
    item, parent = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "active"))
    )
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)

    def extract(data):
        alpha = next(person["id"] for person in data["characters"] if person["name"] == "人物甲")
        proof = quote(data["segments"][0], text)
        return {
            "claims": [
                {
                    "local_key": "value",
                    "kind": "trait",
                    "owner_character_id": alpha,
                    "proposition": "人物甲重视诚信",
                    "slot_key": "value:诚信",
                    "evidence": [proof],
                    "access": [
                        {
                            "character_id": alpha,
                            "route": "firsthand",
                            "acquisition": proof,
                            "approved_excerpt": text,
                        }
                    ],
                },
                {
                    "local_key": "secret",
                    "kind": "fact",
                    "proposition": "人物乙藏起钥匙",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "common", "acquisition": proof}],
                },
            ]
        }

    def review(data):
        result = review_all(data)
        result["claims"][0]["access"][0]["excerpt_safe"] = False
        result["claims"][1]["access"][0]["authorized"] = False
        return result

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    alpha = next(
        row
        for row in service.discovery.list_characters(item, build["build_id"])["characters"]
        if row["name"] == "人物甲"
    )
    agent = service.get_agent_definition(item, build["build_id"], alpha["id"])
    assert "藏起钥匙" not in json.dumps(agent, ensure_ascii=False)
    assert all(
        entry["approved_excerpt"] == "" for entry in agent["baseline"]["value:诚信"]["evidence"]
    )
    details = service.get_character(item, build["build_id"], alpha["id"])
    secret = next(claim for claim in details["reader"]["claims"] if claim["kind"] == "fact")
    assert secret["access"][0]["access_state"] == "revoked"
    assert "藏起钥匙" not in json.dumps(details["public"], ensure_ascii=False)


@pytest.mark.asyncio
async def test_explicit_belief_correction_selects_new_baseline_without_changing_truth(book_library):
    first = "人物甲曾坚信钥匙在箱中。"
    last = "人物甲醒悟：钥匙不在箱中，我先前错了。"
    item, parent = await discovered(book_library, first + "\n" + last)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)

    def extract(data):
        alpha = data["characters"][0]["id"]
        claims = []
        for key, text, prop in [("old", first, "钥匙在箱中"), ("new", last, "钥匙不在箱中")]:
            row = next(row for row in data["segments"] if row["text"] == text)
            proof = quote(row, text)
            claims.append(
                {
                    "local_key": key,
                    "kind": "belief",
                    "owner_character_id": alpha,
                    "proposition": prop,
                    "truth_state": "false" if key == "old" else "true",
                    "slot_key": "belief:钥匙位置",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                    **({"supersedes_local_key": "old"} if key == "new" else {}),
                }
            )
        return {"claims": claims}

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review_all), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    agent = service.get_agent_definition(item, build["build_id"], person["id"])
    assert agent["baseline"]["belief:钥匙位置"]["proposition"] == "钥匙不在箱中"
    original = service.get_character(item, build["build_id"], person["id"])["reader"]["claims"]
    assert original[0]["truth_state"] == "false"
    assert original[1]["supersedes_claim_id"] == original[0]["id"]


@pytest.mark.asyncio
async def test_unknown_story_order_does_not_use_last_text_as_current_belief(book_library):
    item, parent = await discovered(book_library, "人物甲说：我最看重诚信。")
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)

    def extract(data):
        alpha = data["characters"][0]["id"]
        proof = quote(data["segments"][0], "人物甲说：我最看重诚信。")
        return {
            "claims": [
                {
                    "local_key": key,
                    "kind": "belief",
                    "owner_character_id": alpha,
                    "proposition": prop,
                    "slot_key": "belief:选择",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
                for key, prop in [("earlier", "旧信念"), ("later", "另一个信念")]
            ]
        }

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review_all), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    assert (
        service.get_agent_definition(item, build["build_id"], person["id"])["persona"]["beliefs"]
        == "unknown"
    )
    assert service.discovery.get_build(item, build["build_id"])["status"] == "partial_published"


@pytest.mark.asyncio
async def test_published_canon_and_agent_definition_are_frozen_and_scoped(book_library):
    import sqlite3

    from backend.services.book_world.storage import connect

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    await service.run(build["build_id"], PersonaProvider(), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    for sql in [
        "UPDATE book_claims SET proposition='改写' WHERE build_id=?",
        "DELETE FROM book_character_baselines WHERE build_id=?",
        "UPDATE book_characters SET runtime_policy_json='{}' WHERE build_id=?",
        "UPDATE book_build_steps SET result_json='{}' WHERE build_id=?",
    ]:
        with pytest.raises(sqlite3.IntegrityError), connect(service.db_path) as db:
            db.execute(sql, (build["build_id"],))
    other, _ = await discovered(book_library)
    with pytest.raises(BookWorldError):
        service.get_agent_definition(other, build["build_id"], person["id"])


@pytest.mark.asyncio
async def test_persona_progress_counts_only_validated_units_and_failure_is_partial(book_library):
    item, parent = await discovered(book_library, "人物甲说：我最看重诚信。\n人物甲在山中行走。")
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1, model="fixture", unit_char_limit=4000, unit_segment_limit=1
    )
    build = service.request_build(item, parent, config)
    assert build["processed_segments"] == build["completed_units"] == 0

    class PartiallyBroken(PersonaProvider):
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            if data["unit_key"] == "1":
                self.inputs.append(data)
                return LLMResponse(content='{"bad":"shape"}')
            return await super().chat(messages, **kwargs)

    await service.run(build["build_id"], PartiallyBroken(), config)
    final = service.discovery.get_build(item, build["build_id"])
    assert final["status"] == "partial_published"
    assert final["processed_segments"] == 1
    assert final["total_segments"] == 2
    assert final["publication_report"]["failed_units"] == ["1"]


@pytest.mark.asyncio
async def test_historical_belief_does_not_compete_with_supported_current_slot(book_library):
    first, last = "人物甲从前相信钥匙在箱中。", "人物甲如今明白钥匙不在箱中。"
    item, parent = await discovered(book_library, first + "\n" + last)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)

    def extract(data):
        alpha = data["characters"][0]["id"]
        return {
            "claims": [
                {
                    "local_key": key,
                    "kind": "belief",
                    "owner_character_id": alpha,
                    "proposition": prop,
                    "slot_key": "belief:钥匙位置",
                    "evidence": [quote(data["segments"][index], text)],
                    "access": [
                        {
                            "character_id": alpha,
                            "route": "firsthand",
                            "acquisition": quote(data["segments"][index], text),
                        }
                    ],
                }
                for index, (key, text, prop) in enumerate(
                    [("past", first, "钥匙在箱中"), ("now", last, "钥匙不在箱中")]
                )
            ]
        }

    def review(data):
        result = review_all(data)
        result["claims"][0].update(temporal_state="historical", baseline_supported=False)
        return result

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    assert (
        service.get_agent_definition(item, build["build_id"], person["id"])["baseline"][
            "belief:钥匙位置"
        ]["proposition"]
        == "钥匙不在箱中"
    )


@pytest.mark.asyncio
async def test_death_evidence_is_carried_between_units_and_blocks_even_common_grant(book_library):
    death, event = "人物甲去世了。", "人物甲的故乡人人知晓新的桥建好了。"
    item, parent = await discovered(book_library, death + "\n" + event)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1, model="fixture", unit_char_limit=4000, unit_segment_limit=1
    )
    build = service.request_build(item, parent, config)

    def extract(data):
        if data["unit_key"] == "0":
            return {"claims": []}
        person = data["characters"][0]["id"]
        assert data["known_life_states"][person]["state"] == "dead"
        proof = quote(data["segments"][0], event)
        return {
            "claims": [
                {
                    "local_key": "bridge",
                    "kind": "fact",
                    "proposition": "新的桥建好了",
                    "evidence": [proof],
                    "access": [{"character_id": person, "route": "common", "acquisition": proof}],
                }
            ]
        }

    def review(data):
        result = review_all(data)
        if data["unit_key"] == "0":
            result["life_events"] = [
                {
                    "character_id": data["characters"][0]["id"],
                    "state": "dead",
                    "temporal_state": "current",
                    "evidence": quote(data["segments"][0], death),
                }
            ]
        return result  # Even an erroneously authorized review cannot override the known death boundary.

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    detail = service.get_character(item, build["build_id"], person["id"])
    fact = next(row for row in detail["reader"]["claims"] if row["kind"] == "fact")
    assert fact["access"][0]["access_state"] == "revoked"
    agent = service.get_agent_definition(item, build["build_id"], person["id"])
    assert "桥建好了" not in json.dumps(agent, ensure_ascii=False)


@pytest.mark.asyncio
async def test_cancelled_late_semantic_review_never_publishes(book_library):
    import asyncio

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    started, release = asyncio.Event(), asyncio.Event()

    class SlowReview(PersonaProvider):
        async def chat(self, messages, **kwargs):
            if json.loads(messages[-1]["content"])["phase"] == "review":
                started.set()
                await release.wait()
            return await super().chat(messages, **kwargs)

    task = asyncio.create_task(service.run(build["build_id"], SlowReview(), config))
    await asyncio.wait_for(started.wait(), 5)
    service.control(item, build["build_id"], "cancel")
    release.set()
    await task
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    assert service.get_character(item, build["build_id"], person["id"])["reader"]["claims"] == []
    with pytest.raises(BookWorldError):
        service.get_agent_definition(item, build["build_id"], person["id"])


@pytest.mark.asyncio
async def test_publish_failure_rolls_back_profiles_and_baselines(book_library):
    from backend.services.book_world.storage import connect

    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    with connect(service.db_path) as db:
        db.execute(
            "CREATE TRIGGER fail_publication BEFORE UPDATE OF status ON book_builds WHEN NEW.status='published' BEGIN SELECT RAISE(ABORT,'disk failure fixture'); END"
        )
    await service.run(build["build_id"], PersonaProvider(), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    assert person["agent_status"] == "candidate"
    assert service.get_character(item, build["build_id"], person["id"])["reader"]["baseline"] == {}
    assert service.discovery.get_build(item, build["build_id"])["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad", ["private_other", "foreign_owner", "fabricated_quote", "semantic_reject"]
)
async def test_invalid_or_unsupported_persona_never_becomes_an_authorized_baseline(
    book_library, bad
):
    text = "人物甲说：我最看重诚信。人物乙在旁听着。"
    item, parent = await discovered(
        book_library, text, (("人物甲", "active"), ("人物乙", "silent"))
    )
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)

    def extract(data):
        alpha = next(person["id"] for person in data["characters"] if person["name"] == "人物甲")
        beta = next(person["id"] for person in data["characters"] if person["name"] == "人物乙")
        proof = quote(data["segments"][0], text)
        claim = {
            "local_key": "bad",
            "kind": "trait",
            "owner_character_id": alpha,
            "proposition": "人物甲有飞行能力",
            "slot_key": "trait:能力",
            "evidence": [proof],
            "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
        }
        if bad == "private_other":
            claim["owner_character_id"] = beta
        if bad == "foreign_owner":
            claim["owner_character_id"] = "foreign-character"
        if bad == "fabricated_quote":
            claim["evidence"][0] = {**proof, "quote": "人物甲能飞行"}
        return {"claims": [claim]}

    provider = ScriptedPersonaProvider(extract, lambda data: review_all(data, supported=False))
    await service.run(build["build_id"], provider, config)
    people = service.discovery.list_characters(item, build["build_id"])["characters"]
    alpha = next(person for person in people if person["name"] == "人物甲")
    assert service.get_character(item, build["build_id"], alpha["id"])["reader"]["baseline"] == {}
    if bad == "semantic_reject":
        assert service.discovery.get_build(item, build["build_id"])["status"] == "partial_published"
        assert (
            service.get_agent_definition(item, build["build_id"], alpha["id"])["persona"]["traits"]
            == "unknown"
        )
    else:
        with pytest.raises(BookWorldError):
            service.get_agent_definition(item, build["build_id"], alpha["id"])


@pytest.mark.asyncio
async def test_explicit_pre_death_memory_can_be_authorized_but_does_not_invent_current_state(
    book_library,
):
    death, memory = "人物甲去世了。", "回忆人物甲生前曾说：我最看重诚信。"
    item, parent = await discovered(book_library, death + "\n" + memory)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1, model="fixture", unit_char_limit=4000, unit_segment_limit=1
    )
    build = service.request_build(item, parent, config)

    def extract(data):
        if data["unit_key"] == "0":
            return {"claims": []}
        alpha = data["characters"][0]["id"]
        proof = quote(data["segments"][0], memory)
        return {
            "claims": [
                {
                    "local_key": "past",
                    "kind": "belief",
                    "owner_character_id": alpha,
                    "proposition": "重视诚信",
                    "slot_key": "belief:诚信",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "firsthand", "acquisition": proof}],
                }
            ]
        }

    def review(data):
        result = review_all(data)
        if data["unit_key"] == "0":
            result["life_events"] = [
                {
                    "character_id": data["characters"][0]["id"],
                    "state": "dead",
                    "temporal_state": "current",
                    "evidence": quote(data["segments"][0], death),
                }
            ]
        else:
            result["claims"][0].update(temporal_state="historical", baseline_supported=False)
            result["claims"][0]["access"][0].update(
                before_death=True, before_death_evidence=quote(data["segments"][0], memory)
            )
        return result

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    details = service.get_character(item, build["build_id"], person["id"])
    belief = next(row for row in details["reader"]["claims"] if row["kind"] == "belief")
    assert belief["access"][0]["access_state"] == "accepted"
    assert details["reader"]["baseline"] == {}


@pytest.mark.asyncio
async def test_current_resurrection_survives_later_flashback_to_historical_death(book_library):
    lines = [
        "人物甲去世了。",
        "人物甲明确复活，开始了新的生活。",
        "追述人物甲昔日去世的往事。",
        "人物甲亲眼见到新桥建好了。",
    ]
    item, parent = await discovered(book_library, "\n".join(lines))
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(
        provider_id=1, model="fixture", unit_char_limit=4000, unit_segment_limit=1
    )
    build = service.request_build(item, parent, config)

    def extract(data):
        if data["unit_key"] != "3":
            return {"claims": []}
        alpha = data["characters"][0]["id"]
        assert data["known_life_states"][alpha]["state"] == "alive"
        proof = quote(data["segments"][0], lines[3])
        return {
            "claims": [
                {
                    "local_key": "bridge",
                    "kind": "fact",
                    "proposition": "新桥建好了",
                    "evidence": [proof],
                    "access": [{"character_id": alpha, "route": "observed", "acquisition": proof}],
                }
            ]
        }

    def review(data):
        result = review_all(data)
        unit = int(data["unit_key"])
        if unit < 3:
            result["life_events"] = [
                {
                    "character_id": data["characters"][0]["id"],
                    "state": "alive" if unit == 1 else "dead",
                    "temporal_state": "historical" if unit == 2 else "current",
                    "resurrection_supported": unit == 1,
                    "evidence": quote(data["segments"][0], lines[unit]),
                }
            ]
        return result

    await service.run(build["build_id"], ScriptedPersonaProvider(extract, review), config)
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    fact = next(
        row
        for row in service.get_character(item, build["build_id"], person["id"])["reader"]["claims"]
        if row["kind"] == "fact"
    )
    assert fact["access"][0]["access_state"] == "accepted"


@pytest.mark.asyncio
async def test_changed_source_snapshot_blocks_final_publication(book_library):
    item, parent = await discovered(book_library)
    service = BookPersonaService(book_library.workspace_root)
    config = PersonaConfig(provider_id=1, model="fixture", unit_char_limit=4000)
    build = service.request_build(item, parent, config)
    version = build["source_version_id"]
    segment = service.source.list_segments(item, version)["segments"][0]
    locator = service.source.resolve_evidence(item, version, segment["id"])

    class CorruptAfterReview(PersonaProvider):
        async def chat(self, messages, **kwargs):
            result = await super().chat(messages, **kwargs)
            if json.loads(messages[-1]["content"])["phase"] == "review":
                (book_library.workspace_root / locator["asset_path"]).write_bytes(
                    b"changed snapshot"
                )
            return result

    await service.run(build["build_id"], CorruptAfterReview(), config)
    final = service.discovery.get_build(item, build["build_id"])
    assert final["status"] == "failed"
    assert final["error_code"] == "source_changed"
    person = service.discovery.list_characters(item, build["build_id"])["characters"][0]
    with pytest.raises(BookWorldError):
        service.get_agent_definition(item, build["build_id"], person["id"])
