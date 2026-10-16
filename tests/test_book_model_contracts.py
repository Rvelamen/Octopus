"""Regression seams for literal discovery identity and complete reply review transport."""

import json

import pytest
from test_book_discovery import story
from test_book_knowledge import style_character
from test_book_rooms import empty_review

from backend.core.providers.base import LLMResponse
from backend.services.book_world.chat_worker import BookChatWorker
from backend.services.book_world.discovery import BookDiscoveryService, DiscoveryConfig
from backend.services.book_world.room_models import CharacterChatConfig
from backend.services.book_world.rooms import BookRoomService
from backend.services.book_world.rounds import BookRoundService


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["character-chat-v13", "character-chat-v14"])
async def test_current_repair_feedback_covers_missing_refs_and_scoped_inference_before_publication(book_library, version):
    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="v13-inference-repair")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version=version, review_prompt_version="character-chat-review-v9")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "hypothetical", "假设我想慢慢讲，你会怎样回应？", config, time_limit_seconds=60)
    calls = []
    published = "如果你想慢慢说，我会耐心听你讲。"

    class Repair:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data)
            proof = next(iter(data["context"]["baseline"].values()))
            if len(calls) == 1:
                assert data["phase"] == "generate"
                reply = {"content":published+"这只是本次设想。", "dialogue_action":"answer", "claims":[{"text":published,"origin":"inference"},{"text":"这只是本次设想。","origin":"inference"}]}
            elif len(calls) == 2:
                assert data["phase"] == "generate"
                feedback = data["feedback"]
                assert all(word in feedback for word in ("claims.0", "claims.1", "inference", "refs", "conversation"))
                assert "input_value" not in feedback
                assert not [m for m in rooms.read_messages(scope)["messages"] if m["speaker_type"] == "character"]
                reply = {"content":published,"dialogue_action":"answer","action_basis_claim_ids":[proof["claim_id"]],"claims":[{"text":published,"origin":"inference","refs":[{"claim_id":proof["claim_id"],"evidence_id":proof["evidence_id"]}]}]}
            else:
                assert data["phase"] == "review"
                assert "claims" not in data["candidate"]
                assert data["review_claims"][0]["ordinal"] == 0
                reply = {**empty_review(), "claims":[{"ordinal":0,"supported":True,"origin_correct":True,"references_complete":True}]}
            return LLMResponse(content=json.dumps(reply,ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], Repair(), config)
    assert [call["phase"] for call in calls] == ["generate", "generate", "review"]
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
    replies = [m for m in rooms.read_messages(scope)["messages"] if m["speaker_type"] == "character"]
    assert len(replies) == 1 and replies[0]["content"] == published


@pytest.mark.asyncio
async def test_model_context_uses_current_literal_alias_without_renaming_canonical_candidate(
    book_library,
):
    item, source = story(book_library, "美猴王也称猴王。" + "走" * 119 + "。\n猴王继续行走。")
    discovery = BookDiscoveryService(book_library.workspace_root)
    config = DiscoveryConfig(
        provider_id=1, model="fixture", unit_char_limit=128, prompt_version="character-discovery-v7"
    )
    build = discovery.create_build(item, source, config)
    seen = []

    class LiteralIdentityProvider:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            segment = data["segments"][0]
            known = data["known_characters"]
            name = known[0]["name"] if known else "美猴王"
            quote = "猴王继续行走。" if known else "美猴王也称猴王。"
            span = {
                "segment_id": segment["id"],
                "local_start": 0,
                "local_end": len(quote),
                "quote": quote,
            }
            person = {
                "name": name,
                "local_character_key": "monkey",
                "presence": "active",
                "evidence": span,
            }
            if known:
                person.update(identity="existing", existing_character_id=known[0]["id"])
            else:
                person["aliases"] = [{"alias": "猴王", "evidence": span}]
            return LLMResponse(
                content=json.dumps(
                    {
                        "scenes": [
                            {
                                "segment_ids": [r["id"] for r in data["segments"]],
                                "characters": [person],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )

    await discovery.run(build["build_id"], LiteralIdentityProvider(), config)
    result = discovery.get_build(item, build["build_id"])
    assert result["stage"] == "discovery_complete"
    people = discovery.list_characters(item, build["build_id"])["characters"]
    assert len(people) == 1 and people[0]["name"] == "美猴王"
    assert len(people[0]["appearances"]) == 2
    assert len(seen) == 2
    assert seen[1]["known_characters"][0]["name"] == "猴王"


@pytest.mark.asyncio
async def test_nonbelief_reference_feedback_explains_the_actual_kind_and_repairs_the_label(book_library):
    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="source-kind-feedback")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v14", review_prompt_version="character-chat-review-v9")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "style", "请说说你的说话方式。", config, time_limit_seconds=60)
    calls = []
    body = "我说话平和简短。"

    class Repair:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data)
            proof = next(iter(data["context"]["baseline"].values()))
            if data["phase"] == "generate":
                if len(calls) == 2:
                    assert all(word in data["feedback"] for word in ("kind=style", "canon", "inference", "character_belief"))
                reply = {"content":body,"dialogue_action":"answer","claims":[{"text":body,"origin":"character_belief" if len(calls)==1 else "canon","refs":[{"claim_id":proof["claim_id"],"evidence_id":proof["evidence_id"]}]}]}
            else:
                reply = {**empty_review(),"claims":[{"ordinal":0,"supported":True,"origin_correct":True,"references_complete":True}]}
            return LLMResponse(content=json.dumps(reply,ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(scope, turn["round_id"], Repair(), config)
    assert [call["phase"] for call in calls] == ["generate", "generate", "review"]
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
    assert [m["content"] for m in rooms.read_messages(scope)["messages"] if m["speaker_type"]=="character"] == [body]


@pytest.mark.asyncio
async def test_versioned_review_receives_explicit_assertion_indices_and_publishes_without_rewrite(
    book_library,
):
    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="explicit-review-indices")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1, model="fixture", review_prompt_version="character-chat-review-v4"
    )
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(
        scope, "heard-facts", "我代号是青禾，我喜欢下雨。", config, time_limit_seconds=60
    )
    seen = []
    reply = "你说代号是青禾，也说喜欢下雨。"

    class IndexedReviewer:
        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if data["phase"] == "generate":
                message = data["context"]["current_message"]["id"]
                result = {
                    "content": reply,
                    "dialogue_action": "answer",
                    "claims": [
                        {"text": text, "origin": "room_hearsay", "message_ids": [message]}
                        for text in ("代号是青禾", "喜欢下雨")
                    ],
                }
            else:
                result = empty_review()
                # A reviewer should copy input indices instead of guessing whether
                # the human-readable list starts at one, as the native trace did.
                indexed = data.get(
                    "review_claims",
                    [{"ordinal": i + 1} for i, _ in enumerate(data["candidate"]["claims"])],
                )
                result["claims"] = [
                    {
                        "ordinal": entry["ordinal"],
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                    for entry in indexed
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], IndexedReviewer(), config
    )
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
    assert rooms.read_messages(scope)["messages"][-1]["content"] == reply
    assert len(seen) == 2
    assert [entry["ordinal"] for entry in seen[1]["review_claims"]] == [0, 1]
    assert [entry["assertion"] for entry in seen[1]["review_claims"]] == seen[1]["candidate"][
        "claims"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("question,denial,faithful", [
    ("我猜想那不是你亲眼见过的场景。", "你猜想那不是我亲眼见过的场景", True),
    ("我说电灯能照亮夜路。", "你猜想那不是我亲眼见过的场景", False),
    ("我说“你从未见过电灯”这句话不成立。", "你说我从未见过电灯", False),
    ("我说你从未见过电灯，这句话不成立。", "你说我从未见过电灯", False),
    ("我说你从未见过电灯。刚才这句话不成立。", "你说我从未见过电灯", False),
])
@pytest.mark.parametrize("version", ["character-chat-v12", "character-chat-v13", "character-chat-v14"])
async def test_unquoted_user_denial_remains_hearsay_only_when_the_public_source_matches(book_library, question, denial, faithful, version):
    from backend.services.book_world.chat_validation import validate_candidate
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.discovery import _json

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="attributed-denial")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version=version)
    turn = BookRoundService(book_library.workspace_root).submit(scope, "attributed", question, config, time_limit_seconds=60)
    context = CharacterContextBuilder(book_library.workspace_root).compose(scope, turn["round_id"], room["members"][0]["id"])
    content = denial + "；我无法确认。"
    raw = _json({"content": content, "dialogue_action": "answer", "claims": [
        {"text": denial, "origin": "room_hearsay", "message_ids": [context.payload["current_message"]["id"]]},
        {"text": "我无法确认。", "origin": "conversation"},
    ]})
    if faithful:
        assert validate_candidate(raw, context).content == content
    else:
        with pytest.raises(ValueError, match="Negative experience"):
            validate_candidate(raw, context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["format_once", "semantic_once", "mixed_once", "details_once", "format_always"]
)
async def test_review_repair_is_bounded_and_does_not_weaken_body_validation(book_library, failure):
    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="bounded-review-repair")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        review_prompt_version="character-chat-review-v6"
        if failure == "details_once"
        else "character-chat-review-v4",
    )
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "heard-question", "我代号是青禾。", config, time_limit_seconds=60)
    calls = []
    reply = "你说代号是青禾。"

    class RepairReviewer:
        reviews = 0

        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data)
            if data["phase"] == "generate":
                if failure == "details_once" and calls.count(data) == 1 and len(calls) > 1:
                    assert "不支持的先后关系" in data["feedback"]
                result = {
                    "content": reply,
                    "dialogue_action": "answer",
                    "claims": [
                        {
                            "text": "代号是青禾",
                            "origin": "room_hearsay",
                            "message_ids": [data["context"]["current_message"]["id"]],
                        }
                    ],
                }
            else:
                self.reviews += 1
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": entry["ordinal"],
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                    for entry in data["review_claims"]
                ]
                if failure == "format_always" or (self.reviews == 1 and failure == "format_once"):
                    result["claims"] = [
                        {
                            "ordinal": 1,
                            "supported": True,
                            "origin_correct": True,
                            "references_complete": True,
                        }
                    ]
                elif self.reviews == 1 and failure == "semantic_once":
                    result["supported"] = False
                elif self.reviews == 1 and failure == "mixed_once":
                    result["claims"][0].update(ordinal=1, supported=False)
                elif self.reviews == 1 and failure == "details_once":
                    result.update(
                        supported=False, reason="不支持的先后关系", unlisted_assertions=["此后"]
                    )
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], RepairReviewer(), config
    )
    generated = [call for call in calls if call["phase"] == "generate"]
    reviewed = [call for call in calls if call["phase"] == "review"]
    assert len(calls) <= 5 and len(generated) <= 2 and len(reviewed) <= 3
    messages = rooms.read_messages(scope)["messages"]
    if failure == "format_always":
        assert len(messages) == 1
        assert (
            rounds.get_round(scope, turn["round_id"])["error_code"] == "fallback_validation_failed"
        )
    else:
        assert messages[-1]["content"] == reply
        assert len(generated) == (1 if failure == "format_once" else 2)
        assert len(reviewed) == 2
    if failure == "format_once":
        assert reviewed[0]["candidate"] == reviewed[1]["candidate"]
        assert "zero-based" in reviewed[1]["feedback"]


def test_versioned_discovery_keeps_legacy_snapshot_and_excludes_ambiguous_aliases():
    from copy import deepcopy

    from backend.services.book_world.discovery_models import discovery_model_input

    original = {
        "segments": [],
        "known_characters": [
            {
                "id": "c",
                "name": "美猴王",
                "aliases": [
                    {"alias": "猴王", "review_state": "candidate"},
                    {"alias": "那猴", "review_state": "ambiguous"},
                ],
            }
        ],
    }
    frozen = deepcopy(original)
    assert discovery_model_input(original, "character-discovery-v6") == frozen
    current = discovery_model_input(original, "character-discovery-v7")
    assert current["known_characters"] == [
        {"id": "c", "name": "猴王", "aliases": [{"alias": "猴王", "review_state": "candidate"}]}
    ]
    assert original == frozen


