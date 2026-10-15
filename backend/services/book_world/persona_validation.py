"""Literal source checks complement semantic review; neither invents permissions."""

import re
from typing import Any, cast

from .discovery_models import DiscoverySpan
from .persona_models import ClaimProposal, PersonaBatch, PersonaReview, RevisedPersonaReview


def parse_json(raw: str) -> str:
    if len(raw) > 100000:
        raise ValueError("Model result exceeds limit")
    raw = raw.strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[7:-3].strip()
    return raw


def resolve_span(span: DiscoverySpan, rows: dict[str, str]) -> DiscoverySpan:
    text = rows.get(span.segment_id)
    if text is None:
        raise ValueError("Evidence belongs to another input scope")
    start = span.local_start
    resolution = "model"
    if text[start : span.local_end] != span.quote:
        start = text.find(span.quote)
        if start < 0 or text.find(span.quote, start + 1) >= 0:
            raise ValueError(
                "Quote absent or ambiguous; supply precise offsets or a longer verbatim quote"
            )
        resolution = "unique_quote"
    return cast(
        DiscoverySpan,
        span.model_copy(
            update={
                "local_start": start,
                "local_end": start + len(span.quote),
                "offset_resolution": resolution,
            }
        ),
    )


def validate_batch(
    raw: str, data: dict[str, Any], *, require_explicit_excerpt: bool = False
) -> PersonaBatch:
    batch = PersonaBatch.model_validate_json(parse_json(raw))
    rows = {row["id"]: row["text"] for row in data["segments"]}
    people = {person["id"]: person for person in data["characters"]}
    keys: set[str] = set()
    normalized: list[ClaimProposal] = []
    previous = {claim["id"]: claim for claim in data["prior_claims"]}
    for claim_index, claim in enumerate(batch.claims):
        if claim.local_key in keys or not claim.proposition.strip():
            raise ValueError("Duplicate claim key or empty proposition")
        keys.add(claim.local_key)
        if claim.owner_character_id and claim.owner_character_id not in people:
            raise ValueError("Claim owner is outside the supplied identities")
        if claim.slot_key and (
            claim.kind in ("fact", "episode")
            or not re.fullmatch(
                r"(?:belief|trait|relation|emotion|style|motivation|value):[^\s].{0,100}",
                claim.slot_key,
            )
        ):
            raise ValueError("Invalid persona slot")
        if claim.slot_key:
            prefix = claim.slot_key.split(":", 1)[0]
            if prefix in ("motivation", "value") and claim.kind not in (
                "trait",
                "belief",
                "relation",
            ):
                raise ValueError(
                    "Motivation/value must come from personal trait, belief or relation"
                )
            if prefix not in ("motivation", "value") and prefix != claim.kind:
                raise ValueError("Persona slot must match the claim kind")
        evidence = [resolve_span(span, rows) for span in claim.evidence]
        access = []
        granted: set[str] = set()
        for grant_index, grant in enumerate(claim.access):
            if require_explicit_excerpt and "approved_excerpt" not in grant.model_fields_set:
                raise ValueError(
                    f"claims.{claim_index}.access.{grant_index}.approved_excerpt is required; "
                    "choose a safe claim evidence excerpt or explicitly use an empty string"
                )
            if grant.character_id not in people or grant.character_id in granted:
                raise ValueError("Foreign or duplicate access identity")
            granted.add(grant.character_id)
            if claim.kind != "fact" and grant.character_id != claim.owner_character_id:
                raise ValueError("Cannot grant another person's private claim")
            acquisition = resolve_span(grant.acquisition, rows)
            identity_evidence = (
                resolve_span(grant.identity_evidence, rows) if grant.identity_evidence else None
            )
            person = people[grant.character_id]
            if person["presence"] not in ("active", "silent") or (
                grant.route != "common"
                and not any(
                    alias in acquisition.quote
                    or (identity_evidence and alias in identity_evidence.quote)
                    for alias in person["aliases"]
                )
            ):
                raise ValueError(
                    f"Acquisition for {person['name']} needs a present person and a literal name in acquisition or identity_evidence"
                )
            if grant.route == "common" and claim.kind != "fact":
                raise ValueError("Common knowledge applies only to world facts")
            if grant.approved_excerpt and not any(
                grant.approved_excerpt in span.quote for span in evidence
            ):
                raise ValueError("Approved excerpt is not within claim evidence")
            access.append(
                grant.model_copy(
                    update={"acquisition": acquisition, "identity_evidence": identity_evidence}
                )
            )
        target = (
            previous.get(claim.supersedes_claim_id)
            if claim.supersedes_claim_id
            else next(
                (item for item in normalized if item.local_key == claim.supersedes_local_key), None
            )
        )
        if claim.supersedes_claim_id or claim.supersedes_local_key:
            if target is None:
                raise ValueError("Correction target must be a supplied earlier claim")
            owner = (
                target["owner_character_id"]
                if isinstance(target, dict)
                else target.owner_character_id
            )
            slot = target["slot_key"] if isinstance(target, dict) else target.slot_key
            if owner != claim.owner_character_id or not slot or slot != claim.slot_key:
                raise ValueError("Correction must be for the same person and slot")
        normalized.append(claim.model_copy(update={"evidence": evidence, "access": access}))
    return cast(PersonaBatch, batch.model_copy(update={"claims": normalized}))


