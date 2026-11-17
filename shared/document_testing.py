"""Bounded private document-preview transport; no public chat diagnostics."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from shared.models import InputModel, SourceAttachmentReference


class DocumentTestRequest(InputModel):
    message: str = Field(min_length=1, max_length=4000)
    scope: dict


class TestCitation(InputModel):
    label: str = Field(min_length=1, max_length=20)
    source_type: Literal["manual"] = "manual"
    document_id: UUID
    source_revision: UUID
    chunk_id: str | None = Field(default=None, max_length=200)
    element_id: str | None = Field(default=None, max_length=100)
    section_path: list[str] = Field(default_factory=list, max_length=30)


class TestEvidence(InputModel):
    document_id: UUID
    source_revision: UUID
    chunk_id: str = Field(max_length=200)
    element_id: str | None = Field(default=None, max_length=100)
    kind: Literal["paragraph", "table", "image"]
    label: str | None = Field(default=None, max_length=20)
    section_path: list[str] = Field(default_factory=list, max_length=30)
    excerpt: str = Field(max_length=4000)
    eligible: bool
    cited: bool
    supplied: bool = False
    exclusion: str = Field(default="", max_length=300)


class InferenceUsage(InputModel):
    status: Literal['completed', 'failed', 'rejected']
    queue_ms: float = Field(ge=0, allow_inf_nan=False)
    inference_ms: float = Field(ge=0, allow_inf_nan=False)
    prompt_eval_count: int | None = Field(default=None, ge=0)
    eval_count: int | None = Field(default=None, ge=0)
    load_duration: int | None = Field(default=None, ge=0)
    prompt_eval_duration: int | None = Field(default=None, ge=0)
    eval_duration: int | None = Field(default=None, ge=0)
    total_duration: int | None = Field(default=None, ge=0)
    done_reason: str | None = Field(default=None, max_length=100)


class TestDiagnostics(InputModel):
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)
    reason: str = Field(default="", max_length=300)
    retrieved_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    evidence_truncated: bool = False
    fallback_used: bool = False
    answer_mode: str = Field(default='', max_length=100)
    fallback_reason: str = Field(default='', max_length=100)
    failure_kind: str = Field(default='', max_length=100)
    retrieval_degraded: bool = False
    embedding_fallback: bool = False
    omitted_source_labels: list[str] = Field(default_factory=list, max_length=100)
    timings: dict[str, float] = Field(default_factory=dict, max_length=20)
    inference_calls: list[InferenceUsage] = Field(default_factory=list, max_length=10)


class DocumentTestReply(InputModel):
    answer: str = Field(min_length=1, max_length=50000)
    response_type: str = Field(min_length=1, max_length=100)
    route: str = Field(max_length=100)
    sources: list[TestCitation] = Field(default_factory=list, max_length=30)
    attachments: list[SourceAttachmentReference] = Field(default_factory=list, max_length=5)
    evidence: list[TestEvidence] = Field(default_factory=list, max_length=20)
    diagnostics: TestDiagnostics
