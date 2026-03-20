from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "inputs"
OUTPUT_DIR = BASE_DIR / "outputs"
PROMPT_DIR = BASE_DIR / "prompts"

PLANS_CSV = INPUT_DIR / "plans.csv"
RULES_CSV = INPUT_DIR / "rules.csv"
RULE_INTERACTIONS_CSV = INPUT_DIR / "rule_interactions.csv"
EDGE_CASES_CSV = INPUT_DIR / "edge_cases.csv"

SCENARIOS_CSV = OUTPUT_DIR / "scenarios.csv"
DATA_REQUIREMENTS_CSV = OUTPUT_DIR / "data_requirements.csv"
PREFLIGHT_REPORT = OUTPUT_DIR / "preflight_report.txt"

SCENARIO_PROMPT_PATH = PROMPT_DIR / "scenario_prompt.txt"
DATA_REQ_PROMPT_PATH = PROMPT_DIR / "data_req_prompt.txt"
PREFLIGHT_PROMPT_PATH = PROMPT_DIR / "preflight_prompt.txt"

SCENARIO_MODEL = "gpt-4o"
DATA_REQ_MODEL = "gpt-4o-mini"
PREFLIGHT_MODEL = "gpt-4o"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