def validate_review(raw: str, batch: PersonaBatch, data: dict[str, Any]) -> PersonaReview:
    model = RevisedPersonaReview if data.get("correction_hints") else PersonaReview
    review = model.model_validate_json(parse_json(raw))
    if isinstance(review, RevisedPersonaReview):
        requested = {hint["local_key"] for hint in data["correction_hints"]}
        reviewed = [check.local_key for check in review.revision_checks]
        if len(reviewed) != len(requested) or set(reviewed) != requested:
            raise ValueError("Review must assess every ownership correction exactly once")
    expected = {claim.local_key: claim for claim in batch.claims}
    if len(review.claims) != len(expected) or {item.local_key for item in review.claims} != set(
        expected
    ):
        raise ValueError("Review must cover every proposal exactly once")
    people = {person["id"] for person in data["characters"]}
    ids = [item.character_id for item in review.identities]
    if len(ids) != len(set(ids)) or not set(ids) <= people:
        raise ValueError("Invalid reviewed identity")
    for item in review.claims:
        proposed = {grant.character_id for grant in expected[item.local_key].access}
        actual = [grant.character_id for grant in item.access]
        if len(actual) != len(set(actual)) or set(actual) != proposed:
            raise ValueError("Review may not add or omit access identities")
    rows = {row["id"]: row["text"] for row in data["segments"]}
    identities = {person["id"]: person for person in data["characters"]}
    normalized_claims = []
    for item in review.claims:
        grants = [
            grant.model_copy(
                update={
                    "before_death_evidence": resolve_span(grant.before_death_evidence, rows)
                    if grant.before_death_evidence
                    else None,
                    "after_resurrection_evidence": resolve_span(
                        grant.after_resurrection_evidence, rows
                    )
                    if grant.after_resurrection_evidence
                    else None,
                }
            )
            for grant in item.access
        ]
        normalized_claims.append(item.model_copy(update={"access": grants}))
    events = []
    for event in review.life_events:
        person = identities.get(event.character_id)
        proof = resolve_span(event.evidence, rows)
        if (
            person is None
            or person["entity_kind"] != "person"
            or not any(alias in proof.quote for alias in person["aliases"])
        ):
            raise ValueError("Life boundary requires this identified person's literal evidence")
        if event.resurrection_supported and (
            event.state != "alive"
            or event.temporal_state != "current"
            or not any(word in proof.quote for word in ("复活", "还魂", "回生", "重生"))
        ):
            raise ValueError("Resurrection must be explicit and current")
        events.append(event.model_copy(update={"evidence": proof}))
    return cast(
        PersonaReview,
        review.model_copy(update={"claims": normalized_claims, "life_events": events}),
    )


def apply_life_events(current: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    states = dict(current)
    for event in events:
        previous = states.get(event["character_id"])
        if event["temporal_state"] == "historical":
            if previous is None:
                states[event["character_id"]] = {**event, "state": "uncertain"}
            continue
        if event["temporal_state"] == "uncertain":
            states[event["character_id"]] = {
                **event,
                "state": "uncertain",
                "last_confirmed_state": previous["state"] if previous else "unknown",
            }
            continue
        if (
            event["state"] == "dead"
            or not previous
            or previous["state"] not in ("dead", "uncertain")
            or (event.get("resurrection_supported") and event["temporal_state"] == "current")
        ):
            states[event["character_id"]] = event
    return states
