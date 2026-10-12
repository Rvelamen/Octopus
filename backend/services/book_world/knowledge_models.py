"""Actor-facing contracts exclude reader quotes, truth labels and other identities."""

from typing import Literal

from pydantic import Field

from .discovery_models import StrictModel

KNOWLEDGE_POLICY_VERSION = "canonical-perspective-v1"


class CanonicalScope(StrictModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    book_id: str = Field(min_length=1, max_length=100)
    source_version_id: str = Field(min_length=1, max_length=100)
    build_id: str = Field(min_length=1, max_length=100)
    character_id: str = Field(min_length=1, max_length=100)
    canonical_policy_version: str = Field(min_length=1, max_length=100)
    knowledge_policy_version: str = KNOWLEDGE_POLICY_VERSION

    @property
    def binding(self) -> tuple[str, str, str, str]:
        return self.book_id, self.source_version_id, self.build_id, self.character_id


class AllowedEvidence(StrictModel):
    claim_id: str
    evidence_id: str
    kind: Literal["fact", "episode", "belief", "trait", "relation", "emotion", "style"]
    proposition: str
    approved_excerpt: str
    segment_id: str
    local_start: int
    local_end: int
    temporal_state: Literal["current", "historical", "unspecified"]
    route: Literal["firsthand", "observed", "told", "common"]


class AllowlistedContext(StrictModel):
    scope: CanonicalScope
    query: str
    status: Literal["known", "unknown"]
    items: tuple[AllowedEvidence, ...]
    reason: Literal["matched", "no_relevant_evidence"]
    retrieval_strategy: Literal["fts", "allowlist_scan", "catalog"]


class ActorBaselineContext(StrictModel):
    scope: CanonicalScope
    slots: dict[str, AllowedEvidence]
