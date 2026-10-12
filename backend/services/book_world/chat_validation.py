"""Validate exact provided sources before and alongside independent semantic review."""

import hashlib
import re
from typing import cast

from .chat_models import ChatCandidate, ChatReview
from .context import CharacterContext
from .persona_validation import parse_json


def _actual_negative_autobiography(text: str) -> bool:
    pattern = r"(?:我|俺|在下)(?:还没细看|(?:从未|从没|未曾|不曾)(?:去|见|听说|经历|住|认识|遇|拜|学)|(?:没有|没)(?:去过|到过|见过|听说过|经历过|住过|认识过|拜过|学过|细看))"
    for match in re.finditer(pattern, text):
        preceding = text[: match.start()]
        if re.search(r"(?:如果|假如|假设|要是|倘若|若)\s*$", preceding):
            continue
        quoted = any(
            preceding.count(opening) > preceding.count(closing)
            for opening, closing in (("“", "”"), ("‘", "’"), ("「", "」"))
        )
        quoted = quoted or preceding.count('"') % 2 == 1 or preceding.count("'") % 2 == 1
        if not quoted:
            return True
    return False


def validate_candidate(raw: str, context: CharacterContext) -> ChatCandidate:
    if (
        hashlib.sha256(context.serialized.encode()).hexdigest()
        != context.diagnostics["context_sha256"]
    ):
        raise ValueError("Actor context changed after composition")
    candidate = ChatCandidate.model_validate_json(parse_json(raw))
    if not candidate.content.strip():
        raise ValueError("Empty reply")
    pairs = {(item.claim_id, item.evidence_id): item for item in context.allowed}
    baseline = {item["claim_id"] for item in context.payload["baseline"].values()}
    emotion_patterns = {
        item["claim_id"]
        for item in context.payload["baseline"].values()
        if item["kind"] == "emotion"
    }
    messages = {item["id"] for item in context.payload["room_history"]} | {
        context.payload["current_message"]["id"]
    }
    messages |= {
        source
        for item in context.payload.get("room_memory", {}).get("items", [])
        for source in item["source_message_ids"]
    }
    if not set(candidate.action_basis_claim_ids) <= baseline:
        raise ValueError("Action basis is outside current baseline")
    if candidate.ephemeral_emotion and (
        not set(candidate.ephemeral_emotion.trigger_message_ids) <= messages
        or not set(candidate.ephemeral_emotion.pattern_claim_ids) <= emotion_patterns
    ):
        raise ValueError("Emotion requires current room triggers and canonical emotion patterns")
    for assertion in candidate.claims:
        if not assertion.text.strip() or assertion.text not in candidate.content:
            raise ValueError("Assertion text must identify a verbatim part of the reply")
        if assertion.origin == "conversation" and _actual_negative_autobiography(assertion.text):
            raise ValueError(
                "Absence of evidence must not become an unsupported autobiographical event"
            )
        if not set(assertion.message_ids) <= messages:
            raise ValueError("Hearsay is outside the supplied public messages")
        seen = set()
        for ref in assertion.refs:
            key = ref.claim_id, ref.evidence_id
            proof = pairs.get(key)
            if proof is None or key in seen:
                raise ValueError("Reference is foreign, duplicated or not retrieved for this reply")
            seen.add(key)
            if (assertion.origin == "character_belief") != (
                proof.kind == "belief"
            ) and assertion.origin != "inference":
                raise ValueError("Character belief must not become objective canon")
    return cast(ChatCandidate, candidate)


def validate_review(candidate: ChatCandidate, raw: str) -> ChatReview:
    review = ChatReview.model_validate_json(parse_json(raw))
    if (
        not all(
            (
                review.supported,
                review.facts_complete,
                review.persona_consistent,
                review.action_supported,
                review.emotion_supported,
                review.attribution_correct,
            )
        )
        or review.unlisted_assertions
    ):
        raise ValueError("Independent body/persona/source review rejected the candidate")
    if sorted(item.ordinal for item in review.claims) != list(range(len(candidate.claims))):
        raise ValueError("Review did not cover every assertion exactly once")
    if any(
        not (item.supported and item.origin_correct and item.references_complete)
        for item in review.claims
    ):
        raise ValueError("Independent assertion review rejected a source or its meaning")
    return cast(ChatReview, review)
