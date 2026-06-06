"""Seed built-in subagent configurations on startup."""

from loguru import logger

DISTILLER_SYSTEM_PROMPT = """\
You are a **document distillation expert**. Your job is to read unstructured documents \
(PDF, DOCX, TXT) and extract key information into clean, well-structured Markdown notes.

## Available Tools
- `read` — Read a document (supports PDF, DOCX, TXT, MD)
- `write` — Save extracted notes as Markdown **(ALWAYS call this!)**
- `kb_search` — **Full-text search** for related notes in the knowledge base (searches titles and contents)
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
3. **Use `kb_search` at least 2 times with different keywords before writing**
4. For the most relevant results, use `kb_read_note` to verify the exact title before writing `[[...]]` links
5. **Add at least 2-5 wiki-style links `[[Exact Note Title]]` to existing related notes**
6. Add 2-4 relevant #tags in the content to improve discoverability
7. If information is missing from the document, state it explicitly
8. Focus on the user's extraction request; don't add unrelated content
9. **ALWAYS call the `write` tool — never skip this step!**
10. If the document is long, prioritise the most important information
"""


DEFAULT_AVAILABLE_TOOLS = [
    ("read", "Read File", "Read file contents from the filesystem", "filesystem", 1),
    ("write", "Write File", "Write content to a file", "filesystem", 2),
    ("edit", "Edit File", "Edit file using search and replace", "filesystem", 3),
    ("list", "List Directory", "List directory contents", "filesystem", 4),
    ("glob", "Glob Pattern", "Find files matching a pattern", "filesystem", 5),
    ("grep", "Grep Search", "Search for patterns in files", "filesystem", 6),
    ("exec", "Execute Command", "Run shell commands", "shell", 7),
    ("action", "Action", "Perform actions and operations", "action", 8),
    ("message", "Message", "Send messages to users", "communication", 9),
    (
        "kb_search",
        "KB Search",
        "Search the knowledge base for notes by path or title",
        "knowledge",
        10,
    ),
    ("kb_timeline", "KB Timeline", "Preview a note's context before reading", "knowledge", 11),
    (
        "kb_read_note",
        "KB Read Note",
        "Read the full content of a knowledge base note",
        "knowledge",
        12,
    ),
    (
        "kb_write_note",
        "KB Write Note",
        "Write or overwrite a knowledge base note with automatic indexing",
        "knowledge",
        13,
    ),
    (
        "kb_list_links",
        "KB List Links",
        "List bidirectional links for a given note path",
        "knowledge",
        14,
    ),
    (
        "library_search",
        "Library Search",
        "Search the library for papers and AI notes by title or content",
        "library",
        15,
    ),
    (
        "library_timeline",
        "Library Timeline",
        "Preview a library note's context before reading",
        "library",
        16,
    ),
    (
        "library_read_note",
        "Library Read Note",
        "Read the full content of a library note",
        "library",
        17,
    ),
    (
        "library_list_links",
        "Library List Links",
        "List bidirectional links for a given library note path",
        "library",
        18,
    ),
    (
        "library_write_note",
        "Library Write Note",
        "Write or overwrite a library note with automatic indexing",
        "library",
        19,
    ),
    (
        "workflow_list",
        "Workflow List",
        "List all available workflows that can be executed",
        "workflow",
        20,
    ),
    (
        "workflow_run",
        "Workflow Run",
        "Execute a workflow by ID or name and return the result",
        "workflow",
        21,
    ),
    (
        "memory_write",
        "Memory Write",
        "Add, replace, or remove curated memory entries",
        "memory",
        22,
    ),
    ("memory_search", "Memory Search", "Search observations and memory by keyword", "memory", 20),
    ("memory_read", "Memory Read", "Read curated memory or user profile", "memory", 21),
    (
        "memory_timeline",
        "Memory Timeline",
        "Get memory timeline for a session instance",
        "memory",
        22,
    ),
    (
        "browser",
        "Browser",
        "Automate browser navigation, interaction, and screenshots",
        "browser",
        23,
    ),
    ("web_fetch", "Web Fetch", "Fetch web page content via HTTP", "web", 24),
    ("image_understand", "Image Understand", "Analyze and describe images", "image", 25),
    ("image_generate", "Image Generate", "Generate images from text descriptions", "image", 26),
    ("spawn", "Spawn", "Spawn subagents for background tasks", "agent", 27),
    ("cron", "Cron", "Schedule recurring tasks", "scheduler", 28),
    # Workflow designer tools
    ("add_node", "Add Node", "Add a node to the workflow canvas", "workflow", 100),
    ("connect_nodes", "Connect Nodes", "Connect two workflow nodes", "workflow", 101),
    ("set_variable", "Set Variable", "Bind a node input to upstream output", "workflow", 102),
    ("remove_node", "Remove Node", "Remove a node from the workflow", "workflow", 103),
    ("update_node", "Update Node", "Update an existing node configuration", "workflow", 104),
    ("get_node_io", "Get Node IO", "Get node input/output definitions", "workflow", 105),
    ("get_nodes", "Get Nodes", "Get all nodes with full configurations", "workflow", 106),
    ("add_input_variable", "Add Input Variable", "Add an input slot to a node", "workflow", 107),
    ("add_output_variable", "Add Output Variable", "Add an output slot to a node", "workflow", 108),
    ("remove_variable", "Remove Variable", "Remove an input or output variable", "workflow", 109),
    ("auto_layout", "Auto Layout", "Automatically arrange workflow nodes", "workflow", 110),
    (
        "validate_workflow",
        "Validate Workflow",
        "Check workflow for structural errors",
        "workflow",
        111,
    ),
    ("run_test", "Run Test", "Execute workflow in test mode", "workflow", 112),
    (
        "get_variable_context",
        "Get Variable Context",
        "List available workflow variables",
        "workflow",
        113,
    ),
    (
        "list_database_tables",
        "List Database Tables",
        "List user-defined database tables and schemas",
        "workflow",
        114,
    ),
]


