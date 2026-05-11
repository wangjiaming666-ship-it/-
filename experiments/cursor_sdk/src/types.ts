export interface PatientInfo {
  subject_id: string;
  hadm_id: string;
  gender?: string | null;
  age?: number | null;
}

export interface CaseRecord {
  patient_info: PatientInfo;
  primary_diagnosis: string;
  active_specialties: string[];
  specialty_diagnosis_map: Record<string, string[]>;
  comorbidity_list: string[];
  key_labs: Record<string, number | null>;
  raw_case_summary: Record<string, unknown>;
}

export interface DiagnosisRouting {
  active_specialties: string[];
  lead_specialty: string | null;
  specialty_related_diagnoses: Record<string, string[]>;
  rationale: string;
}

export interface DrugRecommendation {
  rank: number;
  drug_name: string;
  confidence: number;
  reason: string;
}

export interface SpecialtyAgentResult {
  specialty_name: string;
  recommended_drugs_topk: DrugRecommendation[];
  recommendation_reasons: Record<string, string>;
  risk_alerts: Array<Record<string, unknown>>;
  avoid_or_low_priority_drugs: Array<Record<string, unknown>>;
  overall_confidence: number;
  summary_reason: string;
  conversation_text: string;
}

export interface CandidatePlan {
  plan_id: string;
  plan_name: string;
  drugs: string[];
  supporting_specialties: string[];
  rationale: string;
  aggregate_score: number;
}

export interface SafetyResult {
  final_plan: CandidatePlan;
  ranked_plans: Array<Record<string, unknown>>;
  triggered_risks: Array<Record<string, unknown>>;
  safety_summary: string;
  safety_review_source?: string;
}
