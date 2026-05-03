from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from experiments.config import ACTIVE_SPECIALTIES, ExperimentPaths
from experiments.knowledge_base import read_csv_flexible
from experiments.schemas import CaseRecord, PatientInfo


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        df = read_csv_flexible(path)
        return None if df.empty else df
    except Exception:  # noqa: BLE001
        return None


class CaseBuilder:
    def __init__(self, paths: ExperimentPaths) -> None:
        self.paths = paths
        self.multi_cases = read_csv_flexible(paths.multi_specialty_cases_file)
        self.admissions = safe_read_csv(paths.admissions_file)
        self.diagnoses = safe_read_csv(paths.diagnoses_file)
        self.labs = safe_read_csv(paths.labs_file)
        self.vitals = safe_read_csv(paths.vitals_file)
        self.past_history = safe_read_csv(paths.past_history_file)
        self.comorbidity_summary = safe_read_csv(paths.comorbidity_summary_file)
        self.procedure_features = safe_read_csv(paths.procedure_features_file)
        self.microbiology_features = safe_read_csv(paths.microbiology_features_file)
        self.icu_features = safe_read_csv(paths.icu_features_file)
        self.outcome_features = safe_read_csv(paths.outcome_features_file)
        self.case_summary = safe_read_csv(paths.case_summary_file)

        for frame in [
            self.multi_cases,
            self.admissions,
            self.diagnoses,
            self.labs,
            self.vitals,
            self.past_history,
            self.comorbidity_summary,
            self.procedure_features,
            self.microbiology_features,
            self.icu_features,
            self.outcome_features,
            self.case_summary,
        ]:
            if frame is not None:
                for col in ["subject_id", "hadm_id"]:
                    if col in frame.columns:
                        frame[col] = frame[col].astype(str)

    def list_case_ids(self, limit: int = 20) -> list[str]:
        return self.multi_cases["hadm_id"].astype(str).head(limit).tolist()

    def build_case_by_index(self, index: int) -> CaseRecord:
        row = self.multi_cases.iloc[index]
        return self.build_case_by_hadm_id(str(row["hadm_id"]))

    def build_case_by_hadm_id(self, hadm_id: str) -> CaseRecord:
        case_row = self.multi_cases[self.multi_cases["hadm_id"].astype(str) == str(hadm_id)]
        if case_row.empty:
            raise KeyError(f"未找到 hadm_id={hadm_id} 对应的多专科病例")
        case_row = case_row.iloc[0]

        subject_id = str(case_row["subject_id"])
        active_specialties = self._parse_specialty_list(str(case_row["specialty_list"]))
        patient_info = self._build_patient_info(subject_id, hadm_id)
        diagnoses = self._load_diagnoses(subject_id, hadm_id)
        specialty_map = self._build_specialty_diagnosis_map(diagnoses, active_specialties)
        primary_diagnosis = self._infer_primary_diagnosis(diagnoses)
        comorbidities = self._infer_comorbidities(diagnoses, primary_diagnosis)
        labs = self._load_labs(subject_id, hadm_id)
        past_history = self._load_feature_row(self.past_history, subject_id, hadm_id)
        key_vitals = self._load_vitals(subject_id, hadm_id)
        procedure_features = self._load_feature_row(self.procedure_features, subject_id, hadm_id)
        microbiology_features = self._load_feature_row(self.microbiology_features, subject_id, hadm_id)
        icu_features = self._load_feature_row(self.icu_features, subject_id, hadm_id)
        outcome_features = self._load_feature_row(self.outcome_features, subject_id, hadm_id)
        summary = self._load_case_summary(hadm_id)

        return CaseRecord(
            patient_info=patient_info,
            primary_diagnosis=primary_diagnosis,
            active_specialties=active_specialties,
            specialty_diagnosis_map=specialty_map,
            comorbidity_list=comorbidities,
            key_labs=labs,
            past_history=past_history,
            key_vitals=key_vitals,
            procedure_features=procedure_features,
            microbiology_features=microbiology_features,
            icu_features=icu_features,
            outcome_features=outcome_features,
            raw_case_summary=summary,
        )

    def _parse_specialty_list(self, specialty_list: str) -> list[str]:
        parts = [item.strip() for item in specialty_list.split("|")]
        return [item for item in parts if item in ACTIVE_SPECIALTIES]

    def _build_patient_info(self, subject_id: str, hadm_id: str) -> PatientInfo:
        gender = None
        age = None
        if self.admissions is not None:
            matched = self.admissions[
                (self.admissions["subject_id"] == subject_id) & (self.admissions["hadm_id"] == hadm_id)
            ]
            if not matched.empty:
                row = matched.iloc[0]
                gender = row.get("gender")
                age = self._to_float(row.get("anchor_age"))
        return PatientInfo(subject_id=subject_id, hadm_id=hadm_id, gender=gender, age=age)

    def _load_diagnoses(self, subject_id: str, hadm_id: str) -> pd.DataFrame:
        if self.diagnoses is None:
            return pd.DataFrame(columns=["long_title", "specialty_group", "seq_num"])
        matched = self.diagnoses[
            (self.diagnoses["subject_id"] == subject_id) & (self.diagnoses["hadm_id"] == hadm_id)
        ].copy()
        if "seq_num" in matched.columns:
            matched["seq_num_numeric"] = pd.to_numeric(matched["seq_num"], errors="coerce")
            matched = matched.sort_values(by=["seq_num_numeric", "long_title"], na_position="last")
        return matched

    def _build_specialty_diagnosis_map(
        self,
        diagnoses: pd.DataFrame,
        active_specialties: list[str],
    ) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for specialty in active_specialties:
            if diagnoses.empty:
                result[specialty] = []
                continue
            matched = diagnoses[diagnoses["specialty_group"] == specialty]
            result[specialty] = [
                str(value)
                for value in matched["long_title"].dropna().astype(str).drop_duplicates().tolist()
            ]
        return result

    def _infer_primary_diagnosis(self, diagnoses: pd.DataFrame) -> str:
        if diagnoses.empty:
            return "Unknown primary diagnosis"
        if "seq_num_numeric" in diagnoses.columns:
            primary = diagnoses[diagnoses["seq_num_numeric"] == diagnoses["seq_num_numeric"].min()]
            if not primary.empty:
                return str(primary.iloc[0]["long_title"])
        return str(diagnoses.iloc[0]["long_title"])

    def _infer_comorbidities(self, diagnoses: pd.DataFrame, primary_diagnosis: str) -> list[str]:
        if diagnoses.empty:
            return []
        values = diagnoses["long_title"].dropna().astype(str).drop_duplicates().tolist()
        return [item for item in values if item != primary_diagnosis]

    def _load_feature_row(
        self,
        frame: pd.DataFrame | None,
        subject_id: str,
        hadm_id: str,
    ) -> dict[str, Any]:
        if frame is None:
            return {}
        matched = frame[
            (frame["subject_id"] == subject_id) & (frame["hadm_id"] == hadm_id)
        ]
        if matched.empty:
            return {}
        row = matched.iloc[0].fillna("")
        return {
            key: self._normalize_feature_value(value)
            for key, value in row.to_dict().items()
            if key not in {"subject_id", "hadm_id"}
        }

    def _load_labs(self, subject_id: str, hadm_id: str) -> dict[str, float | None]:
        default_labs = {
            "creatinine_24h": None,
            "bun_24h": None,
            "potassium_24h": None,
            "sodium_24h": None,
            "glucose_24h": None,
            "inr_24h": None,
            "bilirubin_total_24h": None,
        }
        if self.labs is None:
            return default_labs
        matched = self.labs[
            (self.labs["subject_id"] == subject_id) & (self.labs["hadm_id"] == hadm_id)
        ]
        if matched.empty:
            return default_labs
        row = matched.iloc[0]
        for key in default_labs:
            default_labs[key] = self._to_float(row.get(key))
        return default_labs

    def _load_vitals(self, subject_id: str, hadm_id: str) -> dict[str, float | None]:
        default_vitals = {
            "heart_rate_min_24h": None,
            "heart_rate_mean_24h": None,
            "heart_rate_max_24h": None,
            "respiratory_rate_min_24h": None,
            "respiratory_rate_mean_24h": None,
            "respiratory_rate_max_24h": None,
            "temperature_f_min_24h": None,
            "temperature_f_mean_24h": None,
            "temperature_f_max_24h": None,
            "spo2_min_24h": None,
            "spo2_mean_24h": None,
            "spo2_max_24h": None,
            "sbp_min_24h": None,
            "sbp_mean_24h": None,
            "sbp_max_24h": None,
            "dbp_min_24h": None,
            "dbp_mean_24h": None,
            "dbp_max_24h": None,
            "mbp_min_24h": None,
            "mbp_mean_24h": None,
            "mbp_max_24h": None,
        }
        if self.vitals is None:
            return default_vitals
        matched = self.vitals[
            (self.vitals["subject_id"] == subject_id) & (self.vitals["hadm_id"] == hadm_id)
        ]
        if matched.empty:
            return default_vitals
        row = matched.iloc[0]
        for key in default_vitals:
            default_vitals[key] = self._to_float(row.get(key))
        return default_vitals

    def _load_case_summary(self, hadm_id: str) -> dict[str, Any]:
        if self.case_summary is None or "hadm_id" not in self.case_summary.columns:
            return {}
        matched = self.case_summary[self.case_summary["hadm_id"] == hadm_id]
        if matched.empty:
            return {}
        row = matched.iloc[0].fillna("")
        return row.to_dict()

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _normalize_feature_value(value: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return value