@pytest.mark.asyncio
async def test_unlisted_body_and_certain_inference_cannot_hide_behind_an_approved_review(
    book_library,
):
    from backend.services.book_world.chat_validation import validate_candidate
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.discovery import _json

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="full-body-coverage")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version="character-chat-v8")
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "coverage", "我在本房间自称青禾。", config, time_limit_seconds=60)
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    heard = {
        "text": "你说自称青禾。",
        "origin": "room_hearsay",
        "message_ids": [context.payload["current_message"]["id"]],
    }
    body = {
        "content": "你说自称青禾。我在洞里见过明月。",
        "dialogue_action": "answer",
        "claims": [heard],
    }
    with pytest.raises(ValueError, match="Unreviewed body"):
        validate_candidate(_json(body), context)
    assert (
        validate_candidate(
            _json(
                {
                    **body,
                    "content": "你好。你说自称青禾。",
                    "claims": [{"text": "你好。", "origin": "conversation"}, heard],
                }
            ),
            context,
        ).content
        == "你好。你说自称青禾。"
    )
    proof = context.allowed[0]
    inference = {
        "content": "那洞府就在山门后。",
        "dialogue_action": "answer",
        "claims": [
            {
                "text": "那洞府就在山门后。",
                "origin": "inference",
                "refs": [{"claim_id": proof.claim_id, "evidence_id": proof.evidence_id}],
            }
        ],
    }
    with pytest.raises(ValueError, match="hypothetical"):
        validate_candidate(_json(inference), context)


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["character-chat-v10", "character-chat-v11", "character-chat-v12", "character-chat-v13", "character-chat-v14"])
async def test_negative_experience_needs_explicit_canonical_support_in_every_origin(book_library, version):
    from dataclasses import replace

    from backend.services.book_world.chat_validation import validate_candidate
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.discovery import _json

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="negative-experience-all-origins")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1, model="fixture", prompt_version=version
    )
    turn = BookRoundService(book_library.workspace_root).submit(
        scope, "negative", "我说电灯能照亮夜路。", config, time_limit_seconds=60
    )
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    proof = context.allowed[0]
    refs = [{"claim_id": proof.claim_id, "evidence_id": proof.evidence_id}]
    denials = [
        "并非我亲眼见过的物事。",
        "并没有什么住在月宫的事。",
        "我从未见过电灯。",
        "我还没细看。",
        "我从未听说电灯。",
    ]
    if version in ("character-chat-v12", "character-chat-v13", "character-chat-v14"):
        denials.extend(["这话是你告诉我的，不是我自己见过的。", "并不是我亲历过的事。"])
    for denied in denials:
        for origin in ["canon", "inference", "room_hearsay", "conversation"]:
            content = "如果你问，" + denied
            assertion = {"text": content, "origin": origin}
            if origin in ("canon", "inference"):
                assertion["refs"] = refs
            elif origin == "room_hearsay":
                assertion["message_ids"] = [context.payload["current_message"]["id"]]
            with pytest.raises(ValueError, match="Negative experience"):
                validate_candidate(
                    _json({"content": content, "dialogue_action": "answer", "claims": [assertion]}),
                    context,
                )
    for content, origin in [
        ("这原理我不清楚。", "conversation"),
        ("你说：‘我从未见过电灯。’", "room_hearsay"),
        ("如果我未曾见过那灯，我会先问明白。", "inference"),
        ("这个信息来自你，我无法独立确认。", "room_hearsay"),
        ("不能据此认作我的原著经历。", "conversation"),
        ("你说：‘这不是我自己见过的。’", "room_hearsay"),
        ("如果这不是我自己见过的，我会先问明白。", "inference"),
    ]:
        assertion = {"text": content, "origin": origin}
        if origin == "room_hearsay":
            assertion["message_ids"] = [context.payload["current_message"]["id"]]
        elif origin == "inference":
            assertion["refs"] = refs
        assert (
            validate_candidate(
                _json({"content": content, "dialogue_action": "answer", "claims": [assertion]}),
                context,
            ).content
            == content
        )
    # The source must support this whole denial, including its object. An
    # unrelated negative proposition is insufficient.
    content = "我未曾见过那灯。"
    assertion = {"text": content, "origin": "canon", "refs": refs}
    for proposition, excerpt, route, accepted in [
        (content, "", "firsthand", True),
        ("我未曾住过月宫。", "", "firsthand", False),
        ("老猴告诉石猴：‘我未曾见过那灯。’", content, "told", False),
        ("老猴告诉石猴：‘我未曾见过那灯。’", content, "firsthand", False),
        (content, "", "told", False),
    ]:
        supplied = replace(
            context,
            allowed=(
                proof.model_copy(
                    update={"proposition": proposition, "approved_excerpt": excerpt, "route": route}
                ),
            ),
        )
        raw = _json({"content": content, "dialogue_action": "answer", "claims": [assertion]})
        if accepted:
            assert validate_candidate(raw, supplied).content == content
        else:
            with pytest.raises(ValueError, match="Negative experience"):
                validate_candidate(raw, supplied)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version", ["character-chat-v6", "character-chat-v7", "character-chat-v8", "character-chat-v9", "character-chat-v10", "character-chat-v11", "character-chat-v12", "character-chat-v13", "character-chat-v14"]
)
async def test_silence_remains_valid_for_all_newer_chat_policies(book_library, version):
    from backend.services.book_world.chat_validation import validate_candidate
    from backend.services.book_world.context import CharacterContextBuilder
    from backend.services.book_world.discovery import _json

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="silence-policies")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(provider_id=1, model="fixture", prompt_version=version)
    turn = BookRoundService(book_library.workspace_root).submit(
        scope, "silence", "不必回答。", config, time_limit_seconds=60
    )
    context = CharacterContextBuilder(book_library.workspace_root).compose(
        scope, turn["round_id"], room["members"][0]["id"]
    )
    assert (
        validate_candidate(
            _json({"content": "", "dialogue_action": "no_comment"}), context
        ).dialogue_action
        == "no_comment"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("latest", [False, True])
@pytest.mark.parametrize("repair", [True, False])
@pytest.mark.parametrize("defect", ["unlisted", "negative", "negative_copula"])
async def test_full_body_guard_prevents_publishing_unlisted_fact_despite_positive_judge(
    book_library, repair, defect, latest
):
    from backend.services.book_world.chat_models import UNKNOWN_REPLY

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="unlisted-publish-guard")
    scope = rooms.bind_room(room["room_id"], 1)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        prompt_version="character-chat-v12" if latest else "character-chat-v10" if defect != "unlisted" else "character-chat-v8",
        review_prompt_version="character-chat-review-v8" if latest else "character-chat-review-v5",
    )
    rounds = BookRoundService(book_library.workspace_root)
    turn = rounds.submit(scope, "unlisted", "我自称青禾。", config, time_limit_seconds=60)
    calls = []
    supported = "你说自称青禾。"
    unsupported = {
        "negative": "我从未见过电灯。",
        "negative_copula": "这话是你告诉我的，不是我自己见过的。",
        "unlisted": "我在洞里见过明月。",
    }[defect]

    class MissingFact:
        generated = 0

        async def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]["content"])
            calls.append(data)
            if data["phase"] == "generate":
                self.generated += 1
                fixed = repair and self.generated == 2
                if self.generated == 2:
                    assert (
                        "Negative experience" if defect != "unlisted" else "Unreviewed body"
                    ) in data["feedback"]
                result = {
                    "content": supported if fixed else supported + unsupported,
                    "dialogue_action": "answer",
                    "claims": [
                        {
                            "text": supported,
                            "origin": "room_hearsay",
                            "message_ids": [data["context"]["current_message"]["id"]],
                        }
                    ],
                }
                if defect != "unlisted" and not fixed:
                    result["claims"].append({"text": unsupported, "origin": "conversation"})
            else:
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": entry["ordinal"],
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                    for entry in data["review_claims"]
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], MissingFact(), config
    )
    if defect == "negative_copula" and not latest:
        assert len(calls) == 2
        assert rooms.read_messages(scope)["messages"][-1]["content"] == supported + unsupported
        return
    assert len(calls) == 3 and [call["phase"] for call in calls] == [
        "generate",
        "generate",
        "review",
    ]
    published = rooms.read_messages(scope)["messages"][-1]
    assert published["content"] == (supported if repair else UNKNOWN_REPLY)
    assert "明月" not in published["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("review_version", ["character-chat-review-v5", "character-chat-review-v6", "character-chat-review-v7", "character-chat-review-v8", "character-chat-review-v9"])
async def test_compact_review_budget_keeps_claim_sources_and_generation_context_intact(
    book_library,
    review_version,
):
    import hashlib

    from backend.services.book_world.discovery import _json
    from backend.services.book_world.storage import connect

    actor = (await style_character(book_library))[3]
    rooms = BookRoomService(book_library.workspace_root)
    room = rooms.create_single_room(actor, client_room_id="review-budget")
    scope = rooms.bind_room(room["room_id"], 1)
    rounds = BookRoundService(book_library.workspace_root)
    config = CharacterChatConfig(
        provider_id=1,
        model="fixture",
        prompt_version="character-chat-v8",
        review_prompt_version=review_version,
        context_window=32768,
        max_tokens=4096,
    )
    for index in range(48):
        previous = rounds.submit(
            scope, f"old-{index}", "旧的闲聊" + "风" * 180, config, time_limit_seconds=60
        )
        rounds.control(scope, previous["round_id"], "cancel")
    facts = [f"第{index}条约定是" + "海" * 250 + "。" for index in range(4)]
    previous = rounds.submit(scope, "source", "".join(facts), config, time_limit_seconds=60)
    rounds.control(scope, previous["round_id"], "cancel")
    source = rooms.read_messages(scope, limit=100)["messages"][-1]["id"]
    turn = rounds.submit(scope, "repeat", "请复述最后的约定。", config, time_limit_seconds=60)
    claims = [
        {"text": "你说" + fact, "origin": "room_hearsay", "message_ids": [source]} for fact in facts
    ]
    body = "".join(item["text"] for item in claims)
    seen = []

    class LargeReply:
        async def chat(self, messages, **kwargs):
            assert (
                sum(len(item["content"].encode()) for item in messages) + kwargs["max_tokens"]
                <= config.context_window
            )
            data = json.loads(messages[-1]["content"])
            seen.append(data)
            if data["phase"] == "generate":
                result = {"content": body, "dialogue_action": "answer", "claims": claims}
            else:
                assert "claims" not in data["candidate"]
                assert source in {item["id"] for item in data["context"]["room_history"]}
                result = empty_review()
                result["claims"] = [
                    {
                        "ordinal": entry["ordinal"],
                        "supported": True,
                        "origin_correct": True,
                        "references_complete": True,
                    }
                    for entry in data["review_claims"]
                ]
            return LLMResponse(content=json.dumps(result, ensure_ascii=False))

    await BookChatWorker(book_library.workspace_root).run(
        scope, turn["round_id"], LargeReply(), config
    )
    assert rounds.get_round(scope, turn["round_id"])["status"] == "completed"
    assert (
        len(seen) == 2 and rooms.read_messages(scope, limit=100)["messages"][-1]["content"] == body
    )
    with connect(rooms.db_path) as db:
        display = json.loads(
            db.execute(
                "SELECT display_snapshot_json FROM book_room_messages WHERE round_id=? AND speaker_type='character'",
                (turn["round_id"],),
            ).fetchone()[0]
        )["generation"]
    assert display["review_omitted_history"] > 0
    assert (
        display["context_sha256"] == hashlib.sha256(_json(seen[0]["context"]).encode()).hexdigest()
    )
    assert (
        display["review_context_sha256"]
        == hashlib.sha256(_json(seen[1]["context"]).encode()).hexdigest()
    )


def test_v9_review_and_v14_generate_pin_historical_action_safeguard():
    """v9 review and v14 generate must keep the trait/intention safeguard text.

    The historical-action safeguard prevents a trait (e.g. "勇敢、敢于率先进入")
    from being used to assert completed actions or knowledge changes. It must
    survive prompt edits; otherwise the v8/9 review alone would re-introduce the
    '率先进入 ⇒ 群猴观看' and '勇敢 ⇒ 已完成动作' patterns that v7 acquisition
    review already blocks at the persona level.
    """
    from backend.services.book_world.chat_models import GENERATE_PROMPTS, REVIEW_PROMPTS

    v9_review = REVIEW_PROMPTS["character-chat-review-v9"]
    assert "勇敢" in v9_review and "率先进入" in v9_review
    assert "不额外证明" in v9_review and "认识变化" in v9_review
    assert "愿意/敢于/想要/说要去" in v9_review
    assert "区分意向、发生和结果" in v9_review
    assert "不从故事常识补齐" in v9_review

    v8_review = REVIEW_PROMPTS["character-chat-review-v8"]
    assert v8_review in v9_review, "v9 review must extend v8; safeguard is an addition"

    v14_generate = GENERATE_PROMPTS["character-chat-v14"]
    assert "愿意/敢于/想要/说要做" in v14_generate
    assert "不证明已经做成或看到了什么" in v14_generate


def test_v9_review_pins_cognition_change_safeguard():
    """v9 review must keep the cognition-change, past-conditional and current-choice paragraphs.

    v9 review introduced three new safeguards on top of v8:
      - "原著的认识变化也是事实": a "later found out X" line is itself a
        fact, not a hedge; the review must require a supporting claim
        rather than treat the phrasing as rhetoric.
      - "嵌在过去经历中的'有没有X/是否X'": past-tense yes/no probes must
        not be auto-released just because they sound like open questions
        when the body already says the answer is known.
      - "新处境的条件性选择": conditional choices under a new situation
        can rest on existing character, not on the same route or the
        same question appearing in the source.

    Without these paragraphs the v9 review can re-allow past-knowledge
    denials and over-restrict conditional choice questions, both of
    which the conditional-positive/negative diagnostics were built to
    distinguish.
    """
    from backend.services.book_world.chat_models import REVIEW_PROMPTS

    v9 = REVIEW_PROMPTS["character-chat-review-v9"]
    assert "原著的认识变化也是事实" in v9
    assert "后来才知道X" in v9 or "亲眼查看后才明白X" in v9
    assert "嵌在过去经历中的" in v9
    assert "新处境的条件性选择" in v9
    v8 = REVIEW_PROMPTS["character-chat-review-v8"]
    # Sanity: the new paragraphs are additions, not in v8.
    assert "新处境的条件性选择" not in v8


def test_persona_extract_v4_and_review_v6_pin_trait_vs_completed_action_safeguard():
    """v4 extract and v6 review must keep the trait/intention-vs-action safeguard.

    The matrix v2 T17 review surfaced a 'source strength warning': a model using
    the v3 default extracted a trait '石猴勇敢果断，敢于率先跳入瀑布泉中探险'
    from evidence '我进去！', and the v9 chat review still accepted the trait for
    a historical-action claim. v4 extract and v6 persona review both contain
    explicit safeguards against this conflation; they must survive prompt edits
    so a future v3 default does not silently re-introduce the issue.
    """
    from backend.services.book_world.persona_models import EXTRACT_PROMPTS, REVIEW_PROMPTS

    v3_extract = EXTRACT_PROMPTS["persona-extract-v3"]
    assert "主动表示愿意进入" not in v3_extract, "v3 base should not pre-empt v4 safeguard"

    v4_extract = EXTRACT_PROMPTS["persona-extract-v4"]
    assert v3_extract in v4_extract, "v4 must extend v3; safeguard is an addition"
    assert "本人台词" in v4_extract and "我进去" in v4_extract
    assert "不证明实际做成、看见、获知或得到结果" in v4_extract
    assert "主动表示愿意进入" in v4_extract
    assert "敢于率先跳入" in v4_extract
    assert "容易被误读为已完成动作" in v4_extract
    assert "episode另需原文明示实际发生" in v4_extract

    v5_review = REVIEW_PROMPTS["persona-review-v5"]
    v6_review = REVIEW_PROMPTS["persona-review-v6"]
    assert v5_review in v6_review, "v6 must extend v5; safeguard is an addition"
    assert "上桥头不证明已经过桥" in v6_review
    assert "先看后行动不能倒置" in v6_review
    assert "仅相同地点和名词不足以支持整个命题" in v6_review
    assert "不得从名字推测能力" in v6_review
    assert "保留独立有据的窄化命题" in v6_review

    v7_review = REVIEW_PROMPTS["persona-review-v7"]
    assert v6_review in v7_review, "v7 must extend v6; acquisition stage is an addition"


def test_acquisition_prompt_v7_pins_recipient_knowledge_safeguards():
    """ACQUISITION_PROMPT (persona-review-v7) must keep per-recipient knowledge safeguards.

    The acquisition stage is monotone veto: it can only revoke what canonical
    review granted, never add knowledge. The prompt's key safeguards (no
    pre-trained story knowledge, presence/name/order are not knowledge paths,
    narrator truth cannot replace evidence) must survive prompt edits so the
    v6 review's reader-only isolation does not silently regress into a
    'whole knowledge from narrator truth' claim.
    """
    from backend.services.book_world.persona_acquisition import (
        ACQUISITION_PROMPT,
        ACQUISITION_REVIEW_VERSION,
    )
    from backend.services.book_world.persona_models import REVIEW_PROMPTS

    assert ACQUISITION_REVIEW_VERSION == "persona-review-v7"
    assert ACQUISITION_REVIEW_VERSION in REVIEW_PROMPTS
    # v7 is the same semantic prompt as v6; the acquisition stage is a separate
    # prompt used in an independent pass via ACQUISITION_PROMPT.
    assert REVIEW_PROMPTS[ACQUISITION_REVIEW_VERSION] == REVIEW_PROMPTS["persona-review-v6"]

    assert "只审查人物本人知道什么" in ACQUISITION_PROMPT
    assert "不使用预训练故事常识" in ACQUISITION_PROMPT
    assert "旁白客观真相不能替代获知证据" in ACQUISITION_PROMPT
    assert "收到命令与获知其所有前因分开" in ACQUISITION_PROMPT
    assert "在场、同组织、名字暗示能力均不算路径" in ACQUISITION_PROMPT
    assert "集体看听报告可以证明集体行为，但不能凭名字逐人分配" in ACQUISITION_PROMPT
    assert "knowledge_scope=whole只限整条命题的所有子句都由本人实际观察" in ACQUISITION_PROMPT
    assert "unknown_parts列出未证明本人所知的命题子句" in ACQUISITION_PROMPT
    assert "excerpt_safe=false" in ACQUISITION_PROMPT
    assert "空串没有可用引用，不要自动填全文" in ACQUISITION_PROMPT


def test_acquisition_prompt_v7_frozen_sha256_matches_diagnostic_snapshot():
    """ACQUISITION_PROMPT must stay byte-for-byte frozen against the saved diagnostic.

    The acquisition stage is monotone veto. A single character edit to the
    prompt re-opens knowledge-path regressions; the per-recipient safeguards
    only work when the prompt is exact. The saved diagnostic carries the
    ccc2eb48… sha256, so any drift forces this test to fail before the new
    prompt is shipped.
    """
    import hashlib
    from pathlib import Path

    from backend.services.book_world.persona_acquisition import ACQUISITION_PROMPT

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    controls = json.loads(
        (base / "real-model-persona-acquisition-controls-v4.json").read_text(encoding="utf-8")
    )
    assert (
        hashlib.sha256(ACQUISITION_PROMPT.encode()).hexdigest()
        == controls["prompt_sha256"]
    )


def test_chat_models_module_frozen_sha256_matches_v2_matrix_runtime():
    """chat_models.py runtime file must stay frozen against the v2 matrix diagnostic.

    The v9 chat review and v14 chat generate were both added into
    chat_models.py in the same commit, so freezing the module's sha256 against
    the v2 matrix runtime_sha256 also freezes the historical-action
    safeguard text. Any future change must update the diagnostic snapshot,
    re-run the matrix, and refresh the sha256 here.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    matrix = json.loads(
        (base / "real-model-t17-matrix-v2.json").read_text(encoding="utf-8")
    )
    module_path = (
        Path(__file__).resolve().parents[1]
        / "backend/services/book_world/chat_models.py"
    )
    assert (
        hashlib.sha256(module_path.read_bytes()).hexdigest()
        == matrix["runtime_sha256"]["chat_models.py"]
    )


def test_persona_diagnostic_sha256s_match_prompt_versions():
    """Each persona diagnostic snapshot must point at the same review/extract prompt bytes.

    The intent-v4, intent-v5, evidence-v6 and scope-v7 diagnostics were
    collected against specific (review, extract) prompt versions. Freezing
    these mappings here means any drift in ``persona_models.py`` will fail
    the contract — the diagnostic author has to re-record the snapshot and
    re-run the run before the regression can be re-enabled.
    """
    import hashlib
    from pathlib import Path

    from backend.services.book_world.persona_models import (
        EXTRACT_PROMPTS,
        REVIEW_PROMPTS,
    )

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"

    # (diagnostic, expected review version, expected extract version)
    cases = [
        (
            "real-model-persona-intent-v4-01.json",
            "persona-review-v4",
            "persona-extract-v4",
        ),
        (
            "real-model-persona-intent-v5-01.json",
            "persona-review-v4",
            "persona-extract-v5",
        ),
        (
            "real-model-persona-evidence-v6-01.json",
            "persona-review-v5",
            "persona-extract-v6",
        ),
        (
            "real-model-persona-scope-v7-01.json",
            "persona-review-v7",
            "persona-extract-v7",
        ),
    ]

    for fname, review_ver, extract_ver in cases:
        data = json.loads((base / fname).read_text(encoding="utf-8"))
        expected_review_sha = data["prompt_sha256"]["review"]
        expected_extract_sha = data["prompt_sha256"]["extract"]

        actual_review_sha = hashlib.sha256(
            REVIEW_PROMPTS[review_ver].encode()
        ).hexdigest()
        actual_extract_sha = hashlib.sha256(
            EXTRACT_PROMPTS[extract_ver].encode()
        ).hexdigest()

        assert actual_review_sha == expected_review_sha, (
            f"{fname} review sha drift: {actual_review_sha} != {expected_review_sha}"
        )
        assert actual_extract_sha == expected_extract_sha, (
            f"{fname} extract sha drift: {actual_extract_sha} != {expected_extract_sha}"
        )


def test_t17_matrix_v2_freezes_all_five_chat_runtime_modules():
    """All 5 chat-room runtime modules must stay byte-frozen against the v2 matrix.

    The v2 matrix diagnostic recorded a runtime_sha256 for each module that
    participated in the six-combination native run. Freezing the whole
    snapshot here means every chat/room code change (including helpers that
    do not touch prompts) must update the diagnostic, re-run the matrix,
    and refresh the expected hash. This is a deliberately broad contract
    because the v2 matrix is the most recent complete native run and
    anything that breaks byte-equality needs re-justification.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    matrix = json.loads(
        (base / "real-model-t17-matrix-v2.json").read_text(encoding="utf-8")
    )
    runtime = matrix["runtime_sha256"]
    module_root = (
        Path(__file__).resolve().parents[1] / "backend/services/book_world"
    )
    for rel, expected_sha in runtime.items():
        module_path = module_root / Path(rel).name
        actual_sha = hashlib.sha256(module_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"{rel} module drift: {actual_sha} != {expected_sha}; "
            "re-run the six-combination matrix and update the diagnostic."
        )


def test_discovery_inline_and_grouped_prompts_match_v2_v1_diagnostics():
    """INLINE_PROMPT and GROUPED_PROMPT must stay byte-frozen against discovery diagnostics.

    These two prompt constants drive the inline and grouped discovery
    stages. The inline v2 diagnostic recorded the most recent run; the
    grouped v1 diagnostic is the only grouped snapshot on disk. Any
    character-level change must update the corresponding diagnostic,
    re-run the discovery run, and refresh the expected hash here —
    otherwise the new prompt will silently start receiving inputs
    that were originally validated against the old text.
    """
    import hashlib
    from pathlib import Path

    from backend.services.book_world.discovery_grouped import GROUPED_PROMPT
    from backend.services.book_world.discovery_inline import INLINE_PROMPT

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"

    cases = [
        (
            "real-model-inline-discovery-v2.json",
            "prompt_sha256",
            INLINE_PROMPT,
        ),
        (
            "real-model-grouped-discovery-v1.json",
            "prompt_sha256",
            GROUPED_PROMPT,
        ),
    ]
    for fname, sha_key, prompt in cases:
        data = json.loads((base / fname).read_text(encoding="utf-8"))
        expected = data[sha_key]
        actual = hashlib.sha256(prompt.encode()).hexdigest()
        assert actual == expected, (
            f"{fname} prompt drift: {actual} != {expected}; "
            "re-run the discovery and update the diagnostic."
        )


def test_inline_discovery_v2_module_sha_matches_diagnostic_runtime():
    """discovery_inline.py module bytes must match the inline v2 diagnostic.

    The inline v2 diagnostic recorded the bytes of discovery_inline.py after
    the most recent v15 inline run. If the file drifts, the diagnostic's
    runtime_sha256 no longer describes what the code actually is — and a
    future re-run with the new code will produce results that don't
    reproduce the v2 numbers. Lock the file at its diagnostic SHA so any
    change is caught here first, not by silent re-validation drift.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    module_path = (
        Path(__file__).resolve().parents[1]
        / "backend/services/book_world/discovery_inline.py"
    )

    data = json.loads((base / "real-model-inline-discovery-v2.json").read_text(encoding="utf-8"))
    expected = data["runtime_sha256"]["backend/services/book_world/discovery_inline.py"]
    actual = hashlib.sha256(module_path.read_bytes()).hexdigest()
    assert actual == expected, (
        "discovery_inline.py drifted from the inline v2 diagnostic; "
        "either revert the file or re-run the inline discovery and "
        "update the diagnostic with the new SHA before extending this test."
    )


def test_room_and_knowledge_policy_versions_pin_diagnostic_strings():
    """Room and knowledge policy versions must match the saved diagnostics.

    Both `t17-matrix-v1.json` and `t17-matrix-v2.json` record
    policy_version="bounded-room-v1" and
    knowledge_policy_version="canonical-perspective-v1" in
    character_scopes. These values are imported from the runtime
    constants ROOM_POLICY_VERSION and KNOWLEDGE_POLICY_VERSION. If a
    future bump silently renames them, every saved persona binding stops
    round-tripping with the same scope label.
    """
    from pathlib import Path

    from backend.services.book_world.knowledge_models import (
        KNOWLEDGE_POLICY_VERSION,
    )
    from backend.services.book_world.persona_models import PersonaConfig
    from backend.services.book_world.room_models import ROOM_POLICY_VERSION

    assert ROOM_POLICY_VERSION == "bounded-room-v1"
    assert KNOWLEDGE_POLICY_VERSION == "canonical-perspective-v1"
    # PersonaConfig default is also part of the saved scope label; a silent
    # change to "canonical-persona-v4" would invalidate every diagnostic.
    assert PersonaConfig.model_fields["policy_version"].default == "canonical-persona-v3"

    # Both diagnostics record the same scope labels. Make sure they
    # really do (and didn't drift between v1 and v2 of the matrix).
    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    for fname in (
        "real-model-t17-matrix-v1.json",
        "real-model-t17-matrix-v2.json",
    ):
        data = json.loads((base / fname).read_text(encoding="utf-8"))
        for scope in data["character_scopes"]:
            assert scope["canonical_policy_version"] == "canonical-persona-v3", (
                f"{fname} character scope records "
                f"{scope['canonical_policy_version']!r}; "
                "PersonaConfig default must still be 'canonical-persona-v3'."
            )
            assert scope["knowledge_policy_version"] == "canonical-perspective-v1", (
                f"{fname} character scope records "
                f"{scope['knowledge_policy_version']!r}; "
                "KNOWLEDGE_POLICY_VERSION must still be 'canonical-perspective-v1'."
            )
        cfg = data["model_config"]
        assert cfg["policy_version"] == "bounded-room-v1", (
            f"{fname} model_config records policy_version={cfg['policy_version']!r}; "
            "ROOM_POLICY_VERSION must still be 'bounded-room-v1'."
        )


def test_chat_review_v9_sha_matches_conditional_and_negative_diagnostics():
    """character-chat-review-v9 must stay byte-frozen against t17 SHA diagnostics.

    The conditional-positive and current-negative T17 diagnostics both
    recorded a `review_prompt_sha256` of the v9 review. Freezing this
    here complements the chat_models.py module freeze: any change to
    the v9 review text will fail this test even if some unrelated
    function in the file is touched, so the diagnostic author has to
    re-record the snapshot and re-run the conditional/negative probes.
    """
    import hashlib
    from pathlib import Path

    from backend.services.book_world.chat_models import REVIEW_PROMPTS

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    expected_sha = "91ebcd2c1b193ab27b7350f12d21f0c7fd9bafd1615abc5c806c10fbc85a439e"
    actual_sha = hashlib.sha256(
        REVIEW_PROMPTS["character-chat-review-v9"].encode()
    ).hexdigest()
    assert actual_sha == expected_sha

    # Both diagnostics must agree on the same hash.
    for fname in (
        "real-model-t17-conditional-positive-v1.json",
        "real-model-t17-current-negative-v1.json",
    ):
        data = json.loads((base / fname).read_text(encoding="utf-8"))
        assert data["review_prompt_sha256"] == expected_sha, (
            f"{fname} recorded a different review sha: {data['review_prompt_sha256']}"
        )


def test_persona_version_constants_pin_aliases_and_prompts():
    """Persona version constants must point at specific EXTRACT/REVIEW prompts and keep aliasing.

    The build pipeline reads STRUCTURED_PERSONA_VERSION, EVIDENCE_PERSONA_VERSION,
    SCOPED_PERSONA_VERSION and ACQUISITION_REVIEW_VERSION to decide which prompt
    body to invoke. If a constant silently moves to a different key (e.g. v6 -> v8)
    the saved diagnostics would no longer match what the running code uses. This
    test freezes the four constants to their current key bindings and locks the
    v7-review-equals-v6-review alias so the persona review can keep using v7 as
    a stable label while sharing the actual v6 prompt body.
    """
    from backend.services.book_world.persona_acquisition import (
        ACQUISITION_REVIEW_VERSION,
    )
    from backend.services.book_world.persona_models import (
        EVIDENCE_PERSONA_VERSION,
        EXTRACT_PROMPTS,
        REVIEW_PROMPTS,
        SCOPED_PERSONA_VERSION,
        STRUCTURED_PERSONA_VERSION,
    )

    # Extract-side constants must point at specific EXTRACT_PROMPT keys.
    assert STRUCTURED_PERSONA_VERSION == "persona-extract-v5"
    assert EVIDENCE_PERSONA_VERSION == "persona-extract-v6"
    assert SCOPED_PERSONA_VERSION == "persona-extract-v7"

    # Acquisition review must use persona-review-v7 (the same label frozen by
    # the persona-scope v7 diagnostic and the acquisition-controls v4 snapshot).
    assert ACQUISITION_REVIEW_VERSION == "persona-review-v7"

    # The keys must all exist; otherwise a future rename would silently
    # break build runs that still reference the old name.
    for key in (
        STRUCTURED_PERSONA_VERSION,
        EVIDENCE_PERSONA_VERSION,
        SCOPED_PERSONA_VERSION,
    ):
        assert key in EXTRACT_PROMPTS, f"EXTRACT_PROMPTS missing {key}"
    assert ACQUISITION_REVIEW_VERSION in REVIEW_PROMPTS, (
        f"REVIEW_PROMPTS missing {ACQUISITION_REVIEW_VERSION}"
    )

    # Alias chain: persona-review-v7 shares its body with persona-review-v6
    # (so existing v6 diagnostics remain valid for v7 runs). v7 must be the
    # exact same string, not a re-typed copy.
    assert REVIEW_PROMPTS["persona-review-v7"] is REVIEW_PROMPTS["persona-review-v6"]
    assert REVIEW_PROMPTS["persona-review-v7"] == REVIEW_PROMPTS["persona-review-v6"]

    # The persona-extract chain is not an alias chain: v4 -> v5 -> v6 -> v7
    # are all distinct bodies (cumulative additions). Lock that fact so a
    # future "extract-v7 is just an alias of v6" change would be caught.
    for older, newer in [
        ("persona-extract-v3", "persona-extract-v4"),
        ("persona-extract-v4", "persona-extract-v5"),
        ("persona-extract-v5", "persona-extract-v6"),
        ("persona-extract-v6", "persona-extract-v7"),
    ]:
        assert EXTRACT_PROMPTS[older] in EXTRACT_PROMPTS[newer], (
            f"{newer} must extend {older} (cumulative); not an alias"
        )


def test_t17_matrix_runner_sha_and_baseline_invariant_pin_v2_diagnostic():
    """The t17 v2 matrix runner and baseline-invariance must stay frozen.

    The v2 matrix diagnostic recorded both ``runner_sha256`` (the
    ``discussion-acceptance.py`` script that drove the six-combination
    native run) and an explicit ``canonical_baselines_unchanged`` flag
    that says the per-character canonical SHA before the run equals the
    SHA after the run. Both are independent of the chat-room module
    SHAs already locked elsewhere in this file:

    * ``runner_sha256`` pins the script that constructs the case set,
      timeouts, and per-case prompt/timeout wiring. If a future commit
      edits that script, the diagnostic must be regenerated and the
      matrix re-run, or the result can no longer claim to come from the
      same procedure.
    * ``canonical_baselines_unchanged`` is the proof that the matrix
      is non-destructive on the persona canonical SHA. A future runner
      change that accidentally mutates a persona baseline (e.g. by
      publishing a partial session in the wrong workspace) would
      invalidate the matrix and must be caught here.

    The same baseline-invariance flag is also recorded in the matrix
    v1 diagnostic and the two cognition-pilot diagnostics, all of
    which refer to the same per-character canonical SHA. Locking all
    four together keeps the t17 evidence chain consistent: a future
    runner change that mutates a baseline would have to fix four
    diagnostics, which forces the new state to be re-justified.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"

    runner_path = (
        Path(__file__).resolve().parents[1]
        / "docs/plans/book-character-agents/discussion-acceptance.py"
    )
    actual_runner_sha = hashlib.sha256(runner_path.read_bytes()).hexdigest()

    # Diagnostics that record a runner_sha256 — these three all
    # observed the same runner script and the same canonical baseline
    # invariant.
    runner_diagnostics = (
        "real-model-t17-matrix-v2.json",
        "real-model-t17-cognition-pilot-v1.json",
        "real-model-t17-cognition-pilot-v2.json",
    )
    for fname in runner_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        assert diagnostic["runner_sha256"] == actual_runner_sha, (
            f"{fname} reports runner_sha256="
            f"{diagnostic['runner_sha256']} but discussion-acceptance.py "
            f"is now {actual_runner_sha}; re-run the matrix/pilot and "
            "update the diagnostic."
        )

    # Baseline-invariance: every diagnostic that records the before
    # and after canonical SHA must show they are equal. matrix v1
    # predates the runner_sha256 field but still records the
    # invariance flag, so it is locked here too.
    baseline_diagnostics = (
        "real-model-t17-matrix-v1.json",
        "real-model-t17-matrix-v2.json",
        "real-model-t17-cognition-pilot-v1.json",
        "real-model-t17-cognition-pilot-v2.json",
    )
    for fname in baseline_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        assert diagnostic["canonical_baselines_unchanged"] is True, (
            f"{fname} reports canonical_baselines_unchanged=False; "
            "the matrix/pilot is meant to be a read-only probe"
        )
        assert (
            diagnostic["canonical_baselines_before"]
            == diagnostic["canonical_baselines_after"]
        ), (
            f"{fname} reports canonical baseline drift between "
            "before and after the run; the matrix/pilot is meant to "
            "be a read-only probe"
        )


def test_inline_discovery_v1_module_shas_pin_numbered_runtime():
    """The v1 inline diagnostic recorded two discovery module SHAs.

    v1 of the inline discovery diagnostic recorded runtime SHAs for
    three files: ``discovery_inline.py`` (which we now freeze against
    v2 separately), ``discovery_numbered.py``, and ``discovery.py``.
    The inline prompt has since moved to v2 and ``discovery_inline.py``
    has been rewritten; ``discovery.py`` was also edited and is no
    longer byte-stable against the v1 diagnostic. However
    ``discovery_numbered.py`` is still byte-stable against v1 — the
    numbered module is still in production and the v1 inline run
    observed it at SHA ``5f16f1b1…``. Freezing that here means any
    future edit to ``discovery_numbered.py`` must update the v1
    diagnostic, re-run the inline discovery, and refresh the expected
    hash, exactly as the chat-room matrix requires.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    diagnostic = json.loads(
        (base / "real-model-inline-discovery-v1.json").read_text(encoding="utf-8")
    )
    runtime = diagnostic["runtime_sha256"]

    # discovery_numbered.py is still byte-stable against v1; lock it.
    numbered_path = (
        Path(__file__).resolve().parents[1]
        / "backend/services/book_world/discovery_numbered.py"
    )
    actual_sha = hashlib.sha256(numbered_path.read_bytes()).hexdigest()
    expected_sha = runtime[
        "backend/services/book_world/discovery_numbered.py"
    ]
    assert actual_sha == expected_sha, (
        "discovery_numbered.py drift: "
        f"{actual_sha} != {expected_sha}; "
        "the v1 inline discovery diagnostic observed this module at "
        "this SHA; re-run the inline discovery and update the diagnostic."
    )

    # discovery_inline.py changed between v1 and v2; v1's expected
    # value is the historical snapshot, not the current file. We
    # still record the historical v1 expectation in a comment so the
    # next reader does not mistake the v1 SHA for a current one.
    v1_inline_sha = runtime[
        "backend/services/book_world/discovery_inline.py"
    ]
    # The v2 inline test freezes the current SHA; the v1 value here
    # is the historical reference. Asserting v1 != v2-equivalent
    # documents that the inline file has been edited at least once
    # between the two native runs.
    v2_diagnostic = json.loads(
        (base / "real-model-inline-discovery-v2.json").read_text(encoding="utf-8")
    )
    v2_inline_sha = v2_diagnostic["runtime_sha256"][
        "backend/services/book_world/discovery_inline.py"
    ]
    assert v1_inline_sha != v2_inline_sha, (
        "v1 and v2 inline diagnostics report the same SHA for "
        "discovery_inline.py; the v1 SHA is documented to be a "
        "historical snapshot, so this is a sign the v1/v2 run labels "
        "have been conflated"
    )


def test_inline_discovery_v1_corpus_files_sha_pin_full_source():
    """Corpus text files must stay byte-frozen against the v1 inline source.

    The v1 inline discovery diagnostic recorded
    ``corpus_sources.books[].sha256`` for both 西游记 and 红楼梦. The
    discovery runs operate directly on these files in
    ``tmp/book-corpus/``; if either text changes, the diagnostic
    evidence is invalidated (the discovery outputs cannot be
    re-derived from the new text without re-running the discovery).

    Freezing the file SHAs here is the equivalent of pinning the
    discovery source data: any edit to either corpus file must
    re-record the inline v1 diagnostic, re-run the discovery, and
    refresh the expected hash. The discovery_numbered.py lock
    complements this by pinning the discovery consumer.
    """
    import hashlib
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    diagnostic = json.loads(
        (base / "real-model-inline-discovery-v1.json").read_text(encoding="utf-8")
    )

    # Map title -> expected file SHA from the diagnostic.
    expected_by_title = {}
    for book in diagnostic["corpus_sources"]["books"]:
        expected_by_title[book["title"]] = book["sha256"]

    corpus_dir = (
        Path(__file__).resolve().parents[1] / "tmp" / "book-corpus"
    )
    # File name to diagnostic title mapping. The on-disk files use the
    # Chinese title verbatim; the diagnostic also uses the Chinese
    # title, so we can match by basename.
    for title, expected_sha in expected_by_title.items():
        file_path = corpus_dir / f"{title}.txt"
        assert file_path.exists(), (
            f"corpus file {file_path} not found; the v1 diagnostic "
            f"recorded it at {expected_sha}"
        )
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"{title} corpus text drift: {actual_sha} != {expected_sha}; "
            "the v1 inline diagnostic was recorded against this exact "
            "byte content; update the diagnostic and re-run the inline "
            "discovery to refresh the evidence chain."
        )


def test_persona_sub_build_diagnostics_pin_agent_unchanged_invariant():
    """Persona sub-builds must not mutate the parent Agent hash.

    The intent-v4, intent-v5, evidence-v6, and scope-v7 sub-build
    diagnostics each record ``old_agent_sha256_before`` and
    ``old_agent_sha256_after``. The invariant
    ``before == after`` is the hard evidence that:

      * the new persona sub-build operates on a copy / child
        ``build_id``,
      * the parent Agent (from ``old_build_id``) is left bitwise
        identical after the sub-build,
      * reading the parent Agent post-run returns exactly the
        same fingerprint that the sub-build started from.

    The diagnostic also carries an explicit
    ``old_agent_unchanged`` boolean; locking both the boolean
    and the surrounding hash equality is the non-destructive
    probe contract for "persona extraction never silently
    rewrites the parent". Together with the v5/v6/v7
    ``previous_v5_sha256_before == previous_v5_sha256_after``
    pair, the four diagnostics collectively back the
    "sub-build never edits upstream baselines" guarantee
    that the t17 matrix runner contract (matrix and
    cognition-pilot diagnostics) provides for the chat room
    side.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    agent_diagnostics = (
        "real-model-persona-intent-v4-01.json",
        "real-model-persona-intent-v5-01.json",
        "real-model-persona-evidence-v6-01.json",
        "real-model-persona-scope-v7-01.json",
    )
    for fname in agent_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        before = diagnostic["old_agent_sha256_before"]
        after = diagnostic["old_agent_sha256_after"]
        assert before == after, (
            f"{fname} reports the parent Agent hash drifted during a "
            f"persona sub-build: before={before} after={after}; the "
            "sub-build must operate on a child build and leave the "
            "parent Agent bitwise identical."
        )
        # The diagnostic also exposes an explicit boolean; both must agree.
        assert diagnostic["old_agent_unchanged"] is True, (
            f"{fname} sets old_agent_unchanged=False while the hashes "
            "agree; either the boolean or the hash equality is stale."
        )

    # evidence-v6 and scope-v7 additionally carry the v5 baseline
    # non-destructive probe.
    v5_baseline_diagnostics = (
        "real-model-persona-evidence-v6-01.json",
        "real-model-persona-scope-v7-01.json",
    )
    for fname in v5_baseline_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        v5_before = diagnostic["previous_v5_sha256_before"]
        v5_after = diagnostic["previous_v5_sha256_after"]
        assert v5_before == v5_after, (
            f"{fname} reports the v5 persona baseline drifted during a "
            f"v6/v7 sub-build: before={v5_before} after={v5_after}; "
            "v6/v7 must build on top of v5 without rewriting it."
        )


def test_persona_v5_audit_and_ui_proof_pin_readonly_invariants():
    """The v5 agent-source audit and its paired UI proof are read-only.

    The persona-v5-agent-source-audit.json diagnostic reports a list of
    4 fixed ``permission_checks`` decisions, an
    ``old_agent_unchanged=True`` flag, and a
    ``native_trace_sha256`` that fingerprints the actual run record.

    The matching persona-v5-ui-proof.json diagnostic records the
    user-facing proof that the round trip is read-only:

      * ``model_calls == 0`` — the UI does not trigger any model call,
      * ``only_read_actions == True`` — only read actions were
        performed,
      * ``new_build`` matches the v5 audit's ``build_id`` — the UI
        proof covers the exact build the audit covers,
      * ``old_build`` is non-empty — the v5 sub-build is built on
        top of a specific, named parent build,
      * ``old_agent_unchanged == True`` — re-asserted at the UI
        layer.

    Locking all of these as code-level contracts means a future
    change that, e.g., makes the UI proof trigger a generation
    call, or breaks the audit↔UI proof pairing, will fail the
    regression instead of silently re-introducing model usage into
    a "read-only proof" path.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    audit = json.loads((base / "persona-v5-agent-source-audit.json").read_text(encoding="utf-8"))
    ui = json.loads((base / "persona-v5-ui-proof.json").read_text(encoding="utf-8"))

    # The audit must be a real, read-only inspection of the existing
    # v5 build, not a fresh generation.
    assert audit["old_agent_unchanged"] is True, (
        "persona-v5-agent-source-audit.json flipped "
        "old_agent_unchanged away from True; the audit must not "
        "trigger a fresh agent rewrite."
    )
    assert audit["native_trace_sha256"], (
        "persona-v5-agent-source-audit.json lost its native_trace_sha256; "
        "without it the audit's run is no longer reproducible."
    )
    # The 4 fixed permission-check decisions are the audit's
    # non-destructive probe outputs. They are recorded as a dict
    # mapping decision name -> True/False; the *keys* are the
    # stable label set and must remain identical so a later
    # "I checked the same things" claim can be cross-referenced.
    expected_permission_checks = {
        "stone_birth_composite_rejected_and_revoked",
        "heaven_facts_not_granted_to_stone",
        "groups_remain_needs_review",
        "stone_intent_trait_supported",
    }
    actual_permission_checks = set(audit["permission_checks"].keys())
    assert actual_permission_checks == expected_permission_checks, (
        "persona-v5-agent-source-audit.json permission_check labels drifted "
        f"from the locked set: got {actual_permission_checks!r}, "
        f"expected {expected_permission_checks!r}."
    )
    # Each decision must be a concrete True/False (not None) so the
    # audit's yes/no is unambiguous.
    for label, value in audit["permission_checks"].items():
        assert isinstance(value, bool), (
            f"permission_check {label!r} is not a boolean: {value!r}."
        )

    # The UI proof is paired with the audit: the new_build on the UI
    # side must equal the audit's build_id, and the audit must be
    # a read-only inspection of a parent build.
    assert ui["new_build"] == audit["build_id"], (
        "persona-v5-ui-proof.json new_build "
        f"({ui['new_build']!r}) does not match persona-v5-agent-source-audit.json "
        f"build_id ({audit['build_id']!r}); the UI proof must cover the same build."
    )
    assert ui["old_build"], (
        "persona-v5-ui-proof.json lost its old_build; the v5 sub-build "
        "must name its parent build for the non-destructive probe to "
        "be auditable."
    )
    assert ui["old_build"] != ui["new_build"], (
        "persona-v5-ui-proof.json old_build equals new_build; the v5 "
        "sub-build must be a distinct, child build."
    )
    assert ui["model_calls"] == 0, (
        f"persona-v5-ui-proof.json reports model_calls={ui['model_calls']}; "
        "the UI proof path is supposed to be read-only and must not "
        "trigger any model call."
    )
    assert ui["only_read_actions"] is True, (
        "persona-v5-ui-proof.json only_read_actions flipped away from True; "
        "the UI proof must consist only of read actions."
    )
    # The four "visible" booleans capture what the user actually saw in
    # the read-only UI. Each is a true/false statement about the UI
    # state; locking the truthy ones preserves the original
    # observation.
    assert ui["intent_baseline_visible"] is True
    assert ui["rejected_claim_unavailable_visible"] is True
    assert ui["old_version_selectable"] is True
    assert ui["new_version_restored"] is True


def test_persona_v4_controls_pin_native_budget_and_case_set():
    """The v4 controls diagnostic pins the budget and case labels.

    The persona-v4 controls and feedback diagnostics are the
    per-version sub-build read-only probes. Each:

      * declares a ``native_call_ceiling`` and
        ``actual_native_calls`` — these must match (no overrun, no
        underrun) so the probe is reproducible,
      * carries a fixed list of named ``cases`` — the case names
        are the audit's semantic ground truth (e.g.
        ``unheard-heaven`` for "rejected for not being firsthand"
        and ``volunteered-intention`` for "accepted as trait-only");
        changing them silently would invalidate the contract
        between this probe and the diagnostic record.

    Locking both budgets and case names turns the "this is the
    same probe as before" claim into a regression test.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    for fname in (
        "real-model-persona-v4-controls-v1.json",
        "real-model-persona-v4-feedback-v1.json",
    ):
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        # The hard contract: actual native calls must never exceed
        # the declared ceiling (no overrun). Underruns are allowed
        # because a unit may be rejected by validation before
        # consuming the full budget — this is the expected
        # short-circuit for the feedback diagnostic.
        assert diagnostic["actual_native_calls"] <= diagnostic["native_call_ceiling"], (
            f"{fname} actual_native_calls={diagnostic['actual_native_calls']} "
            f"> native_call_ceiling={diagnostic['native_call_ceiling']}; "
            "the probe exceeded its declared native budget."
        )
        case_names = [c["case"] if "case" in c else c.get("unit_key") for c in diagnostic["cases"]]
        assert case_names, f"{fname} has no cases; the probe shape changed."

    # v4 controls has two fixed semantic cases that the production
    # v3 default is expected to keep honoring. v4 controls consumed
    # its full budget (actual == ceiling) because both units
    # successfully completed; lock the equality.
    controls = json.loads(
        (base / "real-model-persona-v4-controls-v1.json").read_text(encoding="utf-8")
    )
    assert controls["actual_native_calls"] == controls["native_call_ceiling"], (
        "real-model-persona-v4-controls-v1.json no longer consumed its full "
        "native budget; the v3-default semantic probe is not being executed."
    )
    expected_control_cases = ["unheard-heaven", "volunteered-intention"]
    actual_control_cases = [c["case"] for c in controls["cases"]]
    assert actual_control_cases == expected_control_cases, (
        "real-model-persona-v4-controls-v1.json case labels drifted: "
        f"got {actual_control_cases!r}, expected {expected_control_cases!r}; "
        "the unheard-heaven / volunteered-intention labels are the "
        "semantic ground truth for the v3 default review."
    )


