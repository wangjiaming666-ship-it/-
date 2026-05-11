from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import pandas as pd

from experiments.config import ExperimentPaths


def read_csv_flexible(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "gb18030"]
    last_error = None
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path} ({last_error})") from last_error


def read_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


@dataclass
class KnowledgeBaseEntry:
    specialty_name: str
    folder_name: str
    disease_catalog: Path
    drug_catalog: Path
    risk_rules: Path


class KnowledgeBaseIndex:
    def __init__(self, paths: ExperimentPaths) -> None:
        self.paths = paths
        self.index_df = read_csv_flexible(paths.kb_index_file)

    def get_entry(self, specialty_name: str) -> KnowledgeBaseEntry:
        row = self.index_df[self.index_df["specialty_name"] == specialty_name]
        if row.empty:
            raise KeyError(f"未找到专科知识库索引: {specialty_name}")
        item = row.iloc[0]
        folder_name = str(item["folder_name"])
        return KnowledgeBaseEntry(
            specialty_name=specialty_name,
            folder_name=folder_name,
            disease_catalog=self._resolve_index_path(item["disease_catalog"], folder_name),
            drug_catalog=self._resolve_index_path(item["drug_catalog"], folder_name),
            risk_rules=self._resolve_index_path(item["risk_rules"], folder_name),
        )

    def _resolve_index_path(self, raw_path: str, folder_name: str) -> Path:
        candidate = Path(str(raw_path))
        if candidate.exists():
            return candidate

        if not candidate.is_absolute():
            repo_candidate = self.paths.root_dir / candidate
            if repo_candidate.exists():
                return repo_candidate

        filename = PureWindowsPath(str(raw_path)).name
        return self.paths.knowledge_base_dir / folder_name / filename


class SpecialtyKnowledgeLoader:
    def __init__(self, kb_index: KnowledgeBaseIndex) -> None:
        self.kb_index = kb_index

    def load(self, specialty_name: str) -> dict[str, Any]:
        entry = self.kb_index.get_entry(specialty_name)
        disease_catalog = read_csv_flexible(entry.disease_catalog)
        drug_catalog = read_csv_flexible(entry.drug_catalog)
        risk_rules = read_json_file(entry.risk_rules)

        return {
            "entry": entry,
            "disease_catalog": disease_catalog,
            "drug_catalog": drug_catalog,
            "risk_rules": risk_rules,
        }

    def build_prompt_payload(self, specialty_name: str) -> dict[str, Any]:
        kb = self.load(specialty_name)
        disease_catalog = kb["disease_catalog"]
        drug_catalog = kb["drug_catalog"]

        disease_columns = [
            "disease_name",
            "aliases",
            "diagnostic_basis",
            "key_symptoms",
            "key_labs_or_tests",
            "differential_diagnosis",
            "reference_source",
            "reference_url",
            "agent_use",
        ]
        drug_columns = [
            "standard_drug_name",
            "aliases",
            "drug_class",
            "disease_context",
            "treatment_role",
            "order_category",
            "mechanism_or_function",
            "major_cautions",
            "reference_source",
            "reference_url",
            "agent_use",
        ]
        disease_payload = disease_catalog[
            [column for column in disease_columns if column in disease_catalog.columns]
        ].head(30)
        disease_directed_drugs = drug_catalog[
            drug_catalog["treatment_role"].isin(["disease_directed_therapy", "risk_modifying_therapy"])
        ][[column for column in drug_columns if column in drug_catalog.columns]].head(30)
        supportive_drugs = drug_catalog[
            drug_catalog["treatment_role"].isin(
                ["supportive_or_symptomatic_therapy", "general_inpatient_medication"]
            )
        ][[column for column in drug_columns if column in drug_catalog.columns]].head(20)

        return {
            "specialty_name": specialty_name,
            "knowledge_base_dir": str(kb["entry"].disease_catalog.parent),
            "diagnostic_knowledge": disease_payload.fillna("").to_dict(orient="records"),
            "drug_function_knowledge": {
                "disease_directed_or_risk_modifying": disease_directed_drugs.fillna("").to_dict(
                    orient="records"
                ),
                "supportive_or_general": supportive_drugs.fillna("").to_dict(orient="records"),
            },
            "risk_rules": kb["risk_rules"],
        }
