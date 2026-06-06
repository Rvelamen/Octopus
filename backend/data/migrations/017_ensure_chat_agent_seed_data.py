"""
Ensure pdf-chat and library-chat subagents exist for existing databases.
Also fixes pdf-chat tools to use library_* names instead of kb_* names.
"""

from yoyo import step

__depends__ = {"016_add_workflow_design_agent_config"}

steps = [
    step(
        """
        -- Ensure library-chat subagent exists
        INSERT OR IGNORE INTO subagents
        (name, description, provider_id, model_id, tools, extensions,
         max_iterations, temperature, system_prompt, enabled, created_at, updated_at, is_builtin)
        VALUES (
            'library-chat',
            'A library knowledge assistant for conversational Q&A about papers and collections.',
            NULL,
            NULL,
            '["read", "list", "library_search", "library_read_note", "library_list_links", "library_timeline", "memory_search", "memory_read"]',
            '[]',
            10,
            0.5,
            'You are a helpful Library knowledge assistant. You help users understand and analyze academic papers and documents in their library collection. You can search library notes, read PDFs, list directories, and explore note relationships to provide accurate answers.',
            1,
            datetime('now', 'localtime'),
            datetime('now', 'localtime'),
            1
        );

        -- Fix pdf-chat tools to use library_* instead of kb_*
        UPDATE subagents
        SET tools = '["read", "library_search", "library_read_note", "memory_search", "memory_read"]',
            is_builtin = 1
        WHERE name = 'pdf-chat';
        """,
        """
        -- Revert pdf-chat tools (best effort)
        UPDATE subagents
        SET tools = '["read", "kb_search", "kb_read_note", "memory_search", "memory_read"]'
        WHERE name = 'pdf-chat';
        """,
    )
]