def test_discussion_probe_v8_through_v12_pin_baseline_unchanged_invariant():
    """The 5 sequential discussion probes must not mutate the room baseline.

    The real-model-discussion-v8-probe through v12-probe diagnostics
    each record ``baseline_sha256_before`` and
    ``baseline_sha256_after`` plus an explicit
    ``canonical_baselines_unchanged`` boolean. All five
    independently report:

      * ``before == after`` (the same canonical baseline SHA),
      * ``canonical_baselines_unchanged == True`` (the boolean agrees).

    This is the per-probe companion to the t17 matrix runner
    `canonical_baselines_unchanged` contract. While the matrix
    contract covers a single runner covering 6 mode combinations,
    this test covers 5 *sequential* chat-room probes (v8 → v12),
    each with a different ``character-chat`` / ``character-chat-review``
    version. Together they prove the entire chat-room evolution
    from v8 through v12 is non-destructive on the canonical
    room / knowledge baselines — a future change that
    accidentally rewrites the baseline (e.g. by making a probe
    publish partial state) will fail this regression.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    probe_diagnostics = (
        "real-model-discussion-v8-probe.json",
        "real-model-discussion-v9-probe.json",
        "real-model-discussion-v10-probe.json",
        "real-model-discussion-v11-probe.json",
        "real-model-discussion-v12-probe.json",
    )
    for fname in probe_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        before = diagnostic["baseline_sha256_before"]
        after = diagnostic["baseline_sha256_after"]
        assert before == after, (
            f"{fname} reports the canonical baseline SHA drifted during a "
            f"discussion probe: before={before} after={after}; the probe "
            "must be read-only on the baseline."
        )
        assert diagnostic["canonical_baselines_unchanged"] is True, (
            f"{fname} sets canonical_baselines_unchanged=False while the "
            "hashes agree; either the boolean or the hash equality is stale."
        )


def test_expression_revision_room_memory_probes_pin_readonly_invariants():
    """Three single-purpose probes must each honor their read-only contract.

    The expression, revision, and room-memory probes are
    per-feature read-only probes that each guard a different
    sub-system against silent mutation. The locking is a
    per-feature contract:

      * **expression-probe** — the probe over the canonical
        expression archive must not mutate it
        (``canonical_archive_unchanged=True``), the
        ``sample_sha256`` fingerprint of the input must stay
        present, and ``actual_calls`` must equal the declared
        budget (no over/under run).

      * **revision-probe** — the probe over the persona
        revision path must preserve the original build
        (``original_build_preserved=True``), pass the
        base-archive-snapshot assertion
        (``base_archive_snapshot_assertion_passed=True``),
        and the probe must not change global model settings
        (``global_model_settings_changed=False``).

      * **room-memory-probe** — the probe over the room
        memory summary path must keep the canonical baseline
        unchanged (``canonical_baseline_unchanged=True``) and
        consume exactly the declared call budget
        (``actual_calls == call_budget``).

    Each contract is the per-feature counterpart to the
    t17 matrix / discussion v8-v12 baseline-unchanged
    invariants. Together they guarantee that no probe
    accidentally publishes partial state into the canonical
    archives / builds / baselines.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"

    # --- expression probe ---
    expression = json.loads(
        (base / "real-model-expression-probe.json").read_text(encoding="utf-8")
    )
    assert expression["canonical_archive_unchanged"] is True, (
        "real-model-expression-probe.json canonical_archive_unchanged "
        "flipped away from True; the expression probe must not mutate "
        "the canonical expression archive."
    )
    assert expression["sample_sha256"], (
        "real-model-expression-probe.json lost its sample_sha256; without "
        "it the probe's input sample is no longer reproducible."
    )
    # The probe budget is fixed at 2 calls in the recorded diagnostic;
    # any future change to the call count must re-record the diagnostic.
    assert expression["actual_calls"] == 2, (
        f"real-model-expression-probe.json actual_calls={expression['actual_calls']} "
        "drifted from the recorded 2-call budget; the probe shape changed "
        "and the diagnostic must be re-recorded."
    )

    # --- revision probe ---
    revision = json.loads(
        (base / "real-model-revision-probe.json").read_text(encoding="utf-8")
    )
    assert revision["original_build_preserved"] is True, (
        "real-model-revision-probe.json original_build_preserved flipped "
        "away from True; the revision probe must not mutate the original "
        "persona build."
    )
    assert revision["base_archive_snapshot_assertion_passed"] is True, (
        "real-model-revision-probe.json base_archive_snapshot_assertion_passed "
        "flipped away from True; the base archive snapshot assertion no longer "
        "holds and the revision probe is no longer the read-only audit it claims."
    )
    assert revision["global_model_settings_changed"] is False, (
        "real-model-revision-probe.json global_model_settings_changed flipped "
        "to True; the probe is supposed to leave global model settings alone."
    )
    # The probe consumed exactly 6 calls in the recorded diagnostic.
    assert revision["calls"] == 6, (
        f"real-model-revision-probe.json calls={revision['calls']} drifted "
        "from the recorded 6-call count; the probe shape changed and the "
        "diagnostic must be re-recorded."
    )

    # --- room-memory probe ---
    room_memory = json.loads(
        (base / "real-model-room-memory-probe.json").read_text(encoding="utf-8")
    )
    assert room_memory["canonical_baseline_unchanged"] is True, (
        "real-model-room-memory-probe.json canonical_baseline_unchanged "
        "flipped away from True; the room memory probe must not mutate the "
        "canonical room baseline."
    )
    assert room_memory["actual_calls"] == room_memory["call_budget"], (
        f"real-model-room-memory-probe.json actual_calls={room_memory['actual_calls']} "
        f"!= call_budget={room_memory['call_budget']}; the room memory probe "
        "consumed a different number of calls than its declared budget."
    )


