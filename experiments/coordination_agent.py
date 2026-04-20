from __future__ import annotations

import json
from collections import Counter, defaultdict

from experiments.config import LLMSettings
from experiments.llm_client import OpenAICompatibleClient
from experiments.schemas import CandidatePlan, CaseRecord, DiagnosisRouting, SpecialtyAgentResult


class CoordinationAgent:
    def __init__(self, llm_settings: LLMSettings) -> None:
        self.llm_settings = llm_settings
        self.llm_client = OpenAICompatibleClient(llm_settings) if llm_settings.enabled else None

    def coordinate(
        self,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
    ) -> list[CandidatePlan]:
        if self.llm_client is not None:
            try:
                return self._coordinate_with_llm(case_record, routing, specialty_results)
            except Exception:  # noqa: BLE001
                pass
        return self._coordinate_with_rules(routing, specialty_results)

    def _coordinate_with_llm(
        self,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
    ) -> list[CandidatePlan]:
        system_prompt = (
            "你是多专科协商协调智能体。请基于各专科建议生成 3 个候选方案。"
            "输出 JSON，包含 plans 数组，每个 plan 含有 plan_id, plan_name, drugs, supporting_specialties, rationale, aggregate_score。"
        )
        payload = {
            "case": case_record.to_dict(),
            "routing": routing.to_dict(),
            "specialty_results": [item.to_dict() for item in specialty_results],
        }
        response = self.llm_client.chat_json(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2))
        plans = []
        for item in response.get("plans", []):
            plans.append(
                CandidatePlan(
                    plan_id=str(item.get("plan_id", "")),
                    plan_name=str(item.get("plan_name", "")),
                    drugs=[str(drug) for drug in item.get("drugs", [])],
                    supporting_specialties=[str(name) for name in item.get("supporting_specialties", [])],
                    rationale=str(item.get("rationale", "")),
                    aggregate_score=float(item.get("aggregate_score", 0)),
                )
            )
        return plans

    def _coordinate_with_rules(
        self,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
    ) -> list[CandidatePlan]:
        lead_specialty = routing.lead_specialty
        vote_counter: Counter[str] = Counter()
        supporters: defaultdict[str, set[str]] = defaultdict(set)

        for result in specialty_results:
            for item in result.recommended_drugs_topk:
                base = 1.0
                if result.specialty_name == lead_specialty:
                    base += 0.4
                vote_counter[item.drug_name] += base + item.confidence
                supporters[item.drug_name].add(result.specialty_name)

        sorted_drugs = [drug for drug, _ in vote_counter.most_common(10)]
        lead_drugs = []
        if lead_specialty:
            lead_result = next(
                (item for item in specialty_results if item.specialty_name == lead_specialty),
                None,
            )
            if lead_result:
                lead_drugs = [item.drug_name for item in lead_result.recommended_drugs_topk[:5]]

        plan_a_drugs = self._dedupe(lead_drugs + sorted_drugs)[:5]
        plan_b_drugs = self._dedupe(sorted_drugs)[:5]
        plan_c_drugs = self._dedupe(sorted_drugs)[:3]

        return [
            CandidatePlan(
                plan_id="plan_a",
                plan_name="主专科优先方案",
                drugs=plan_a_drugs,
                supporting_specialties=sorted({name for drug in plan_a_drugs for name in supporters.get(drug, set())}),
                rationale="以主专科推荐为核心，同时吸收其他专科共同支持的药物。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in plan_a_drugs),
            ),
            CandidatePlan(
                plan_id="plan_b",
                plan_name="多专科平衡方案",
                drugs=plan_b_drugs,
                supporting_specialties=sorted({name for drug in plan_b_drugs for name in supporters.get(drug, set())}),
                rationale="优先保留被多个专科共同推荐的候选药物。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in plan_b_drugs),
            ),
            CandidatePlan(
                plan_id="plan_c",
                plan_name="保守低负荷方案",
                drugs=plan_c_drugs,
                supporting_specialties=sorted({name for drug in plan_c_drugs for name in supporters.get(drug, set())}),
                rationale="减少药物数量，保留共识度较高的少量核心药物。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in plan_c_drugs),
            ),
        ]

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen = set()
        ordered = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered
