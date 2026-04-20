from __future__ import annotations

from typing import Any

from experiments.config import ExperimentPaths
from experiments.knowledge_base import KnowledgeBaseIndex, SpecialtyKnowledgeLoader
from experiments.schemas import CandidatePlan, CaseRecord, SafetyScreeningResult, SpecialtyAgentResult


def evaluate_risk_rule(rule: dict[str, Any], lab_value: float | None) -> str | None:
    if lab_value is None:
        return None

    threshold_type = rule.get("threshold_type")
    moderate = rule.get("moderate_risk_threshold", {})
    high = rule.get("high_risk_threshold", {})

    if threshold_type == "upper_bound":
        high_value = high.get("value")
        moderate_value = moderate.get("value")
        if high_value is not None and lab_value > float(high_value):
            return "high"
        if moderate_value is not None and lab_value > float(moderate_value):
            return "moderate"
        return None

    if threshold_type in {"range", "bidirectional"}:
        high_low = high.get("low")
        high_high = high.get("high")
        mod_low = moderate.get("low")
        mod_high = moderate.get("high")

        if high_low is not None and high_high is not None:
            if lab_value < float(high_low) or lab_value > float(high_high):
                return "high"
        if mod_low is not None and mod_high is not None:
            if lab_value < float(mod_low) or lab_value > float(mod_high):
                return "moderate"
        return None

    return None


class SafetyAgent:
    def __init__(self, paths: ExperimentPaths) -> None:
        self.kb_index = KnowledgeBaseIndex(paths)
        self.kb_loader = SpecialtyKnowledgeLoader(self.kb_index)

    def screen(
        self,
        case_record: CaseRecord,
        candidate_plans: list[CandidatePlan],
        specialty_outputs: list[SpecialtyAgentResult],
    ) -> SafetyScreeningResult:
        triggered_risks: list[dict[str, Any]] = []

        for specialty in case_record.active_specialties:
            kb = self.kb_loader.load(specialty)
            for rule in kb["risk_rules"]:
                lab_name = rule["lab_name"]
                lab_value = case_record.key_labs.get(lab_name)
                risk_level = evaluate_risk_rule(rule, lab_value)
                if risk_level is None:
                    continue
                triggered_risks.append(
                    {
                        "specialty_name": specialty,
                        "rule_id": rule.get("rule_id"),
                        "lab_name": lab_name,
                        "lab_value": lab_value,
                        "risk_level": risk_level,
                        "risk_message": rule.get("risk_message"),
                    }
                )

        avoid_drugs = {
            item.drug_name.lower()
            for output in specialty_outputs
            for item in output.avoid_or_low_priority_drugs
        }

        ranked_plans = []
        for plan in candidate_plans:
            high_risk_count = sum(1 for item in triggered_risks if item["risk_level"] == "high")
            moderate_risk_count = sum(1 for item in triggered_risks if item["risk_level"] == "moderate")
            avoid_penalty = sum(1 for drug in plan.drugs if drug.lower() in avoid_drugs)
            risk_penalty = high_risk_count * 3 + moderate_risk_count + avoid_penalty
            final_score = plan.aggregate_score - risk_penalty
            ranked_plans.append(
                {
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "drugs": plan.drugs,
                    "supporting_specialties": plan.supporting_specialties,
                    "aggregate_score": plan.aggregate_score,
                    "risk_penalty": risk_penalty,
                    "final_score": final_score,
                    "rationale": plan.rationale,
                }
            )

        ranked_plans = sorted(ranked_plans, key=lambda item: item["final_score"], reverse=True)
        top = ranked_plans[0]
        final_plan = CandidatePlan(
            plan_id=top["plan_id"],
            plan_name=top["plan_name"],
            drugs=top["drugs"],
            supporting_specialties=top["supporting_specialties"],
            rationale=top["rationale"],
            aggregate_score=float(top["final_score"]),
        )
        summary = (
            "安全智能体已基于各专科风险规则和关键检验值对候选方案做二次筛查，并选择风险惩罚后得分最高的方案。"
        )

        return SafetyScreeningResult(
            final_plan=final_plan,
            ranked_plans=ranked_plans,
            triggered_risks=triggered_risks,
            safety_summary=summary,
        )