def test_t17_discussion_cases_dataset_pins_six_combination_ground_truth():
    """The t17 six-combination gold standard is a frozen dataset.

    ``t17-discussion-cases-v1.json`` is the gold standard
    dataset for the t17 six-combination matrix probe
    (free/topic × natural/directed/all). It carries:

      * ``dataset_version`` — the version string for the
        gold standard (must remain the same identifier so
        later diagnostics can cite the same set),
      * ``native_call_ceiling`` — the per-probe call budget,
      * ``manual_continues_per_turn`` — the manual continue
        budget per turn (must not silently grow),
      * ``reviewer_kind`` — must continue to label the
        reviewer as the Agent doing the inspection (not a
        human blind review claim),
      * exactly **6 cases** with the expected
        ``discussion_mode`` × ``mode`` coverage:
        - free + natural,
        - free + directed,
        - free + all,
        - topic + natural,
        - topic + directed,
        - topic + all.
        The 6 case set is the contract that gives the matrix
        its name; any future change must re-record the
        diagnostic AND bump the dataset version.

    Locking the dataset shape is the only way to make
    "matrix v1 == matrix v2 == cognition-pilot v1 == ...
    == 'this same six-combination probe'" a regression-test
    statement instead of a hand-waving claim.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    cases = json.loads(
        (base / "t17-discussion-cases-v1.json").read_text(encoding="utf-8")
    )

    assert cases["dataset_version"] == "t17-six-combinations-v1", (
        f"t17-discussion-cases-v1.json dataset_version drifted to "
        f"{cases['dataset_version']!r}; the matrix probe cites the "
        "dataset by this string, so renaming it silently breaks "
        "the citation chain."
    )
    assert cases["native_call_ceiling"] == 32, (
        f"t17-discussion-cases-v1.json native_call_ceiling drifted to "
        f"{cases['native_call_ceiling']}; the matrix v1/v2 budget ceiling "
        "is part of the gold standard."
    )
    assert cases["manual_continues_per_turn"] == 1, (
        f"t17-discussion-cases-v1.json manual_continues_per_turn drifted "
        f"to {cases['manual_continues_per_turn']}; the matrix probe's "
        "manual-continue budget is part of the gold standard."
    )
    assert "Agent" in cases["reviewer_kind"] and "no claim of human blind" in cases["reviewer_kind"], (
        f"t17-discussion-cases-v1.json reviewer_kind drifted to "
        f"{cases['reviewer_kind']!r}; the reviewer must remain the "
        "Agent doing the inspection (no human blind-review claim)."
    )
    assert len(cases["cases"]) == 6, (
        f"t17-discussion-cases-v1.json has {len(cases['cases'])} cases, "
        "expected exactly 6 to match the free/topic × natural/directed/all "
        "six combinations."
    )
    # The 6 case combinations are the probe's ground truth; each case
    # must declare both its discussion_mode and its mode.
    expected_mode_combos = {
        ("free", "natural"),
        ("free", "directed"),
        ("free", "all"),
        ("topic", "natural"),
        ("topic", "directed"),
        ("topic", "all"),
    }
    actual_mode_combos = {
        (c["discussion_mode"], c["mode"]) for c in cases["cases"]
    }
    assert actual_mode_combos == expected_mode_combos, (
        f"t17-discussion-cases-v1.json mode coverage drifted: "
        f"got {actual_mode_combos!r}, expected {expected_mode_combos!r}."
    )
    # Each case must carry the same questions/expected structure so
    # the matrix runner can iterate them uniformly.
    required_case_fields = {"case_id", "discussion_mode", "mode", "questions", "expected"}
    for c in cases["cases"]:
        missing = required_case_fields - set(c.keys())
        assert not missing, (
            f"t17-discussion-cases-v1.json case {c.get('case_id')!r} "
            f"is missing required fields {missing!r}."
        )


def test_t17_review_cognition_v1_pins_instruction_sha_and_aggregate_budget():
    """The cognition-safeguard review instruction must stay byte-frozen.

    ``real-model-t17-review-cognition-v1.json`` is the diagnostic
    that recorded the cognition-change safeguard addition to the
    t17 review prompt. It pins:

      * ``instruction_sha256: e7295bfe…`` — the byte-level SHA of
        the experimental review addition (cognition change +
        past-conditional + new-situation choice). Any future
        text edit to that addition must re-record the
        diagnostic and re-run the probe.
      * ``source_matrix: real-model-t17-matrix-v1.json`` — the
        diagnostic is built on top of matrix v1's six cases, so
        it is auditable against the v1 matrix baseline.
      * ``actual_native_calls == native_call_ceiling`` (2==2) —
        the probe consumed its full budget.
      * ``aggregate_t17_ceiling == 32`` and
        ``aggregate_native_calls == 27`` — the aggregate t17
        budget roll-up (matrix v1's 25 native calls + 2 from
        this probe = 27/32). Any change to the matrix native
        call count must be reflected here.
      * ``publication == False`` — the diagnostic is a
        diagnostic, not a publication.

    Locking the SHA + aggregate budget means the
    "cognition-safeguard is the same instruction the diagnostic
    ran" claim survives as a regression test.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    cog = json.loads(
        (base / "real-model-t17-review-cognition-v1.json").read_text(encoding="utf-8")
    )
    assert cog["instruction_sha256"] == (
        "e7295bfec91e06d67186527a502c282ce593ddaffc50ff10571d7ccea36f1e1f"
    ), (
        f"real-model-t17-review-cognition-v1.json instruction_sha256 drifted "
        f"to {cog['instruction_sha256']!r}; the cognition-safeguard review "
        "addition's byte-level SHA must stay frozen."
    )
    assert cog["source_matrix"] == "real-model-t17-matrix-v1.json", (
        f"real-model-t17-review-cognition-v1.json source_matrix drifted to "
        f"{cog['source_matrix']!r}; the cognition diagnostic must be built "
        "on top of matrix v1 to remain auditable against the v1 baseline."
    )
    assert cog["actual_native_calls"] == cog["native_call_ceiling"], (
        f"real-model-t17-review-cognition-v1.json actual_native_calls "
        f"({cog['actual_native_calls']}) != native_call_ceiling "
        f"({cog['native_call_ceiling']}); the cognition probe no longer "
        "consumed its full budget."
    )
    assert cog["aggregate_t17_ceiling"] == 32, (
        f"real-model-t17-review-cognition-v1.json aggregate_t17_ceiling "
        f"drifted to {cog['aggregate_t17_ceiling']}; the t17 aggregate "
        "ceiling is part of the gold standard."
    )
    assert cog["aggregate_native_calls"] == 27, (
        f"real-model-t17-review-cognition-v1.json aggregate_native_calls "
        f"drifted to {cog['aggregate_native_calls']}; the t17 aggregate "
        "roll-up must equal matrix v1 (25) + cognition probe (2) = 27."
    )
    assert cog["publication"] is False, (
        "real-model-t17-review-cognition-v1.json publication flipped to "
        "True; the cognition diagnostic is a probe, not a publication."
    )


