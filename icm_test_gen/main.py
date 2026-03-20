from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict

import pandas as pd

from config import (
    DATA_REQ_MODEL,
    DATA_REQ_PROMPT_PATH,
    DATA_REQUIREMENTS_CSV,
    EDGE_CASES_CSV,
    PLANS_CSV,
    PREFLIGHT_MODEL,
    PREFLIGHT_PROMPT_PATH,
    PREFLIGHT_REPORT,
    RULE_INTERACTIONS_CSV,
    RULES_CSV,
    SCENARIO_MODEL,
    SCENARIO_PROMPT_PATH,
    SCENARIOS_CSV,
)
from src.data_req_gen import DataRequirementError, generate_data_requirement
from src.edge_case_filter import filter_edge_cases
from src.exporter import export_data_requirements, export_scenarios
from src.loader import InputLoadError, load_inputs
from src.models import PreflightFinding, TestScenario
from src.preflight import PreflightLLMError, run_preflight_consistency, write_preflight_report
from src.scenario_gen import ScenarioGenerationError, generate_cross_plan_scenarios, generate_single_plan_scenarios


PLANS_REQUIRED_COLUMNS = {
    "plan_id", "plan_name", "role_type", "period_type", "currency", "period_start", "period_end", "credit_source",
    "proration_enabled", "draws_enabled", "cap_enabled", "accelerator_enabled", "bonus_component", "notes"
}
RULES_REQUIRED_COLUMNS = {
    "plan_id", "rule_id", "pipeline_stage", "rule_category", "rule_type", "condition", "parameters", "interaction_with", "stateful", "state_key", "notes"
}
INTERACTIONS_REQUIRED_COLUMNS = {
    "source_plan_id", "source_rule_id", "target_plan_id", "target_rule_id", "interaction_type", "description"
}
EDGE_REQUIRED_COLUMNS = {
    "edge_case_id", "name", "category", "description", "applies_when", "expected_behavior", "known_failure_mode"
}


def prompt_yes_no(prompt: str, auto_answer: bool | None = None) -> bool:
    """Return True for yes (y), False for no (n)."""
    if auto_answer is not None:
        choice = "y" if auto_answer else "n"
        print(f"{prompt} (y/n): {choice} [auto]")
        return auto_answer
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Invalid choice. Please enter y or n.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ICM Test Case Generator")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--yes", action="store_true", help="Auto-answer yes to all approval prompts.")
    mode_group.add_argument("--no", action="store_true", help="Auto-answer no to all approval prompts.")
    return parser.parse_args()


def validate_required_columns() -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    files = [
        (PLANS_CSV, PLANS_REQUIRED_COLUMNS),
        (RULES_CSV, RULES_REQUIRED_COLUMNS),
        (RULE_INTERACTIONS_CSV, INTERACTIONS_REQUIRED_COLUMNS),
        (EDGE_CASES_CSV, EDGE_REQUIRED_COLUMNS),
    ]
    for file_path, required in files:
        df = pd.read_csv(file_path)
        missing = required - set(df.columns)
        for col in sorted(missing):
            findings.append(
                PreflightFinding(
                    severity="error",
                    area=file_path.name,
                    message=f"Missing required column '{col}'.",
                    suggestion="Add missing column and retry.",
                )
            )
    return findings


def assign_unique_scenario_ids(scenarios: list[TestScenario]) -> None:
    seen: set[str] = set()
    global_index = 1
    for scenario in scenarios:
        primary_plan = scenario.plan_ids[0] if scenario.plan_ids else "GLOBAL"
        candidate = f"{primary_plan}_SC{global_index:04d}"
        while candidate in seen:
            global_index += 1
            candidate = f"{primary_plan}_SC{global_index:04d}"
        scenario.scenario_id = candidate
        seen.add(candidate)
        global_index += 1


