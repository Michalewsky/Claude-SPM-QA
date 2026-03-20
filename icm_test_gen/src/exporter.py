from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import DataRequirement, TestScenario


def export_scenarios(scenarios: list[TestScenario], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in scenarios:
        row = s.model_dump()
        row["plan_ids"] = json.dumps(row["plan_ids"])
        row["rule_ids"] = json.dumps(row["rule_ids"])
        row["key_variables"] = json.dumps(row["key_variables"])
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_path, index=False)


def export_data_requirements(requirements: list[DataRequirement], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in requirements:
        row = r.model_dump()
        row["plan_ids"] = json.dumps(row["plan_ids"])
        row["tables_needed"] = json.dumps(row["tables_needed"])
        row["record_shapes"] = json.dumps(row["record_shapes"])
        row["temporal_constraints"] = json.dumps(row["temporal_constraints"])
        row["dependencies"] = json.dumps(row["dependencies"])
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_path, index=False)
