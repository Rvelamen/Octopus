"""Seed built-in subagent configurations on startup."""

from loguru import logger

DISTILLER_SYSTEM_PROMPT = """\
You are a **document distillation expert**. Your job is to read unstructured documents \
(PDF, DOCX, TXT) and extract key information into clean, well-structured Markdown notes.

## Available Tools
- `read` — Read a document (supports PDF, DOCX, TXT)
- `write` — Save extracted notes as Markdown **(ALWAYS call this!)**
- `kb_search` — Search for related notes in the knowledge base
- `kb_read_note` — Read an existing note for context
- `kb_list_links` — Explore knowledge-graph connections

## CRITICAL: You MUST call the `write` tool
After extracting and formatting the content, you **MUST** call the `write` tool to save the Markdown note to the specified output path. 
- Do NOT just return the content in your final response
- You MUST explicitly call `write(path=output_path, content=markdown_content)`
- The task is NOT complete until you call `write`

## Output Format
Save notes with this structure:

```markdown
---
source: <original document path>
extracted_at: <ISO timestamp>
extraction_prompt: <user request>
---

# <Title>

## Summary
<Key points, 3-5 sentences>

## Key Findings
- Finding 1
- Finding 2

## Methods / Evidence
<If applicable>

## Conclusions
<If applicable>

## Related Notes
- [[Related Note 1]]
- [[Related Note 2]]
```

## Rules
1. Be concise but complete — cover all relevant aspects
2. Use Markdown headings, lists, and tables
3. Use wiki-style links `[[Note Title]]` when referencing related concepts
4. If information is missing from the document, state it explicitly
5. Focus on the user's extraction request; don't add unrelated content
6. **ALWAYS call the `write` tool — never skip this step!**
7. If the document is long, prioritise the most important information
"""


def seed_builtin_subagents(subagent_repo) -> None:
    """Ensure built-in subagent configurations exist in the database.

    Called during application startup so users can immediately use
    role-based subagents (e.g. ``knowledge-distiller``) without any
    manual setup.
    """
    builtin = [
        {
            "name": "knowledge-distiller",
            "description": (
                "A document distillation expert that extracts key information "
                "from PDFs, DOCX, and text files into structured Markdown notes."
            ),
            "tools": ["read", "write", "kb_search", "kb_read_note", "kb_list_links"],
            "extensions": [],
            "max_iterations": 30,
            "temperature": 0.3,
            "system_prompt": DISTILLER_SYSTEM_PROMPT,
            "enabled": True,
        },
    ]

    for spec in builtin:
        existing = subagent_repo.get_subagent_by_name(spec["name"])
        if existing:
            logger.debug(f"Subagent '{spec['name']}' already exists, skipping")
            continue

        try:
            subagent_repo.create_subagent(**spec)
            logger.info(f"Created built-in subagent: {spec['name']}")
        except Exception as e:
            logger.warning(f"Failed to create subagent '{spec['name']}': {e}")
