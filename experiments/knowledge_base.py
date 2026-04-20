from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
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
    lab_profile: Path
    risk_rules: Path
    disease_drug_map: Path
    example_cases: Path


class KnowledgeBaseIndex:
    def __init__(self, paths: ExperimentPaths) -> None:
        self.paths = paths
        self.index_df = read_csv_flexible(paths.kb_index_file)

    def get_entry(self, specialty_name: str) -> KnowledgeBaseEntry:
        row = self.index_df[self.index_df["specialty_name"] == specialty_name]
        if row.empty:
            raise KeyError(f"未找到专科知识库索引: {specialty_name}")
        item = row.iloc[0]
        return KnowledgeBaseEntry(
            specialty_name=specialty_name,
            folder_name=str(item["folder_name"]),
            disease_catalog=Path(item["disease_catalog"]),
            drug_catalog=Path(item["drug_catalog"]),
            lab_profile=Path(item["lab_profile"]),
            risk_rules=Path(item["risk_rules"]),
            disease_drug_map=Path(item["disease_drug_map"]),
            example_cases=Path(item["example_cases"]),
        )


class SpecialtyKnowledgeLoader:
    def __init__(self, kb_index: KnowledgeBaseIndex) -> None:
        self.kb_index = kb_index

    def load(self, specialty_name: str) -> dict[str, Any]:
        entry = self.kb_index.get_entry(specialty_name)
        disease_catalog = read_csv_flexible(entry.disease_catalog)
        drug_catalog = read_csv_flexible(entry.drug_catalog)
        disease_drug_map = read_csv_flexible(entry.disease_drug_map)
        lab_profile = read_csv_flexible(entry.lab_profile)
        risk_rules = read_json_file(entry.risk_rules)
        example_cases = read_json_file(entry.example_cases)

        return {
            "entry": entry,
            "disease_catalog": disease_catalog,
            "drug_catalog": drug_catalog,
            "disease_drug_map": disease_drug_map,
            "lab_profile": lab_profile,
            "risk_rules": risk_rules,
            "example_cases": example_cases,
        }

    def build_prompt_payload(self, specialty_name: str) -> dict[str, Any]:
        kb = self.load(specialty_name)
        disease_catalog = kb["disease_catalog"]
        drug_catalog = kb["drug_catalog"]
        disease_drug_map = kb["disease_drug_map"]

        core_diseases = disease_catalog[disease_catalog["disease_role"] == "核心病种"].head(20)
        core_drugs = drug_catalog[drug_catalog["drug_role"] == "核心治疗药"].head(20)
        usable_map = disease_drug_map[disease_drug_map["mapping_quality"] == "可直接使用"].head(30)

        return {
            "specialty_name": specialty_name,
            "knowledge_base_dir": str(kb["entry"].disease_catalog.parent),
            "core_diseases": core_diseases.fillna("").to_dict(orient="records"),
            "core_drugs": core_drugs.fillna("").to_dict(orient="records"),
            "disease_drug_map": usable_map.fillna("").to_dict(orient="records"),
            "risk_rules": kb["risk_rules"],
            "example_cases": kb["example_cases"],
        }
