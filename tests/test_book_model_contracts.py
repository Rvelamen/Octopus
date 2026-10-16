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
