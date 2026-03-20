from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Strip whitespace from keys and string values to avoid CSV drift issues."""
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        clean_key = str(key).strip()
        if isinstance(value, str):
            normalized[clean_key] = value.strip()
        else:
            normalized[clean_key] = value
    return normalized


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

    plans: list[Plan] = []
    for raw in plans_df.to_dict(orient="records"):
        row = _normalize_row(raw)
        row["proration_enabled"] = parse_bool(row.get("proration_enabled", ""))
        row["draws_enabled"] = parse_bool(row.get("draws_enabled", ""))
        row["cap_enabled"] = parse_bool(row.get("cap_enabled", ""))
        row["accelerator_enabled"] = parse_bool(row.get("accelerator_enabled", ""))
        row["bonus_component"] = parse_bool(row.get("bonus_component", ""))
        plans.append(Plan(**row))

    rules: list[Rule] = []
    for raw in rules_df.to_dict(orient="records"):
        row = _normalize_row(raw)
        row["parameters"] = parse_kv_pipe(row.get("parameters", ""))
        row["interaction_with"] = parse_csv_list(row.get("interaction_with", ""))
        row["stateful"] = parse_bool(row.get("stateful", ""))
        rules.append(Rule(**row))

    interactions = [RuleInteraction(**_normalize_row(row)) for row in interactions_df.to_dict(orient="records")]
    edge_cases = [
        EdgeCase(**{**_normalize_row(row), "applies_when": parse_kv_pipe(row.get("applies_when", ""))})
        for row in edge_df.to_dict(orient="records")
    ]

    return LoadedInputs(plans=plans, rules=rules, interactions=interactions, edge_cases=edge_cases)
