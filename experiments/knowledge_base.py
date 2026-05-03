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
    lab_profile: Path
    lab_profile_all: Path | None
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
        folder_name = str(item["folder_name"])
        return KnowledgeBaseEntry(
            specialty_name=specialty_name,
            folder_name=folder_name,
            disease_catalog=self._resolve_index_path(item["disease_catalog"], folder_name),
            drug_catalog=self._resolve_index_path(item["drug_catalog"], folder_name),
            lab_profile=self._resolve_index_path(item["lab_profile"], folder_name),
            lab_profile_all=(
                self._resolve_index_path(item["lab_profile_all"], folder_name)
                if "lab_profile_all" in item and pd.notna(item["lab_profile_all"])
                else None
            ),
            risk_rules=self._resolve_index_path(item["risk_rules"], folder_name),
            disease_drug_map=self._resolve_index_path(item["disease_drug_map"], folder_name),
            example_cases=self._resolve_index_path(item["example_cases"], folder_name),
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
        disease_drug_map = read_csv_flexible(entry.disease_drug_map)
        lab_profile = read_csv_flexible(entry.lab_profile)
        lab_profile_all = (
            read_csv_flexible(entry.lab_profile_all)
            if entry.lab_profile_all is not None and entry.lab_profile_all.exists()
            else pd.DataFrame()
        )
        risk_rules = read_json_file(entry.risk_rules)
        example_cases = read_json_file(entry.example_cases)

        return {
            "entry": entry,
            "disease_catalog": disease_catalog,
            "drug_catalog": drug_catalog,
            "disease_drug_map": disease_drug_map,
            "lab_profile": lab_profile,
            "lab_profile_all": lab_profile_all,
            "risk_rules": risk_rules,
            "example_cases": example_cases,
        }

    def build_prompt_payload(self, specialty_name: str) -> dict[str, Any]:
        kb = self.load(specialty_name)
        disease_catalog = kb["disease_catalog"]
        drug_catalog = kb["drug_catalog"]
        disease_drug_map = kb["disease_drug_map"]

        if "diagnosis_relevance" in disease_catalog.columns:
            primary_diseases = disease_catalog[
                disease_catalog["diagnosis_relevance"] == "primary_specialty_disease"
            ].head(20)
            related_conditions = disease_catalog[
                disease_catalog["diagnosis_relevance"].isin(["specialty_related_condition", "cross_specialty_comorbidity"])
            ].head(20)
        else:
            primary_diseases = disease_catalog[disease_catalog["disease_role"] == "核心病种"].head(20)
            related_conditions = disease_catalog[disease_catalog["disease_role"] == "背景共病"].head(20)

        if "treatment_role" in drug_catalog.columns:
            disease_directed_drugs = drug_catalog[
                drug_catalog["treatment_role"].isin(["disease_directed_therapy", "risk_modifying_therapy"])
            ].head(20)
            supportive_drugs = drug_catalog[
                drug_catalog["treatment_role"].isin(["supportive_or_symptomatic_therapy", "general_inpatient_medication"])
            ].head(20)
        else:
            disease_directed_drugs = drug_catalog[drug_catalog["drug_role"] == "核心治疗药"].head(20)
            supportive_drugs = drug_catalog[drug_catalog["drug_role"] != "核心治疗药"].head(20)

        if "mapping_quality" in disease_drug_map.columns:
            usable_map = disease_drug_map[
                disease_drug_map["mapping_quality"].isin(["可直接使用", "候选证据充分"])
            ].head(30)
        else:
            usable_map = disease_drug_map.head(30)

        lab_profile_all = kb["lab_profile_all"]
        top_labs = (
            lab_profile_all.sort_values(["coverage_pct", "case_count"], ascending=[False, False]).head(30)
            if not lab_profile_all.empty and {"coverage_pct", "case_count"}.issubset(lab_profile_all.columns)
            else pd.DataFrame()
        )

        return {
            "specialty_name": specialty_name,
            "knowledge_base_dir": str(kb["entry"].disease_catalog.parent),
            "diagnostic_knowledge": {
                "primary_specialty_diseases": primary_diseases.fillna("").to_dict(orient="records"),
                "related_conditions": related_conditions.fillna("").to_dict(orient="records"),
            },
            "treatment_knowledge": {
                "disease_directed_or_risk_modifying": disease_directed_drugs.fillna("").to_dict(orient="records"),
                "supportive_or_general": supportive_drugs.fillna("").to_dict(orient="records"),
            },
            "core_diseases": primary_diseases.fillna("").to_dict(orient="records"),
            "core_drugs": disease_directed_drugs.fillna("").to_dict(orient="records"),
            "lab_knowledge": {
                "key_risk_labs": kb["lab_profile"].fillna("").to_dict(orient="records"),
                "top_covered_labs": top_labs.fillna("").to_dict(orient="records"),
            },
            "disease_drug_map": usable_map.fillna("").to_dict(orient="records"),
            "risk_rules": kb["risk_rules"],
            "example_cases": kb["example_cases"],
        }
