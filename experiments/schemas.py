from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PatientInfo:
    subject_id: str
    hadm_id: str
    gender: str | None
    age: float | None


@dataclass
class CaseRecord:
    patient_info: PatientInfo
    primary_diagnosis: str
    active_specialties: list[str]
    specialty_diagnosis_map: dict[str, list[str]]
    comorbidity_list: list[str]
    key_labs: dict[str, float | None]
    past_history: dict[str, Any] = field(default_factory=dict)
    key_vitals: dict[str, float | None] = field(default_factory=dict)
    procedure_features: dict[str, Any] = field(default_factory=dict)
    microbiology_features: dict[str, Any] = field(default_factory=dict)
    icu_features: dict[str, Any] = field(default_factory=dict)
    outcome_features: dict[str, Any] = field(default_factory=dict)
    raw_case_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosisRouting:
    active_specialties: list[str]
    lead_specialty: str | None
    specialty_related_diagnoses: dict[str, list[str]]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DrugRecommendation:
    rank: int
    drug_name: str
    confidence: float
    reason: str


@dataclass
class RiskAlert:
    lab_name: str
    risk_level: str
    triggered_rule_id: str
    message: str
    action_taken: str


@dataclass
class AvoidDrug:
    drug_name: str
    reason: str


@dataclass
class SpecialtyAgentResult:
    specialty_name: str
    recommended_drugs_topk: list[DrugRecommendation]
    recommendation_reasons: dict[str, str]
    risk_alerts: list[RiskAlert]
    avoid_or_low_priority_drugs: list[AvoidDrug]
    overall_confidence: float
    summary_reason: str
    conversation_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class CandidatePlan:
    plan_id: str
    plan_name: str
    drugs: list[str]
    supporting_specialties: list[str]
    rationale: str
    aggregate_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyScreeningResult:
    final_plan: CandidatePlan
    ranked_plans: list[dict[str, Any]]
    triggered_risks: list[dict[str, Any]]
    safety_summary: str
    llm_safety_review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_plan": self.final_plan.to_dict(),
            "ranked_plans": self.ranked_plans,
            "triggered_risks": self.triggered_risks,
            "safety_summary": self.safety_summary,
            "llm_safety_review": self.llm_safety_review,
        }


@dataclass
class DialogueMessage:
    round_id: int
    speaker: str
    message_type: str
    content: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
