from __future__ import annotations

from collections import Counter

from experiments.schemas import CaseRecord, DiagnosisRouting


class DiagnosisAgent:
    def route(self, case_record: CaseRecord) -> DiagnosisRouting:
        counts = Counter(
            {
                specialty: len(diagnoses)
                for specialty, diagnoses in case_record.specialty_diagnosis_map.items()
            }
        )
        lead_specialty = counts.most_common(1)[0][0] if counts else None
        rationale = (
            f"根据病例中各专科相关诊断数量进行唤起，当前主专科判定为 {lead_specialty}。"
            if lead_specialty
            else "当前病例未识别出主专科，需人工复核。"
        )
        return DiagnosisRouting(
            active_specialties=case_record.active_specialties,
            lead_specialty=lead_specialty,
            specialty_related_diagnoses=case_record.specialty_diagnosis_map,
            rationale=rationale,
        )
