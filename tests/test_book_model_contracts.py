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
