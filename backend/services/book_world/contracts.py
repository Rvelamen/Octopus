"""Validated desktop payloads; callers never choose a filesystem or knowledge scope."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .revisions import RevisionPatch


class BookWorldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "prepare_source",
        "get_source",
        "list_segments",
        "resolve_evidence",
        "read_source",
        "start_discovery",
        "get_build",
        "list_characters",
        "cancel_build",
        "retry_build",
        "resume_build",
        "start_persona",
        "get_character",
        "get_revision_context",
        "create_revision",
        "save_extension",
        "preview_knowledge",
        "start_expression_set",
        "get_expression_set",
        "list_expression_materials",
        "cancel_expression_set",
        "resume_expression_set",
        "retry_expression_set",
        "get_auto_import",
        "cancel_auto_import",
        "retry_auto_import",
        "continue_auto_import",
        "restart_auto_import",
    ]
    item_id: int = Field(strict=True, gt=0)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)
    automatic_job_id: str | None = Field(default=None, min_length=1, max_length=100)
    source_version_id: str | None = None
    segment_id: str | None = None
    build_id: str | None = Field(default=None, max_length=100)
    character_id: str | None = Field(default=None, max_length=100)
    expected_attachment_sha256: str | None = None
    after_ordinal: int = Field(default=-1, strict=True, ge=-1)
    limit: int = Field(default=50, strict=True, ge=1, le=200)
    local_start: int = Field(default=0, strict=True, ge=0)
    local_end: int | None = Field(default=None, strict=True, gt=0)
    offset: int = Field(default=0, strict=True, ge=0)
    text_limit: int = Field(default=12000, strict=True, ge=1, le=20000)
    expected_revision: int | None = Field(default=None, strict=True, gt=0)
    revision_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    patches: list[RevisionPatch] | None = Field(default=None, min_length=1, max_length=12)
    extension_text: str | None = Field(default=None, min_length=1, max_length=4000)
    query: str = Field(default="", max_length=1000)
    retrospective: bool = Field(default=False, strict=True)
    knowledge_limit: int = Field(default=6, strict=True, ge=1, le=50)
    expression_set_id: str | None = Field(default=None, min_length=1, max_length=100)
    dialogue_action: Literal[
        "answer",
        "ask",
        "challenge",
        "comfort",
        "avoid",
        "greet",
        "disagree",
        "express_unknown",
        "other",
    ] = "other"

    @model_validator(mode="after")
    def required_source_identity(self) -> "BookWorldRequest":
        if self.action in ("cancel_auto_import", "retry_auto_import", "restart_auto_import", "continue_auto_import") and (
            self.workspace_id is None or self.automatic_job_id is None
        ):
            raise ValueError("Automatic controls require workspace and current pipeline identity")
        if (
            self.action in ("list_segments", "resolve_evidence", "read_source", "start_discovery")
            and not self.source_version_id
        ):
            raise ValueError("source_version_id is required")
        if self.action == "resolve_evidence" and not self.segment_id:
            raise ValueError("segment_id is required")
        if (
            self.action
            in (
                "list_characters",
                "cancel_build",
                "retry_build",
                "resume_build",
                "start_persona",
                "get_character",
                "get_revision_context",
                "create_revision",
                "save_extension",
                "preview_knowledge",
                "start_expression_set",
                "get_expression_set",
                "list_expression_materials",
                "cancel_expression_set",
                "resume_expression_set",
                "retry_expression_set",
            )
            and not self.build_id
        ):
            raise ValueError("build_id is required")
        if (
            self.action
            in (
                "get_character",
                "save_extension",
                "preview_knowledge",
                "start_expression_set",
                "get_expression_set",
                "list_expression_materials",
                "cancel_expression_set",
                "resume_expression_set",
                "retry_expression_set",
            )
            and not self.character_id
        ):
            raise ValueError("character_id is required")
        if self.action == "create_revision" and (
            self.expected_revision is None or not self.revision_request_id or not self.patches
        ):
            raise ValueError("Revision, request identity and patches are required")
        if self.action == "save_extension" and not self.extension_text:
            raise ValueError("extension_text is required")
        if (
            self.action
            in (
                "list_expression_materials",
                "cancel_expression_set",
                "resume_expression_set",
                "retry_expression_set",
            )
            and not self.expression_set_id
        ):
            raise ValueError("expression_set_id is required")
        return self