def seed_available_tools(db) -> None:
    """Ensure all built-in tools are present in the available_tools table.

    Called during application startup so that newly-added tools appear in
    the frontend subagent configuration without manual database edits.
    """
    try:
        with db._get_connection() as conn:
            for name, display_name, description, category, sort_order in DEFAULT_AVAILABLE_TOOLS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO available_tools
                    (name, display_name, description, category, enabled, sort_order)
                    VALUES (?, ?, ?, ?, 1, ?)
                """,
                    (name, display_name, description, category, sort_order),
                )
            conn.commit()
        logger.info("Seeded available_tools with defaults")
    except Exception as e:
        logger.warning(f"Failed to seed available_tools: {e}")


LIBRARY_DISTILLER_SYSTEM_PROMPT = """\
You are a **library paper distillation expert**. Your job is to read academic papers \
(PDF, DOCX, TXT) and extract key information into clean, well-structured Markdown notes \
that live in the Library knowledge base.

## Available Tools
- `read` — Read a document (supports PDF, DOCX, TXT, MD)
- `library_search` — **Full-text search** for related papers and notes in the library
- `library_timeline` — Preview a library note's context (links, tags, related notes) before reading
- `library_read_note` — Read an existing library note for context
- `library_list_links` — Explore library knowledge-graph connections
- `library_write_note` — Save extracted notes as Markdown and auto-index to library graph **(ALWAYS call this!)**

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
3. **Use `library_search` at least 2 times with different keywords before writing**
4. For the most relevant results, use `library_read_note` to verify the exact title before writing `[[...]]` links
5. **Add at least 2-5 wiki-style links `[[Exact Note Title]]` to existing related library notes**
6. Add 2-4 relevant #tags in the content to improve discoverability
7. If information is missing from the document, state it explicitly
8. Focus on the user's extraction request; don't add unrelated content
9. **ALWAYS call the `write` tool — never skip this step!**
10. If the document is long, prioritise the most important information
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
            "tools": [
                "read",
                "write",
                "kb_search",
                "kb_read_note",
                "kb_write_note",
                "kb_list_links",
            ],
            "extensions": [],
            "max_iterations": 30,
            "temperature": 0.3,
            "system_prompt": DISTILLER_SYSTEM_PROMPT,
            "enabled": True,
            "is_builtin": True,
        },
        {
            "name": "library-distiller",
            "description": (
                "A library paper distillation expert that reads academic papers "
                "and generates structured summary notes with library knowledge-graph connections."
            ),
            "tools": [
                "read",
                "library_search",
                "library_timeline",
                "library_read_note",
                "library_list_links",
                "library_write_note",
            ],
            "extensions": [],
            "max_iterations": 30,
            "temperature": 0.3,
            "system_prompt": LIBRARY_DISTILLER_SYSTEM_PROMPT,
            "enabled": True,
            "is_builtin": True,
        },
        {
            "name": "pdf-chat",
            "description": "A PDF reading assistant for conversational Q&A about documents.",
            "tools": [
                "read",
                "library_search",
                "library_read_note",
                "memory_search",
                "memory_read",
            ],
            "extensions": [],
            "max_iterations": 10,
            "temperature": 0.5,
            "system_prompt": (
                "You are a helpful PDF reading assistant. You help users understand academic papers "
                "and documents by answering questions based on the provided context and your knowledge. "
                "You can search the knowledge base and read files to provide accurate answers. "
                "Be concise but thorough. When citing information from the PDF, reference the page number if available."
            ),
            "enabled": True,
            "is_builtin": True,
        },
        {
            "name": "library-chat",
            "description": "A library knowledge assistant for conversational Q&A about papers and collections.",
            "tools": [
                "read",
                "list",
                "library_search",
                "library_read_note",
                "library_list_links",
                "library_timeline",
                "memory_search",
                "memory_read",
            ],
            "extensions": [],
            "max_iterations": 10,
            "temperature": 0.5,
            "system_prompt": (
                "You are a helpful Library knowledge assistant. You help users understand and analyze "
                "academic papers and documents in their library collection. You can search library notes, "
                "read PDFs, list directories, and explore note relationships to provide accurate answers."
            ),
            "enabled": True,
            "is_builtin": True,
        },
    ]

    WORKFLOW_DESIGNER_SYSTEM_PROMPT = """\
You are a **workflow design expert** for the Octopus platform.

Your job is to help users create and modify visual workflows through tool calls.

## Available Tools
- `add_node` — Add a new node to the canvas
- `connect_nodes` — Connect two nodes with an edge
- `set_variable` — Bind a node's input to an upstream output using {{nodeId.outputKey}}
- `remove_node` — Remove a node from the canvas
- `auto_layout` — Rearrange all nodes neatly
- `validate_workflow` — Check for structural errors
- `run_test` — Execute the workflow in test mode
- `get_variable_context` — List all available variables
- `read` — Read files
- `write` — Write files

## Design Rules
1. EVERY workflow MUST have `workflowStart` and `workflowEnd` nodes
2. Use Chinese for node names (e.g. "智能回复", "问题分类")
3. Prefer linear structures; use branches only when necessary
4. After adding nodes, automatically call `validate_workflow`
5. If validation fails, fix the errors before reporting success
6. Call `auto_layout` after structural changes

## Variable Binding
- Syntax: {{nodeId.outputKey}}
- Examples: {{start-1.userChatInput}}, {{llm-1.output}}
- If the system auto-binds a variable, confirm it in your response
- For uncertain bindings, the system will use {{?}} placeholder

## Node Type Reference
- workflowStart: Entry point, no default outputs. User must add custom input variables via add_input_variable/add_output_variable
- workflowEnd: Exit point, input result[string]
- llm / chatNode: LLM call. FIXED params (use update_node): systemPrompt[string], userPrompt[string], temperature[number], maxToken[number]; INPUT variable (use set_variable): input[string]; OUTPUT: output[string]
- classifyQuestion: Classification, input input[string], output cqResult[string]
- contentExtract: Extraction, input input[string], output extractResult[string]
- http / httpRequest468: HTTP request, input url[string], method[string], output body[string], statusCode[integer], headers[object]
- code: Python code, output result[string]
- ifElseNode: Conditional branch, input condition[string], outputs system_resultTrue, system_resultFalse
- textEditor: Text processing, input text[string], output result[string]
- jsonDeserialize: JSON parse, input json[string], output object[object]
- readFiles: File reading, output content[string]
- variableUpdate: Variable update, output updatedValue[string]
- loop: Loop container
- parallelRun: Parallel execution

## Response Style
1. Explain your design plan in natural language first
2. Then call the necessary tools
3. Report the final result including what was created and any {{?}} placeholders
"""

    builtin.append(
        {
            "name": "workflow-designer",
            "description": (
                "A workflow design expert that creates and modifies visual workflows "
                "through natural language conversation and tool calls."
            ),
            "tools": [
                "add_node",
                "connect_nodes",
                "set_variable",
                "add_input_variable",
                "add_output_variable",
                "remove_variable",
                "get_node_io",
                "get_nodes",
                "remove_node",
                "update_node",
                "auto_layout",
                "validate_workflow",
                "run_test",
                "get_variable_context",
                "list_database_tables",
            ],
            "extensions": [],
            "max_iterations": 15,
            "temperature": 0.3,
            "system_prompt": WORKFLOW_DESIGNER_SYSTEM_PROMPT,
            "enabled": True,
            "is_builtin": True,
        }
    )

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
