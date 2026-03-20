from __future__ import annotations

import json
from pathlib import Path

import instructor
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import DataRequirement, Plan, Rule, TestScenario


class DataRequirementError(Exception):
    """Raised when data requirement generation fails after retries."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _generate(client: instructor.Instructor, model: str, prompt: str, payload: dict) -> DataRequirement:
    return client.chat.completions.create(
        model=model,
        response_model=DataRequirement,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )


def generate_data_requirement(
    scenario: TestScenario,
    plans: list[Plan],
    rules: list[Rule],
    prompt_path: Path,
    model: str,
) -> DataRequirement:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    scoped_plans = [p.model_dump() for p in plans if p.plan_id in scenario.plan_ids]
    scoped_rules = [r.model_dump() for r in rules if r.plan_id in scenario.plan_ids or r.rule_id in scenario.rule_ids]
    payload = {
        "scenario": scenario.model_dump(),
        "plans": scoped_plans,
        "rules": scoped_rules,
    }
    try:
        client = instructor.from_openai(OpenAI())
        return _generate(client, model, prompt_text, payload)
    except Exception as exc:
        raise DataRequirementError(
            f"Failed to generate data requirements for scenario {scenario.scenario_id} after 3 attempts."
        ) from exc
