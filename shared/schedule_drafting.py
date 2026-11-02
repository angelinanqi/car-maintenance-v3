"""Structured schedule proposals exchanged with the private generation service."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from shared.models import InputModel

Index = Annotated[int, Field(strict=True, ge=0)]
Positive = Annotated[int, Field(strict=True, gt=0, le=10000000)]
Action = Literal["inspect", "replace", "service"]


class DraftRule(InputModel):
    type: Literal["recurring", "milestone", "informational"]
    distanceKm: Positive | None = None
    months: Positive | None = None
    distanceMilestones: list[Positive] = Field(default_factory=list, max_length=200)
    monthMilestones: list[Positive] = Field(default_factory=list, max_length=200)
    conditions: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def valid_structure(self):
        for values in (self.distanceMilestones, self.monthMilestones):
            if values != sorted(set(values)):
                raise ValueError("Milestones must be unique and in ascending order.")
        if self.type != "recurring" and (self.distanceKm or self.months):
            raise ValueError("Only recurring rules may contain intervals.")
        if self.type != "milestone" and (self.distanceMilestones or self.monthMilestones):
            raise ValueError("Only milestone rules may contain milestones.")
        return self


class CellReference(InputModel):
    row: Index
    column: Index


class SourceCell(CellReference):
    text: str = Field(max_length=12000)
    header: bool = False
    rowspan: int = Field(default=1, ge=1, le=1000)
    colspan: int = Field(default=1, ge=1, le=1000)


class ScheduleDraftRequest(InputModel):
    document_id: UUID
    source_revision: UUID
    document_name: str = Field(max_length=500)
    document_type: str = Field(max_length=100)
    vehicle: dict[str, str]
    table_id: str = Field(pattern=r"^table-\d{5,}$")
    title: str = Field(max_length=1000)
    cells: list[SourceCell] = Field(min_length=1, max_length=4000)
    task_rows: list[Index] = Field(min_length=1, max_length=200)
    item_columns: list[Index] = Field(min_length=1, max_length=100)
    context: list[str] = Field(default_factory=list, max_length=100)
    notes: list[str] = Field(default_factory=list, max_length=100)
    table_uncertainty: list[str] = Field(default_factory=list, max_length=20)


class DraftRow(InputModel):
    name: str = Field(min_length=1, max_length=200)
    action: Action | None = None
    source_rows: list[Index] = Field(min_length=1, max_length=20)
    rule: DraftRule | None = None
    evidence_cells: list[CellReference] = Field(min_length=1, max_length=100)
    note_indices: list[Index] = Field(default_factory=list, max_length=100)
    context_indices: list[Index] = Field(default_factory=list, max_length=100)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)
    manual_entry_required: bool = False


class DraftResult(InputModel):
    rows: list[DraftRow] = Field(max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ScheduleDraftResponse(DraftResult):
    provider: str | None = None
    model: str | None = None


def rule_issues(rule):
    if rule is None:
        return ["Enter a rule supported by the original manual."]
    if rule.type == "recurring" and not (rule.distanceKm or rule.months):
        return ["Enter a distance or time interval."]
    if rule.type == "milestone" and not (rule.distanceMilestones or rule.monthMilestones):
        return ["Enter the service mileages or vehicle ages."]
    if rule.type == "informational" and not (rule.conditions or rule.notes):
        return ["Describe the condition or guidance in the manual."]
    return []