def main(auto_answer: bool | None = None) -> int:
    print("Loading input files...")
    try:
        loaded = load_inputs(PLANS_CSV, RULES_CSV, RULE_INTERACTIONS_CSV, EDGE_CASES_CSV)
    except InputLoadError as exc:
        print(f"Input load failed: {exc}")
        return 1

    print(
        f"Loaded {len(loaded.plans)} plans, {len(loaded.rules)} rules, "
        f"{len(loaded.interactions)} interactions, {len(loaded.edge_cases)} edge cases"
    )

    raw_plans = pd.read_csv(PLANS_CSV).fillna("").to_dict(orient="records")
    raw_rules = pd.read_csv(RULES_CSV).fillna("").to_dict(orient="records")

    print("Running pre-flight consistency check...")
    required_col_findings = validate_required_columns()
    try:
        preflight_findings = required_col_findings + run_preflight_consistency(
            loaded.plans,
            loaded.rules,
            loaded.interactions,
            loaded.edge_cases,
            PREFLIGHT_PROMPT_PATH,
            PREFLIGHT_MODEL,
            raw_plans,
            raw_rules,
        )
    except PreflightLLMError as exc:
        print(str(exc))
        if not prompt_yes_no("Pre-flight LLM failed. Continue with deterministic checks only?", auto_answer):
            return 1
        preflight_findings = required_col_findings

    write_preflight_report(preflight_findings, PREFLIGHT_REPORT)
    errors = [f for f in preflight_findings if f.severity == "error"]
    warnings = [f for f in preflight_findings if f.severity == "warning"]
    infos = [f for f in preflight_findings if f.severity == "info"]
    print(f"Pre-flight summary: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")
    if errors:
        print("ERROR findings detected. Please review outputs/preflight_report.txt")

    if not prompt_yes_no("Proceed", auto_answer):
        print("Exiting cleanly per user request.")
        return 0

    rules_by_plan = defaultdict(list)
    for rule in loaded.rules:
        rules_by_plan[rule.plan_id].append(rule)
    plan_by_id = {p.plan_id: p for p in loaded.plans}

    all_scenarios: list[TestScenario] = []

    for plan in loaded.plans:
        print(f"Generating scenarios for plan {plan.plan_id}...")
        try:
            generated = generate_single_plan_scenarios(plan, rules_by_plan[plan.plan_id], SCENARIO_PROMPT_PATH, SCENARIO_MODEL)
            all_scenarios.extend(generated)
        except ScenarioGenerationError as exc:
            print(f"{exc} LLM may have returned a refusal/partial/invalid response.")
            if not prompt_yes_no("Scenario generation failed for this plan. Skip and continue?", auto_answer):
                return 1

    for interaction in loaded.interactions:
        if interaction.source_plan_id == interaction.target_plan_id:
            continue
        source_plan = plan_by_id.get(interaction.source_plan_id)
        target_plan = plan_by_id.get(interaction.target_plan_id)
        if not source_plan or not target_plan:
            continue
        print(f"Generating scenarios for plan pair {interaction.source_plan_id}->{interaction.target_plan_id}...")
        try:
            generated = generate_cross_plan_scenarios(
                source_plan,
                rules_by_plan[source_plan.plan_id],
                target_plan,
                rules_by_plan[target_plan.plan_id],
                interaction,
                SCENARIO_PROMPT_PATH,
                SCENARIO_MODEL,
            )
            all_scenarios.extend(generated)
        except ScenarioGenerationError as exc:
            print(f"{exc} LLM may have returned a refusal/partial/invalid response.")
            if not prompt_yes_no("Cross-plan scenario generation failed. Skip and continue?", auto_answer):
                return 1

    edge_scenarios: list[TestScenario] = []
    for plan in loaded.plans:
        print(f"Filtering edge cases for plan {plan.plan_id}...")
        edge_scenarios.extend(filter_edge_cases(plan, loaded.edge_cases))

    print("Merging scenarios...")
    all_scenarios.extend(edge_scenarios)
    assign_unique_scenario_ids(all_scenarios)
    rule_count = len([s for s in all_scenarios if s.source == "rule_derived"])
    edge_count = len([s for s in all_scenarios if s.source == "edge_case"])
    print(f"{rule_count} rule-derived, {edge_count} edge case scenarios ready")

    requirements = []
    total = len(all_scenarios)
    for i, scenario in enumerate(all_scenarios, start=1):
        print(f"Generating data requirements ({i}/{total})...")
        try:
            req = generate_data_requirement(scenario, loaded.plans, loaded.rules, DATA_REQ_PROMPT_PATH, DATA_REQ_MODEL)
            requirements.append(req)
        except DataRequirementError as exc:
            print(f"{exc} LLM may have returned a refusal/partial/invalid response.")
            if not prompt_yes_no("Data requirement generation failed for this scenario. Skip and continue?", auto_answer):
                return 1

    print("Writing output files...")
    export_scenarios(all_scenarios, SCENARIOS_CSV)
    export_data_requirements(requirements, DATA_REQUIREMENTS_CSV)

    source_counts = Counter(s.source for s in all_scenarios)
    category_counts = Counter(s.category for s in all_scenarios)
    print("Final summary:")
    print(f"By source: {dict(source_counts)}")
    print(f"By category: {dict(category_counts)}")
    print(f"Pre-flight report: {PREFLIGHT_REPORT}")
    print(f"Scenario output: {SCENARIOS_CSV}")
    print(f"Data requirements output: {DATA_REQUIREMENTS_CSV}")
    return 0


if __name__ == "__main__":
    args = parse_args()
    auto_answer = True if args.yes else False if args.no else None
    sys.exit(main(auto_answer=auto_answer))
