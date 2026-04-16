"""Extract structured observations from conversation messages."""

import json
from enum import Enum
from typing import Any, Callable

from loguru import logger


class ObservationType(str, Enum):
    GOTCHA = "gotcha"
    PROBLEM_SOLUTION = "problem-solution"
    HOW_IT_WORKS = "how-it-works"
    WHAT_CHANGED = "what-changed"
    DISCOVERY = "discovery"
    WHY_IT_EXISTS = "why-it-exists"
    DECISION = "decision"
    TRADE_OFF = "trade-off"
    GENERAL = "general"


OBSERVATION_TYPE_ICON = {
    ObservationType.GOTCHA: "🔴",
    ObservationType.PROBLEM_SOLUTION: "🟡",
    ObservationType.HOW_IT_WORKS: "🔵",
    ObservationType.WHAT_CHANGED: "🟢",
    ObservationType.DISCOVERY: "🟣",
    ObservationType.WHY_IT_EXISTS: "🟠",
    ObservationType.DECISION: "🟤",
    ObservationType.TRADE_OFF: "⚖️",
    ObservationType.GENERAL: "⚪",
}


EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge curator. Your job is to distill conversation snippets into high-signal, reusable observations.

Rules:
- ONLY extract observations that are genuinely novel, non-obvious, or actionable.
- Prefer empty array [] over low-value fluff.
- Titles must be specific, keyword-rich, and searchable.
- Narratives should explain the WHAT and the WHY in 1-3 sentences.
"""

EXTRACTION_PROMPT_TEMPLATE = """Analyze the conversation snippet below and extract up to 3 structured observations.

Return a JSON array. If nothing notable was discussed, return [] exactly.

--- Observation Types ---
- gotcha: A hidden trap, edge case, or counter-intuitive behavior that could bite someone later.
- decision: An architectural or design choice with reasoning.
- trade-off: A deliberate compromise between competing goals.
- problem-solution: A bug or issue and how it was fixed.
- what-changed: A concrete code/config change and its effect.
- how-it-works: An explanation of a mechanism or system behavior.
- discovery: A surprising finding or newly learned fact.
- why-it-exists: The rationale behind a feature, rule, or pattern.
- general: Fallback only if none of the above fit.

--- Field Schema ---
- type: one of the types above
- title: a short, specific, keyword-rich title (e.g., "Hook timeout too short for npm install on slow networks")
- narrative: 1-3 concise sentences summarizing the insight
- files: array of relevant file paths (empty if none)
- concepts: array of key technical terms or domain concepts (empty if none)
- token_count: rough integer estimate of narrative length in tokens

--- Quality Criteria ---
DO extract:
- Fixes with clear root causes
- Configuration changes with rationale
- Surprising API behavior or limits
- Decisions that affect future work

DO NOT extract:
- Generic greetings or status updates
- Vague summaries like "we discussed the project"
- Purely procedural steps without insight
- Obvious facts that need no explanation

--- Examples ---
Bad title (too vague): "About the code change"
Good title: "Increase npm install hook timeout from 60s to 300s"

Bad observation (no insight): {{"type": "general", "title": "We talked about the bug", "narrative": "We discussed a bug in the app.", ...}}
Good observation: {{"type": "gotcha", "title": "SQLite FTS5 auto-sync triggers fail on ALTER TABLE", "narrative": "Adding an ALTER TABLE after creating FTS5 triggers caused the triggers to reference the old schema, leading to silent insert failures. Recreate triggers after schema changes.", "files": ["backend/data/database.py"], "concepts": ["SQLite", "FTS5", "triggers"], "token_count": 45}}

Conversation snippet:
{conversation_text}

JSON array only:"""


def _conversation_text_from_messages(messages: list[dict[str, Any]]) -> str:
    """Build a concise conversation text from messages."""
    lines = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        # Truncate very long contents
        text = str(content)
        if len(text) > 800:
            text = text[:800] + "\n...[truncated]"
        lines.append(f"{role}: {text}")
    return "\n\n".join(lines)


def _parse_observations(raw: str) -> list[dict[str, Any]]:
    """Parse JSON array of observations from LLM response."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first fence line and last fence line
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            logger.warning(f"Observation extraction returned non-list: {type(data)}")
            return []
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse observation JSON: {e}\nRaw: {raw[:500]}")
        return []


async def extract_observations_from_messages(
    messages: list[dict[str, Any]],
    provider: Any,
    model: str,
    provider_type: str,
    record_token_usage: Callable | None = None,
    session_instance_id: int | None = None,
) -> list[dict[str, Any]]:
    """Extract structured observations from a list of messages.

    Args:
        messages: Messages to analyze.
        provider: LLM provider instance.
        model: Model ID.
        provider_type: Provider type string.
        record_token_usage: Optional callback to record token usage.
        session_instance_id: Optional session instance ID for token recording.

    Returns:
        List of observation dicts.
    """
    if len(messages) < 2:
        return []

    conversation_text = _conversation_text_from_messages(messages)
    if len(conversation_text) < 100:
        return []

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(conversation_text=conversation_text)
    extraction_messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await provider.chat(
            messages=extraction_messages,
            tools=[],
            model=model,
        )
        if response.usage and record_token_usage:
            record_token_usage(
                session_instance_id=session_instance_id,
                provider_name=provider_type,
                model_id=model,
                usage=response.usage,
                request_type="observation_extraction",
            )
        raw = response.content or ""
        observations = _parse_observations(raw)
        # Validate fields
        valid = []
        for obs in observations:
            if not isinstance(obs, dict):
                continue
            obs_type = obs.get("type", "general")
            if obs_type not in {t.value for t in ObservationType}:
                obs_type = "general"
            valid.append({
                "type": obs_type,
                "title": str(obs.get("title", "")).strip() or "Untitled observation",
                "narrative": str(obs.get("narrative", "")).strip(),
                "files": list(obs.get("files", [])) if isinstance(obs.get("files"), list) else [],
                "concepts": list(obs.get("concepts", [])) if isinstance(obs.get("concepts"), list) else [],
                "token_count": int(obs.get("token_count", 0)) or 100,
            })
        logger.info(f"Extracted {len(valid)} observations from {len(messages)} messages")
        return valid
    except Exception as e:
        logger.error(f"Observation extraction failed: {e}")
        return []
