"""Validate exact provided sources before and alongside independent semantic review."""

import hashlib
import re
import unicodedata
from typing import cast

from .chat_models import UNKNOWN_REPLY, ChatCandidate, ChatReview
from .context import CharacterContext
from .persona_validation import parse_json

_NEGATIVE_AUTOBIOGRAPHY = r"(?:我|俺|在下)(?:还没细看|(?:从未|从没|未曾|不曾)(?:去|见|听说|经历|住|认识|遇|拜|学)|(?:没有|没)(?:去过|到过|见过|听说过|经历过|住过|认识过|拜过|学过|细看))"


def _inside_quote(preceding: str) -> bool:
    return (
        any(
            preceding.count(opening) > preceding.count(closing)
            for opening, closing in (("“", "”"), ("‘", "’"), ("「", "」"))
        )
        or preceding.count('"') % 2 == 1
        or preceding.count("'") % 2 == 1
    )


def _actual_negative_autobiography(text: str) -> bool:
    for match in re.finditer(_NEGATIVE_AUTOBIOGRAPHY, text):
        preceding = text[: match.start()]
        if re.search(r"(?:如果|假如|假设|要是|倘若|若)\s*$", preceding):
            continue
        if not _inside_quote(preceding):
            return True
    return False


def _negative_experience_sentences(text: str) -> list[str]:
    """Recognize explicit denial forms; semantic review still handles other wording."""
    pattern = (
        r"(?:并非|(?:并)?(?:没有|没|未曾|从未|从没|不曾))[^。！？；\n]{0,12}(?:亲眼见过|住在|住过|去过|到过|经历过|听说过|见过|发生过)|"
        + _NEGATIVE_AUTOBIOGRAPHY
    )
    denied = []
    for match in re.finditer(pattern, text):
        preceding = text[: match.start()]
        if _inside_quote(preceding):
            continue
        clause = re.split(r"[，。！？；\n]", preceding)[-1]
        if re.search(r"如果|假如|假设|要是|倘若|若", clause):
            continue
        start = max((preceding.rfind(char) for char in "。！？；\n"), default=-1) + 1
        end_match = re.search(r"[。！？；\n]", text[match.end() :])
        end = match.end() + end_match.start() if end_match else len(text)
        denied.append(text[start:end])
    return denied


def _without_punctuation(text: str) -> str:
    return "".join(
        char
        for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def validate_candidate(raw: str, context: CharacterContext) -> ChatCandidate:
    if (
        hashlib.sha256(context.serialized.encode()).hexdigest()
        != context.diagnostics["context_sha256"]
    ):
        raise ValueError("Actor context changed after composition")
    candidate = ChatCandidate.model_validate_json(parse_json(raw))
    if candidate.dialogue_action == "no_comment" and context.config.prompt_version not in (
        "character-chat-v4",
        "character-chat-v5",
        "character-chat-v6",
        "character-chat-v7",
        "character-chat-v8",
        "character-chat-v9",
        "character-chat-v10",
    ):
        raise ValueError("Silence requires the new versioned chat policy")
    if candidate.dialogue_action != "no_comment" and not candidate.content.strip():
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
        if (
            context.config.prompt_version != "character-chat-v10"
            and assertion.origin == "conversation"
            and _actual_negative_autobiography(assertion.text)
        ):
            raise ValueError(
                "Absence of evidence must not become an unsupported autobiographical event"
            )
        if not set(assertion.message_ids) <= messages:
            raise ValueError("Hearsay is outside the supplied public messages")
        if (
            context.config.prompt_version
            in ("character-chat-v8", "character-chat-v9", "character-chat-v10")
            and assertion.origin == "inference"
            and not re.search(
                r"可能|或许|也许|推测|推想|猜测|猜想|假设|假如|如果|倘若|(?:^|[，。；！？\s])若",
                assertion.text,
            )
        ):
            raise ValueError(
                "Inference must be explicitly hypothetical, not an asserted original-world event"
            )
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
    if context.config.prompt_version == "character-chat-v10":
        for denied in _negative_experience_sentences(candidate.content):
            grounded = any(
                assertion.origin == "canon"
                and denied in assertion.text
                and any(
                    pairs[(ref.claim_id, ref.evidence_id)].route == "firsthand"
                    and re.match(r"^(?:我|俺|在下|并非我)", source.strip())
                    and not any(char in source for char in "“”‘’「」\"'")
                    and _without_punctuation(denied) == _without_punctuation(source)
                    for ref in assertion.refs
                    for source in (pairs[(ref.claim_id, ref.evidence_id)].proposition,)
                    if source
                )
                for assertion in candidate.claims
            )
            if not grounded:
                raise ValueError(
                    "Negative experience needs explicit canonical support for the same event and scope; state current uncertainty or who supplied the information: "
                    + denied[:100]
                )
    if context.config.prompt_version in (
        "character-chat-v8",
        "character-chat-v9",
        "character-chat-v10",
    ):
        trusted_fallback = (
            candidate.content == UNKNOWN_REPLY
            and not candidate.claims
            and candidate.dialogue_action == "express_unknown"
            and not candidate.action_basis_claim_ids
            and candidate.ephemeral_emotion is None
        )
        if not trusted_fallback:
            covered: set[int] = set()
            for assertion in candidate.claims:
                start = candidate.content.find(assertion.text)
                while start >= 0:
                    covered.update(range(start, start + len(assertion.text)))
                    start = candidate.content.find(assertion.text, start + 1)
            missing = next(
                (
                    index
                    for index, char in enumerate(candidate.content)
                    if index not in covered
                    and not char.isspace()
                    and not unicodedata.category(char).startswith("P")
                ),
                None,
            )
            if missing is not None:
                raise ValueError(
                    "Unreviewed body span: " + candidate.content[missing : missing + 80]
                )
    return cast(ChatCandidate, candidate)


class ReviewContractError(ValueError):
    """The review format is invalid; this does not judge the candidate's content."""


class SemanticReviewError(ValueError):
    def __init__(self, message: str, review: ChatReview):
        super().__init__(message)
        self.feedback = {
            "reason": review.reason,
            "unlisted_assertions": review.unlisted_assertions,
            "rejected_ordinals": [
                item.ordinal
                for item in review.claims
                if not (item.supported and item.origin_correct and item.references_complete)
            ],
        }


def validate_review(candidate: ChatCandidate, raw: str) -> ChatReview:
    try:
        review = ChatReview.model_validate_json(parse_json(raw))
    except ValueError as error:
        raise ReviewContractError("Review must return the complete structured contract") from error
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
        raise SemanticReviewError(
            "Independent body/persona/source review rejected the candidate", review
        )
    if any(
        not (item.supported and item.origin_correct and item.references_complete)
        for item in review.claims
    ):
        raise SemanticReviewError(
            "Independent assertion review rejected a source or its meaning", review
        )
    if sorted(item.ordinal for item in review.claims) != list(range(len(candidate.claims))):
        raise ReviewContractError("Review did not cover every assertion exactly once")
    return cast(ChatReview, review)
