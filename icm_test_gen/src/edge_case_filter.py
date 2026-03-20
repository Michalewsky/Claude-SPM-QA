from __future__ import annotations

from .models import EdgeCase, Plan, TestScenario


def _map_category_to_pipeline_stage(category: str) -> str:
    low = category.strip().lower()
    if low in {"timing", "quota"}:
        return "aggregation"
    if low in {"credit", "hierarchy"}:
        return "credit_attribution"
    if low in {"draw", "adjustment"}:
        return "post_calc"
    if low == "bonus":
        return "bonus"
    return "post_calc"


def filter_edge_cases(plan: Plan, edge_cases: list[EdgeCase]) -> list[TestScenario]:
    scenarios: list[TestScenario] = []

    for edge in edge_cases:
        match = True
        for key, expected in edge.applies_when.items():
            plan_value = getattr(plan, key, None)
            if isinstance(plan_value, bool):
                normalized = str(plan_value).lower()
            else:
                normalized = str(plan_value)
            if normalized != expected:
                match = False
                break

        if not match:
            continue

        scenarios.append(
            TestScenario(
                scenario_id=f"{plan.plan_id}_EC_{edge.edge_case_id}",
                plan_ids=[plan.plan_id],
                rule_ids=[],
                name=edge.name,
                source="edge_case",
                category="edge_case",
                pipeline_stage=_map_category_to_pipeline_stage(edge.category),
                description=edge.description,
                key_variables={"known_failure_mode": edge.known_failure_mode},
                expected_outcome=edge.expected_behavior,
                edge_case_id=edge.edge_case_id,
            )
        )

    return scenarios