def test_discovery_probes_pin_no_publication_and_actual_budget():
    """Discovery probes must not publish into the database.

    The v8 through v14 discovery repair probes are
    per-version read-only probes. Each reports
    ``database_publication == False`` (or, equivalently for
    the v12+ diagnostics, ``publication == False``) and a
    ``terminal == True`` flag marking the probe finished.
    This is the canonical "discovery probes don't publish
    into the canonical archive" contract: any future change
    that flips publication to True would mean a probe has
    silently mutated the canonical archive state, which the
    documented contract explicitly forbids.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    no_publication_diagnostics = (
        "real-model-discovery-v8-repair.json",
        "real-model-discovery-v9-repair.json",
        "real-model-discovery-v10-repair.json",
        "real-model-discovery-v12-choices.json",
        "real-model-discovery-v13-literal.json",
        "real-model-discovery-v13-numbered.json",
        "real-model-discovery-v14-window-repair.json",
        "real-model-discovery-v12-binding-repairs.json",
    )
    for fname in no_publication_diagnostics:
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        # Each diagnostic has either database_publication (older
        # shape) or publication (newer shape). Both must be False.
        pub_field = "database_publication" if "database_publication" in diagnostic else "publication"
        assert diagnostic[pub_field] is False, (
            f"{fname} {pub_field} flipped to True; the discovery probe "
            "must not publish into the canonical archive."
        )
        assert diagnostic["terminal"] is True, (
            f"{fname} terminal flipped to False; the probe shape changed."
        )

    # real-model-discovery-v7-contract.json additionally reports
    # validation_pass=True (the v7 contract holds on its frozen
    # input) — that's a different signal from "no publication"
    # and lives on a contract diagnostic.
    v7 = json.loads(
        (base / "real-model-discovery-v7-contract.json").read_text(encoding="utf-8")
    )
    assert v7["validation_pass"] is True, (
        "real-model-discovery-v7-contract.json validation_pass flipped to "
        "False; the v7 contract no longer holds on its recorded input."
    )


def test_t17_agent_reviews_pin_unfinished_and_baseline_invariants():
    """Agent reviews must honestly mark T17/T12 as not yet closed.

    Both ``t17-cognition-agent-review.json`` and
    ``t17-matrix-v2-agent-review.json`` are the Agent's own
    post-run audit of the t17 work. They carry four honest
    signals that the work is **not** yet accepted:

      * ``t17_complete: False`` and ``t12_complete: False`` —
        the review explicitly states the task is not closed.
        Flipping either to True without a re-recorded
        diagnostic and a new pass would silently claim
        acceptance that never happened.

      * ``quality_pass: False`` — the Agent did not find the
        run quality-acceptable. This is a separate signal
        from "complete" and must remain in sync with the
        failure catalog.

      * ``baseline_mutation: False`` (cognition) /
        ``canonical_baselines_unchanged: True`` (matrix v2) —
        the run is non-destructive. Locking both ensures
        that the honesty signal ("not yet closed") does not
        come at the cost of a hidden baseline rewrite.

    Together these tests make "T17 / T12 are not closed by
    this run" a regression-test statement, not a hand-wave.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    for fname in (
        "t17-cognition-agent-review.json",
        "t17-matrix-v2-agent-review.json",
    ):
        review = json.loads((base / fname).read_text(encoding="utf-8"))
        assert review["t17_complete"] is False, (
            f"{fname} flipped t17_complete to True without re-recording "
            "the diagnostic; t17 must not be silently marked complete."
        )
        assert review["t12_complete"] is False, (
            f"{fname} flipped t12_complete to True without re-recording "
            "the diagnostic; t12 must not be silently marked complete."
        )
        assert review["quality_pass"] is False, (
            f"{fname} flipped quality_pass to True without re-recording "
            "the diagnostic; the Agent's quality pass must remain in sync "
            "with the failure catalog."
        )

    # Per-review non-destructive probe signals must also hold.
    cognition = json.loads(
        (base / "t17-cognition-agent-review.json").read_text(encoding="utf-8")
    )
    assert cognition["baseline_mutation"] is False, (
        "t17-cognition-agent-review.json baseline_mutation flipped to True; "
        "the cognition probe must not have mutated the canonical baseline."
    )
    matrix_v2 = json.loads(
        (base / "t17-matrix-v2-agent-review.json").read_text(encoding="utf-8")
    )
    assert matrix_v2["canonical_baselines_unchanged"] is True, (
        "t17-matrix-v2-agent-review.json canonical_baselines_unchanged "
        "flipped to False; the matrix v2 run must not have mutated the "
        "canonical baselines."
    )


