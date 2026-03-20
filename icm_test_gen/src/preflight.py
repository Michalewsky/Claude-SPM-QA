from __future__ import annotations

import json
from pathlib import Path

import instructor
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .loader import parse_bool
from .models import EdgeCase, Plan, PreflightFinding, Rule, RuleInteraction


class PreflightLLMError(Exception):
    """Raised when preflight consistency analysis cannot complete."""


class PreflightResponse(BaseModel):
    findings: list[PreflightFinding]


def run_deterministic_checks(
    plans: list[Plan],
    rules: list[Rule],
    interactions: list[RuleInteraction],
    raw_plans: list[dict],
    raw_rules: list[dict],
) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []

    plan_ids = [p.plan_id for p in plans]
    if len(plan_ids) != len(set(plan_ids)):
        findings.append(PreflightFinding(severity="error", area="plans", message="Duplicate plan_ids detected.", suggestion="Ensure each plan_id is unique."))

    rule_ids = [r.rule_id for r in rules]
    if len(rule_ids) != len(set(rule_ids)):
        findings.append(PreflightFinding(severity="error", area="rules", message="Duplicate rule_ids detected.", suggestion="Ensure each rule_id is unique."))

    bool_cols_plan = ["proration_enabled", "draws_enabled", "cap_enabled", "accelerator_enabled", "bonus_component"]
    for i, row in enumerate(raw_plans, start=2):
        for col in bool_cols_plan:
            try:
                parse_bool(row.get(col, ""))
            except Exception:
                findings.append(PreflightFinding(severity="error", area="plans", message=f"Invalid boolean in plans.csv row {i} column '{col}'.", suggestion="Use true/false values only."))

    for i, row in enumerate(raw_rules, start=2):
        try:
            parse_bool(row.get("stateful", ""))
        except Exception:
            findings.append(PreflightFinding(severity="error", area="rules", message=f"Invalid boolean in rules.csv row {i} column 'stateful'.", suggestion="Use true/false values only."))

    valid_rule_ids = {r.rule_id for r in rules}
    for interaction in interactions:
        if interaction.source_rule_id not in valid_rule_ids:
            findings.append(PreflightFinding(severity="error", area="rule_interactions", message=f"Missing source_rule_id: {interaction.source_rule_id}", suggestion="Fix or remove invalid source_rule_id reference."))
        if interaction.target_rule_id not in valid_rule_ids:
            findings.append(PreflightFinding(severity="error", area="rule_interactions", message=f"Missing target_rule_id: {interaction.target_rule_id}", suggestion="Fix or remove invalid target_rule_id reference."))

    return findings


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_preflight_llm(client: instructor.Instructor, model: str, prompt: str, payload: dict) -> PreflightResponse:
    return client.chat.completions.create(
        model=model,
        response_model=PreflightResponse,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )


def run_preflight_consistency(
    plans: list[Plan],
    rules: list[Rule],
    interactions: list[RuleInteraction],
    edge_cases: list[EdgeCase],
    prompt_path: Path,
    model: str,
    raw_plans: list[dict],
    raw_rules: list[dict],
) -> list[PreflightFinding]:
    deterministic = run_deterministic_checks(plans, rules, interactions, raw_plans, raw_rules)

    prompt_text = prompt_path.read_text(encoding="utf-8")
    payload = {
        "plans": [p.model_dump() for p in plans],
        "rules": [r.model_dump() for r in rules],
        "interactions": [i.model_dump() for i in interactions],
        "edge_cases": [e.model_dump() for e in edge_cases],
    }

    try:
        client = instructor.from_openai(OpenAI())
        llm_resp = _call_preflight_llm(client, model, prompt_text, payload)
    except Exception as exc:
        raise PreflightLLMError(
            "Pre-flight LLM consistency analysis failed after 3 attempts. "
            "Options: fix input and retry, continue with deterministic findings only, or abort."
        ) from exc

    return deterministic + llm_resp.findings


def write_preflight_report(findings: list[PreflightFinding], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ICM Test Case Generator - Preflight Report", "=" * 48, ""]
    if not findings:
        lines.append("No findings.")
    else:
        for item in findings:
            lines.append(f"[{item.severity.upper()}] {item.area}: {item.message}")
            lines.append(f"  Suggestion: {item.suggestion}")
            lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
