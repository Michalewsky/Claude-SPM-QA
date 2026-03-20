from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class Plan(BaseModel):
    plan_id: str
    plan_name: str
    role_type: str
    period_type: str
    currency: str
    period_start: str
    period_end: str
    credit_source: str
    proration_enabled: bool
    draws_enabled: bool
    cap_enabled: bool
    accelerator_enabled: bool
    bonus_component: bool
    notes: str = ""


class Rule(BaseModel):
    plan_id: str
    rule_id: str
    pipeline_stage: str
    rule_category: str
    rule_type: str
    condition: str
    parameters: dict[str, str] = Field(default_factory=dict)
    interaction_with: list[str] = Field(default_factory=list)
    stateful: bool = False
    state_key: str = ""
    notes: str = ""


class RuleInteraction(BaseModel):
    source_plan_id: str
    source_rule_id: str
    target_plan_id: str
    target_rule_id: str
    interaction_type: Literal["feeds_into", "overrides", "blocks", "precedes"]
    description: str


class EdgeCase(BaseModel):
    edge_case_id: str
    name: str
    category: str
    description: str
    applies_when: dict[str, str] = Field(default_factory=dict)
    expected_behavior: str
    known_failure_mode: str


class TestScenario(BaseModel):
    scenario_id: str
    plan_ids: list[str]
    rule_ids: list[str]
    name: str
    source: Literal["rule_derived", "edge_case"]
    category: Literal["happy_path", "boundary", "exception", "negative", "edge_case"]
    pipeline_stage: str
    description: str
    key_variables: dict[str, Union[float, int, str]] = Field(default_factory=dict)
    expected_outcome: str
    edge_case_id: Optional[str] = None


class RecordShape(BaseModel):
    table_name: str
    key_fields: dict[str, str]
    example_values: dict[str, str]
    cardinality: str


class DataRequirement(BaseModel):
    scenario_id: str
    plan_ids: list[str]
    tables_needed: list[str]
    record_shapes: list[RecordShape]
    temporal_constraints: list[str]
    dependencies: list[str]


class PreflightFinding(BaseModel):
    severity: Literal["error", "warning", "info"]
    area: str
    message: str
    suggestion: str
