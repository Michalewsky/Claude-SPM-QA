from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .models import EdgeCase, Plan, Rule, RuleInteraction


class InputLoadError(Exception):
    """Raised when input files cannot be parsed."""


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise InputLoadError(f"Invalid boolean value: {value}")


def parse_kv_pipe(value: object) -> dict[str, str]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return {}
    parsed: dict[str, str] = {}
    for item in text.split("|"):
        if "=" not in item:
            raise InputLoadError(f"Invalid key=value token: {item}")
        key, raw_value = item.split("=", 1)
        parsed[key.strip()] = raw_value.strip()
    return parsed


def parse_csv_list(value: object) -> list[str]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


@dataclass
class LoadedInputs:
    plans: list[Plan]
    rules: list[Rule]
    interactions: list[RuleInteraction]
    edge_cases: list[EdgeCase]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise InputLoadError(f"Missing required file: {path}")
    return pd.read_csv(path).fillna("")


def load_inputs(plans_csv: Path, rules_csv: Path, interactions_csv: Path, edge_cases_csv: Path) -> LoadedInputs:
    plans_df = _read_csv(plans_csv)
    rules_df = _read_csv(rules_csv)
    interactions_df = _read_csv(interactions_csv)
    edge_df = _read_csv(edge_cases_csv)

    plans = [
        Plan(
            **row,
            proration_enabled=parse_bool(row["proration_enabled"]),
            draws_enabled=parse_bool(row["draws_enabled"]),
            cap_enabled=parse_bool(row["cap_enabled"]),
            accelerator_enabled=parse_bool(row["accelerator_enabled"]),
            bonus_component=parse_bool(row["bonus_component"]),
        )
        for row in plans_df.to_dict(orient="records")
    ]

    rules = [
        Rule(
            **row,
            parameters=parse_kv_pipe(row["parameters"]),
            interaction_with=parse_csv_list(row["interaction_with"]),
            stateful=parse_bool(row["stateful"]),
        )
        for row in rules_df.to_dict(orient="records")
    ]

    interactions = [RuleInteraction(**row) for row in interactions_df.to_dict(orient="records")]
    edge_cases = [
        EdgeCase(**row, applies_when=parse_kv_pipe(row["applies_when"]))
        for row in edge_df.to_dict(orient="records")
    ]

    return LoadedInputs(plans=plans, rules=rules, interactions=interactions, edge_cases=edge_cases)
