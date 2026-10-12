"""Validated desktop payloads; callers never choose a filesystem or knowledge scope."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    ]
    item_id: int = Field(strict=True, gt=0)
    source_version_id: str | None = None
    segment_id: str | None = None
    build_id: str | None = Field(default=None, max_length=100)
    expected_attachment_sha256: str | None = None
    after_ordinal: int = Field(default=-1, strict=True, ge=-1)
    limit: int = Field(default=50, strict=True, ge=1, le=200)
    local_start: int = Field(default=0, strict=True, ge=0)
    local_end: int | None = Field(default=None, strict=True, gt=0)
    offset: int = Field(default=0, strict=True, ge=0)
    text_limit: int = Field(default=12000, strict=True, ge=1, le=20000)

    @model_validator(mode="after")
    def required_source_identity(self) -> "BookWorldRequest":
        if (
            self.action in ("list_segments", "resolve_evidence", "read_source", "start_discovery")
            and not self.source_version_id
        ):
            raise ValueError("source_version_id is required")
        if self.action == "resolve_evidence" and not self.segment_id:
            raise ValueError("segment_id is required")
        if (
            self.action in ("list_characters", "cancel_build", "retry_build", "resume_build")
            and not self.build_id
        ):
            raise ValueError("build_id is required")
        return self
