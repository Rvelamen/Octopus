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
- Extract observations that capture meaningful work, decisions, findings, or changes.
- Titles must be specific, keyword-rich, and searchable.
- Narratives should explain the WHAT and the WHY in 1-3 sentences.
- When in doubt, extract rather than skip - empty results should be rare.
"""

EXTRACTION_PROMPT_TEMPLATE = """Analyze the conversation snippet below and extract up to 5 structured observations.

Return a JSON array. Even modest but useful observations should be included.

--- Observation Types ---
- gotcha: A hidden trap, edge case, or counter-intuitive behavior that could bite someone later.
- decision: An architectural or design choice with reasoning.
- trade-off: A deliberate compromise between competing goals.
- problem-solution: A bug or issue and how it was fixed.
- what-changed: A concrete code/config change and its effect.
- how-it-works: An explanation of a mechanism or system behavior.
- discovery: A surprising finding or newly learned fact.
- why-it-exists: The rationale behind a feature, rule, or pattern.
- general: Fallback for any notable information that doesn't fit above.

--- Field Schema ---
- type: one of the types above
- title: a short, specific, keyword-rich title (e.g., "Hook timeout too short for npm install on slow networks")
- narrative: 1-3 concise sentences summarizing the insight
- files: array of relevant file paths (empty if none)
- concepts: array of key technical terms or domain concepts (empty if none)
- token_count: rough integer estimate of narrative length in tokens

--- What to Extract ---
- File modifications and their purpose
- Configuration changes and their rationale
- Tool usage patterns and outcomes
- Task completions and their results
- Any work that was done during the conversation
- Decisions made and why
- Problems encountered and solutions found
- API behaviors or limits discovered

--- Examples ---
Good observation: {{"type": "what-changed", "title": "Modified observation_extractor.py to improve extraction", "narrative": "Made changes to the observation extraction logic to capture more meaningful work from the conversation.", "files": ["backend/agent/observation_extractor.py"], "concepts": ["observation", "extraction"], "token_count": 35}}
Good observation: {{"type": "problem-solution", "title": "Fixed memory page not showing data after compression", "narrative": "The memory page was not displaying extracted observations after context compression. Root cause was the LLM returning empty results due to overly strict extraction criteria.", "files": [], "concepts": ["memory", "compression", "LLM"], "token_count": 45}}

Conversation snippet:
{conversation_text}

JSON array:"""


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
    if not raw:
        logger.warning("Observation extraction: empty raw response")
        return []

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first fence line and last fence line
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text:
        logger.warning("Observation extraction: empty text after stripping fences")
        return []

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            logger.warning(f"Observation extraction returned non-list: {type(data)}, content: {text[:200]}")
            return []
        logger.debug(f"Observation extraction parsed {len(data)} observations from LLM response")
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
        logger.info(f"Extracted {len(valid)} observations from {len(messages)} messages (raw count: {len(observations)})")
        if not valid and raw:
            logger.warning(f"LLM returned empty observations. Raw response ({len(raw)} chars): {raw[:500]}")
        return valid
    except Exception as e:
        logger.error(f"Observation extraction failed: {e}")
        return []
