"""Validated desktop payloads; callers never choose a filesystem or knowledge scope."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookWorldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["prepare_source", "get_source", "list_segments", "resolve_evidence"]
    item_id: int = Field(strict=True, gt=0)
    source_version_id: str | None = None
    segment_id: str | None = None
    expected_attachment_sha256: str | None = None
    after_ordinal: int = Field(default=-1, strict=True, ge=-1)
    limit: int = Field(default=50, strict=True, ge=1, le=200)
    local_start: int = Field(default=0, strict=True, ge=0)
    local_end: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def required_source_identity(self) -> "BookWorldRequest":
        if self.action in ("list_segments", "resolve_evidence") and not self.source_version_id:
            raise ValueError("source_version_id is required")
        if self.action == "resolve_evidence" and not self.segment_id:
            raise ValueError("segment_id is required")
        return self
