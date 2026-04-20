from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class ExperimentPaths:
    root_dir: Path = ROOT_DIR
    knowledge_base_dir: Path = field(default_factory=lambda: ROOT_DIR / "knowledge_base")
    agent_specs_dir: Path = field(default_factory=lambda: ROOT_DIR / "agent_specs")
    outputs_dir: Path = field(default_factory=lambda: ROOT_DIR / "experiments" / "outputs")

    multi_specialty_cases_file: Path = field(
        default_factory=lambda: ROOT_DIR / "multi_specialty_cases_v2.csv"
    )
    admissions_file: Path = field(default_factory=lambda: ROOT_DIR / "cohort_admissions.csv")
    diagnoses_file: Path = field(
        default_factory=lambda: ROOT_DIR / "cleaned_diagnosis_specialty_detail_6.csv"
    )
    labs_file: Path = field(default_factory=lambda: ROOT_DIR / "cohort_first24h_labs.csv")
    case_summary_file: Path = field(default_factory=lambda: ROOT_DIR / "case_summary.csv")
    kb_index_file: Path = field(default_factory=lambda: ROOT_DIR / "knowledge_base" / "kb_index.csv")
    input_template_file: Path = field(
        default_factory=lambda: ROOT_DIR / "agent_specs" / "specialty_agent_input_template.json"
    )
    output_template_file: Path = field(
        default_factory=lambda: ROOT_DIR / "agent_specs" / "specialty_agent_output_template.json"
    )


@dataclass
class LLMSettings:
    api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )
    )
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    timeout_seconds: int = field(default_factory=lambda: int(os.getenv("OPENAI_TIMEOUT", "120")))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


ACTIVE_SPECIALTIES = [
    "心血管",
    "神经",
    "呼吸",
    "肾内/泌尿",
    "内分泌/代谢",
    "消化",
]
