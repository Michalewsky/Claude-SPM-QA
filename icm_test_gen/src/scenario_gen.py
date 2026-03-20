from __future__ import annotations

import json
from pathlib import Path

import instructor
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import Plan, Rule, RuleInteraction, TestScenario


class ScenarioGenerationError(Exception):
    """Raised when scenario generation fails after retries."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _generate(client: instructor.Instructor, model: str, prompt: str, payload: dict) -> list[TestScenario]:
    return client.chat.completions.create(
        model=model,
        response_model=list[TestScenario],
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )


def generate_single_plan_scenarios(plan: Plan, rules: list[Rule], prompt_path: Path, model: str) -> list[TestScenario]:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    payload = {"plan": plan.model_dump(), "rules": [r.model_dump() for r in rules]}
    try:
        client = instructor.from_openai(OpenAI())
        return _generate(client, model, prompt_text, payload)
    except Exception as exc:
        raise ScenarioGenerationError(
            f"Failed to generate scenarios for plan {plan.plan_id} after 3 attempts."
        ) from exc


def generate_cross_plan_scenarios(
    source_plan: Plan,
    source_rules: list[Rule],
    target_plan: Plan,
    target_rules: list[Rule],
    interaction: RuleInteraction,
    prompt_path: Path,
    model: str,
) -> list[TestScenario]:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    payload = {
        "source_plan": source_plan.model_dump(),
        "source_rules": [r.model_dump() for r in source_rules],
        "target_plan": target_plan.model_dump(),
        "target_rules": [r.model_dump() for r in target_rules],
        "interaction": interaction.model_dump(),
    }
    try:
        client = instructor.from_openai(OpenAI())
        return _generate(client, model, prompt_text, payload)
    except Exception as exc:
        raise ScenarioGenerationError(
            "Failed to generate cross-plan scenarios "
            f"for interaction {interaction.source_plan_id}->{interaction.target_plan_id} after 3 attempts."
        ) from exc