def test_small_probes_pin_frozen_source_sha_and_budget_consumption():
    """Per-feature probes must keep their frozen source SHA and budget.

    The detail-review, grouped-repair, and unit-literal-options
    probes each declare a single source SHA fingerprint (their
    frozen input) and a native call budget that must be
    consumed exactly:

      * ``real-model-detail-review-v7.json`` — ``source_sha256`` is
        the byte-level SHA of the saved-evidence input the v7
        review was tested against; ``actual_calls == 2 ==
        native_call_budget``.
      * ``real-model-grouped-repair-v1.json`` —
        ``source_report_sha256`` is the byte-level SHA of the
        diagnostic report the grouped repair was run on;
        ``actual_native_calls == 2 == native_call_ceiling``.
      * ``real-model-unit-literal-options-v1.json`` —
        ``probe_source_sha256`` is the byte-level SHA of the
        literal-options probe input;
        ``actual_native_calls == 2 == native_call_ceiling``.

    All three are explicitly read-only probes
    (``publication: False``, ``terminal: True``) and all three
    must keep their frozen source SHA so a later "I ran the
    same probe" claim can cite the same input.
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"

    detail = json.loads(
        (base / "real-model-detail-review-v7.json").read_text(encoding="utf-8")
    )
    assert detail["source_sha256"] == (
        "4cd263c70b37a9f7da140de75d8297b2cf52e6d19a950256a301fcf1575ea5b5"
    ), (
        f"real-model-detail-review-v7.json source_sha256 drifted to "
        f"{detail['source_sha256']!r}; the v7 review probe's saved-evidence "
        "input is no longer byte-stable."
    )
    assert detail["actual_calls"] == detail["native_call_budget"], (
        f"real-model-detail-review-v7.json actual_calls={detail['actual_calls']} "
        f"!= native_call_budget={detail['native_call_budget']}; the v7 review "
        "probe no longer consumes its full budget."
    )
    assert detail["publication"] is False
    assert detail["terminal"] is True

    grouped = json.loads(
        (base / "real-model-grouped-repair-v1.json").read_text(encoding="utf-8")
    )
    assert grouped["source_report_sha256"] == (
        "84247f0f214bcee51718942713b449778283ed4da2b5cc35cafce56f552bd573"
    ), (
        f"real-model-grouped-repair-v1.json source_report_sha256 drifted to "
        f"{grouped['source_report_sha256']!r}; the grouped repair's input "
        "report is no longer byte-stable."
    )
    assert grouped["actual_native_calls"] == grouped["native_call_ceiling"], (
        f"real-model-grouped-repair-v1.json actual_native_calls="
        f"{grouped['actual_native_calls']} != native_call_ceiling="
        f"{grouped['native_call_ceiling']}; the grouped repair probe no "
        "longer consumes its full budget."
    )
    assert grouped["publication"] is False
    assert grouped["terminal"] is True

    literal = json.loads(
        (base / "real-model-unit-literal-options-v1.json").read_text(encoding="utf-8")
    )
    assert literal["probe_source_sha256"] == (
        "0473ebdd996d1d0f3a1df72d44d8fa962bef07e6685821241c99d8032c1a5c62"
    ), (
        f"real-model-unit-literal-options-v1.json probe_source_sha256 drifted "
        f"to {literal['probe_source_sha256']!r}; the literal-options probe's "
        "input is no longer byte-stable."
    )
    assert literal["actual_native_calls"] == literal["native_call_ceiling"], (
        f"real-model-unit-literal-options-v1.json actual_native_calls="
        f"{literal['actual_native_calls']} != native_call_ceiling="
        f"{literal['native_call_ceiling']}; the literal-options probe no "
        "longer consumes its full budget."
    )
    assert literal["publication"] is False
    assert literal["terminal"] is True


def test_anchored_and_mentions_prototypes_share_input_pair():
    """Anchored and mentions prototypes test the same 2 inputs.

    ``real-model-anchored-discovery-v1.json`` and
    ``real-model-mentions-discovery-v1.json`` are two v1
    prototypes (anchored = scene-based, mentions =
    mention-based) tested on the same pair of frozen
    units. Both diagnostics record two cases with identical
    ``source_input_sha256`` values:

      * case 0 — ``65270ca41c323a8197dd9afa…``
      * case 1 — ``d6dea8f6459e1fc4e73a4433…``

    Locking the shared input pair is the only way to make
    "anchored v1 and mentions v1 are running the same two
    units" a regression-test statement instead of a
    hand-waving claim. The two prototypes must each also
    remain explicitly read-only
    (``publication: False``, ``terminal: True``).
    """
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    expected_input_shas = [
        "65270ca41c323a8197dd9afa",
        "d6dea8f6459e1fc4e73a4433",
    ]
    for fname in (
        "real-model-anchored-discovery-v1.json",
        "real-model-mentions-discovery-v1.json",
    ):
        diagnostic = json.loads((base / fname).read_text(encoding="utf-8"))
        actual_input_shas = [
            c["source_input_sha256"][:24] for c in diagnostic["cases"]
        ]
        assert actual_input_shas == expected_input_shas, (
            f"{fname} case input SHAs drifted from the shared anchored/"
            f"mentions input pair: got {actual_input_shas!r}, expected "
            f"{expected_input_shas!r}. A drift here means the two "
            "prototypes are no longer tested against the same frozen units."
        )
        assert diagnostic["publication"] is False
        assert diagnostic["terminal"] is True
        assert diagnostic["actual_native_calls"] == diagnostic["native_call_ceiling"], (
            f"{fname} actual_native_calls={diagnostic['actual_native_calls']} "
            f"!= native_call_ceiling={diagnostic['native_call_ceiling']}; "
            "the prototype no longer consumes its full budget."
        )
        # The prototype must stay in candidate-identity-v2 policy
        # (i.e. only build candidates, do not grant knowledge or
        # publish Agents). This is the "prototype, not production"
        # policy marker.
        assert diagnostic["model_config"]["policy_version"] == "candidate-identity-v2", (
            f"{fname} policy_version drifted to "
            f"{diagnostic['model_config']['policy_version']!r}; the prototype "
            "must stay on candidate-identity-v2 (not the production policy)."
        )
        # And the prompt version explicitly carries the -prototype-v1 suffix.
        assert diagnostic["model_config"]["prompt_version"].endswith("-prototype-v1"), (
            f"{fname} prompt_version {diagnostic['model_config']['prompt_version']!r} "
            "lost its -prototype-v1 suffix; the prototype marker must remain."
        )


def test_t12_pilot_eight_cases_dataset_pins_layered_gold_standard():
    """The T12 8-pilot gold standard must stay a frozen layered dataset.

    ``t12-quality-cases-v1.json`` is the gold standard for the
    T12 first-version quality evaluation pilot. Per
    ``chat-quality-protocol.md`` Q05 the T12 question set is
    60 boundary + 24 expression = 84; the 8-pilot is the small
    first slice (4 boundary + 4 expression) meant to validate
    the dataset / runner / schema before the full 84 is
    authored. It carries:

      * ``dataset_version`` — the version string for the
        pilot (must remain the same identifier so later
        diagnostics can cite the same set),
      * ``native_call_ceiling`` — the per-pilot call budget
        (8-pilot mirrors t17 six-combination probe at 32),
      * ``manual_continues_per_turn`` — the manual continue
        budget per turn (must not silently grow),
      * ``reviewer_kind`` — must continue to label the
        reviewer as the Agent doing the inspection (not a
        human blind review claim),
      * exactly **8 cases** with the expected
        ``tier`` × ``class`` coverage:
        - boundary + knowable,
        - boundary + unknowable,
        - boundary + belief,
        - boundary + emotion,
        - expression + answer,
        - expression + challenge,
        - expression + comfort,
        - expression + cross_book_hearsay.
        The 8 case set is the contract that gives the pilot
        its name; any future change must re-record the
        diagnostic AND bump the dataset version.

    Locking the dataset shape is the only way to make
    "t12-pilot-eight-v1" a regression-test statement
    instead of a hand-waving claim. The runner
    ``t12-quality-runner.py`` is the parallel of
    ``discussion-acceptance.py`` for this pilot and is
    exercised by ``--dry-run`` to prove the wiring is
    reproducible without consuming any model budget.
    """
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "docs/plans/book-character-agents/validation"
    cases = json.loads(
        (base / "t12-quality-cases-v1.json").read_text(encoding="utf-8")
    )

    assert cases["dataset_version"] == "t12-pilot-eight-v1", (
        f"t12-quality-cases-v1.json dataset_version drifted to "
        f"{cases['dataset_version']!r}; the T12 pilot cites the "
        "dataset by this string, so renaming it silently breaks "
        "the citation chain."
    )
    assert cases["native_call_ceiling"] == 32, (
        f"t12-quality-cases-v1.json native_call_ceiling drifted to "
        f"{cases['native_call_ceiling']}; the 8-pilot budget ceiling "
        "is part of the gold standard (mirrors t17 six-combination)."
    )
    assert cases["manual_continues_per_turn"] == 1, (
        f"t12-quality-cases-v1.json manual_continues_per_turn drifted "
        f"to {cases['manual_continues_per_turn']}; the pilot's "
        "manual-continue budget is part of the gold standard."
    )
    assert "Agent" in cases["reviewer_kind"] and "no claim of human blind" in cases["reviewer_kind"], (
        f"t12-quality-cases-v1.json reviewer_kind drifted to "
        f"{cases['reviewer_kind']!r}; the reviewer must remain the "
        "Agent doing the inspection (no human blind-review claim)."
    )
    assert len(cases["cases"]) == 8, (
        f"t12-quality-cases-v1.json has {len(cases['cases'])} cases, "
        "expected exactly 8 to match the 4-boundary + 4-expression "
        "8-pilot (per chat-quality-protocol.md Q05 '先跑其中八项')."
    )
    # The 8 case (tier, class) pairs are the pilot's ground truth;
    # each case must declare both its tier and its class.
    expected_tier_class = {
        ("boundary", "knowable"),
        ("boundary", "unknowable"),
        ("boundary", "belief"),
        ("boundary", "emotion"),
        ("expression", "answer"),
        ("expression", "challenge"),
        ("expression", "comfort"),
        ("expression", "cross_book_hearsay"),
    }
    actual_tier_class = {
        (c["tier"], c["class"]) for c in cases["cases"]
    }
    assert actual_tier_class == expected_tier_class, (
        f"t12-quality-cases-v1.json tier/class coverage drifted: "
        f"got {actual_tier_class!r}, expected {expected_tier_class!r}. "
        "The 4 boundary classes (knowable / unknowable / belief / emotion) "
        "and 4 of 6 expression classes (answer / challenge / comfort / "
        "cross_book_hearsay) are the 8-pilot's contract."
    )
    # Each case must carry the same required fields so the
    # runner can iterate them uniformly.
    required_case_fields = {
        "case_id",
        "tier",
        "class",
        "target_actor_indices",
        "questions",
        "gold_standard",
        "expected",
    }
    for c in cases["cases"]:
        missing = required_case_fields - set(c.keys())
        assert not missing, (
            f"t12-quality-cases-v1.json case {c.get('case_id')!r} "
            f"is missing required fields {missing!r}."
        )
    # Each case's gold_standard must carry the four fields that
    # the runner validates (verdict / required_claims / forbidden_claims /
    # expected_source). These are the Q05 '金标准' fields.
    required_gold_fields = {
        "verdict",
        "required_claims",
        "forbidden_claims",
        "expected_source",
    }
    for c in cases["cases"]:
        gold = c.get("gold_standard", {})
        missing_gold = required_gold_fields - set(gold.keys())
        assert not missing_gold, (
            f"t12-quality-cases-v1.json case {c['case_id']!r} "
            f"gold_standard is missing fields {missing_gold!r}; "
            "the Q05 gold standard requires all four."
        )
    # verdict must be one of the documented values from the
    # dataset's verdict_legend; this keeps the runner's switch
    # logic stable against silent renames.
    valid_verdicts = set(cases["verdict_legend"].keys())
    for c in cases["cases"]:
        verdict = c["gold_standard"]["verdict"]
        assert verdict in valid_verdicts, (
            f"t12-quality-cases-v1.json case {c['case_id']!r} "
            f"verdict {verdict!r} is not in verdict_legend "
            f"{valid_verdicts!r}; verdict values must stay in sync "
            "with the dataset's documented legend."
        )
    # The pilot's tier_breakdown must report the same 4+4 split
    # as the actual cases; if the cases grow to cover the
    # remaining 2 expression classes, this check will fail and
    # force a dataset version bump to t12-pilot-ten-v1.
    breakdown = cases.get("tier_breakdown", {})
    assert breakdown.get("boundary_cases") == 4, (
        f"t12-quality-cases-v1.json tier_breakdown.boundary_cases "
        f"is {breakdown.get('boundary_cases')!r}, expected 4."
    )
    assert breakdown.get("expression_cases") == 4, (
        f"t12-quality-cases-v1.json tier_breakdown.expression_cases "
        f"is {breakdown.get('expression_cases')!r}, expected 4."
    )
    # The runner must exist; this protects the t12-pilot-eight-v1
    # dataset from being orphaned by a deleted runner.
    runner_path = (
        Path(__file__).resolve().parents[1]
        / "docs/plans/book-character-agents/t12-quality-runner.py"
    )
    assert runner_path.exists(), (
        "t12-quality-runner.py missing at "
        f"{runner_path}; the 8-pilot dataset is paired with this runner."
    )


def test_t12_pilot_runner_dry_run_produces_frozen_non_destructive_shape():
    """The T12 8-pilot runner's dry-run output must stay byte-shaped.

    The runner's ``--dry-run`` mode is the only invocation allowed
    under "控制模型调用预算" — it must prove the wiring is
    reproducible without consuming any model budget. The dry-run
    output carries a fixed structural shape:

      * ``mode == "dry_run"`` — explicit signal that no model
        call was made,
      * ``actual_native_calls == 0`` — the no-budget-consumed
        promise,
      * ``publication is False`` and ``terminal is True`` — the
        same "non-destructive probe" contract as the t17
        six-combination matrix probe,
      * ``runner_sha256`` — byte-level fingerprint of the runner
        file; any character change (including whitespace) must
        bump this and the test below will fail,
      * ``dataset_sha256`` and ``actors_source_sha256`` — the
        frozen-input fingerprints cited above,
      * exactly 8 cases, all with ``status == "not_started"``,
      * every case must carry its gold_standard so a future
        reviewer can see the Q05 contract without re-reading
        the dataset file.

    This is the dry-run companion to ``test_t12_pilot_eight_cases_
    dataset_pins_layered_gold_standard``: that test pins the
    dataset; this one pins the runner's wiring.
    """
    import hashlib
    import json
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    runner_path = repo / "docs/plans/book-character-agents/t12-quality-runner.py"
    output_path = repo / "tmp" / "t12-pilot-eight-v1-dryrun-fixture.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    proc = subprocess.run(
        [
            sys.executable,
            str(runner_path),
            "--workspace",
            str(repo / "tmp"),
            "--output",
            str(output_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo),
    )
    assert proc.returncode == 0, (
        "t12-quality-runner.py --dry-run failed: "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["mode"] == "dry_run", (
        f"dry-run report mode drifted to {report['mode']!r}; "
        "the dry-run mode label is the explicit 'no model call "
        "was made' signal and must remain 'dry_run'."
    )
    assert report["actual_native_calls"] == 0, (
        f"dry-run report actual_native_calls={report['actual_native_calls']} "
        "!= 0; the dry-run path must not spend any model budget."
    )
    assert report["publication"] is False, (
        "dry-run report publication must remain False; a dry-run "
        "must never write to canonical baselines or Agents."
    )
    assert report["terminal"] is True, (
        "dry-run report terminal must remain True; the dry-run "
        "is a complete, non-resumable validation record."
    )
    assert report["quality_pass"] is False, (
        "dry-run report quality_pass must remain False; a "
        "validation-only run cannot claim quality pass."
    )
    assert report["native_call_ceiling"] == 32
    assert len(report["cases"]) == 8, (
        f"dry-run report has {len(report['cases'])} cases, expected 8."
    )
    for case in report["cases"]:
        assert case["status"] == "not_started", (
            f"dry-run case {case['case_id']!r} status is "
            f"{case['status']!r}; every dry-run case must remain "
            "'not_started' since no model budget is consumed."
        )
        # The dry-run report must carry the gold standard for
        # each case so a reviewer can audit the Q05 contract
        # without re-reading the dataset file.
        assert "gold_standard" in case, (
            f"dry-run case {case['case_id']!r} missing gold_standard; "
            "the runner must echo the Q05 gold standard into the "
            "report so the pilot's contract is auditable from the "
            "report alone."
        )
        gold = case["gold_standard"]
        for key in ("verdict", "required_claims", "forbidden_claims", "expected_source"):
            assert key in gold, (
                f"dry-run case {case['case_id']!r} gold_standard "
                f"missing {key!r}; the Q05 gold standard must be "
                "echoed intact."
            )
    # The runner file's byte-level SHA must be cited in the
    # report itself; this is the same pattern as t17-matrix-v2
    # diagnostic's runner_sha256. Any whitespace / prompt change
    # in the runner bumps this and forces the test below to
    # be re-recorded with the new SHA, exactly as the t17
    # runner_sha256 test does for discussion-acceptance.py.
    expected_runner_sha = hashlib.sha256(runner_path.read_bytes()).hexdigest()
    assert report["runner_sha256"] == expected_runner_sha, (
        f"dry-run report runner_sha256={report['runner_sha256']!r} "
        f"does not match current runner file SHA={expected_runner_sha!r}; "
        "either the runner was edited without re-recording the "
        "diagnostic, or someone hand-edited the SHA in the report. "
        "Re-run the dry-run to refresh the in-report fingerprint."
    )
