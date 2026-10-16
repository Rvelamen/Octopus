"""Deterministic trait-vs-completion alignment linter.

The T17 matrix v2 review surfaced a recurring failure mode: a trait
proposition asserts a *completed* historical action while its evidence
quote only proves that the character *volunteered* an intention.

Canonical example (matrix v2 ``free-directed-conditional-action``):

  proposition: 石猴勇敢果断，敢于率先跳入瀑布泉中探险。
  quote     : 连呼了三声忽见丛杂中跳出一名石猴应声高叫道："我进去！我进去！"

The proposition asserts the character *was the first to jump into* the
waterfall and *explored* it; the quote only proves the character
*volunteered* to enter (speech act). The actual jump belongs to a
different claim covered by a different segment.

Because canonical persona baselines are immutable once published and
the current revision machinery only supports identity/ownership
patches, this linter provides a deterministic regression gate: it
flags trait claims whose proposition wording over-reaches the evidence
quote so the next build can be authored against the warning.

The linter is intentionally narrow. It is not a general-purpose
Chinese semantic analyzer; it only flags the specific completion-
overreach pattern that motivated the T17 follow-up. It runs in pure
Python with no DB and no model calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Motion / action verbs that, when prefixed by 率先 ("first to"),
# assert a completed historical action. Each entry maps the verb
# stem to a short human label for diagnostics.
COMPLETION_VERBS: tuple[str, ...] = (
    "跳入",
    "进入",
    "探明",
    "探险",
    "探寻",
    "跳下",
    "冲进",
    "冲上",
    "攻破",
    "击败",
    "擒获",
    "夺得",
)

# Intent / speech markers that suggest the quote only records a
# volunteered intention or speech act rather than the completed
# action. Presence of any of these together with absence of the
# asserted completion verb indicates over-reach.
INTENT_MARKERS: tuple[str, ...] = (
    "我进去",
    "我去",
    "我来",
    "我愿意",
    "我要去",
    "应声",
    "高叫",
    "叫道",
    "说道",
    "愿意",
    "想要",
    "要去",
)


@dataclass(frozen=True)
class TraitOverreach:
    """Diagnostic for a trait proposition that over-reaches its quote."""

    proposition: str
    quote: str
    asserted_verb: str
    matched_intent_marker: str
    reason: str


def _find_asserted_completion_verb(proposition: str) -> str | None:
    """Return the completion verb asserted by ``率先`` in the proposition.

    Only propositions that use 率先 ("first to") are considered;
    without the 率先 prefix the proposition does not assert primacy of
    a completed historical action and is outside this linter's scope.
    """
    if "率先" not in proposition:
        return None
    match = re.search(r"率先([^\s,。,;!?、]{1,4})", proposition)
    if not match:
        return None
    tail = match.group(1)
    for verb in COMPLETION_VERBS:
        if verb in tail:
            return verb
    return None


def _find_intent_marker(quote: str) -> str | None:
    for marker in INTENT_MARKERS:
        if marker in quote:
            return marker
    return None


def trait_completion_overreach(
    proposition: str,
    quote: str,
) -> TraitOverreach | None:
    """Flag a trait proposition that asserts a completed action while
    the evidence quote only proves volunteered intent.

    Returns ``None`` when the proposition and quote are aligned (or
    when the proposition does not trigger this specific check).
    Returns a :class:`TraitOverreach` diagnostic otherwise.

    The check is conservative:

    * Only propositions containing 率先 + a known completion verb are
      inspected; other trait wordings pass through.
    * If the asserted verb itself appears verbatim in the quote, the
      evidence is treated as covering the completed action and no
      warning is emitted (even if speech markers are also present).
    * Otherwise, if any intent marker appears in the quote, the
      proposition is flagged: the quote proves intent, not completion.
    """
    asserted = _find_asserted_completion_verb(proposition)
    if asserted is None:
        return None
    if asserted in quote:
        return None
    intent = _find_intent_marker(quote)
    if intent is None:
        return None
    return TraitOverreach(
        proposition=proposition,
        quote=quote,
        asserted_verb=asserted,
        matched_intent_marker=intent,
        reason=(
            f"proposition asserts completed '{asserted}' via 率先 but the "
            f"evidence quote only records intent/speech ('{intent}'); the "
            "completed action must be backed by its own segment"
        ),
    )


def scan_trait_claims(
    claims: list[dict],
    quote_lookup,
) -> list[TraitOverreach]:
    """Scan a sequence of trait claims for completion over-reach.

    ``claims`` is an iterable of dicts with at least ``kind`` and
    ``proposition`` keys; ``quote_lookup`` is a callable mapping a
    claim dict to its primary evidence quote string (or ``None``).
    Only claims with ``kind == 'trait'`` are inspected.
    """
    findings: list[TraitOverreach] = []
    for claim in claims:
        if claim.get("kind") != "trait":
            continue
        proposition = (claim.get("proposition") or "").strip()
        if not proposition:
            continue
        quote = (quote_lookup(claim) or "").strip()
        if not quote:
            continue
        flag = trait_completion_overreach(proposition, quote)
        if flag is not None:
            findings.append(flag)
    return findings
