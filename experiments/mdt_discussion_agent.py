from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from experiments.schemas import CandidatePlan, CaseRecord, DiagnosisRouting, SpecialtyAgentResult


@dataclass
class SpecialtyReview:
    reviewer_specialty: str
    accepted_drugs: list[str]
    cautioned_drugs: list[str]
    conflict_notes: list[str]
    priority_comment: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MDTDiscussionResult:
    review_round: list[SpecialtyReview]
    consensus_notes: list[str]
    candidate_plans: list[CandidatePlan]

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_round": [item.to_dict() for item in self.review_round],
            "consensus_notes": self.consensus_notes,
            "candidate_plans": [item.to_dict() for item in self.candidate_plans],
        }


class MDTDiscussionAgent:
    """Rule-based MDT discussion that replaces a single coordinator decision."""

    def discuss(
        self,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
    ) -> MDTDiscussionResult:
        review_round = self._cross_review(case_record, routing, specialty_results)
        candidate_plans = self._build_consensus_plans(routing, specialty_results, review_round)
        consensus_notes = self._build_consensus_notes(routing, specialty_results, review_round, candidate_plans)
        return MDTDiscussionResult(
            review_round=review_round,
            consensus_notes=consensus_notes,
            candidate_plans=candidate_plans,
        )

    def _cross_review(
        self,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
    ) -> list[SpecialtyReview]:
        all_recommended = {
            item.drug_name
            for result in specialty_results
            for item in result.recommended_drugs_topk
            if item.drug_name
        }
        avoid_by_specialty = {
            result.specialty_name: {item.drug_name for item in result.avoid_or_low_priority_drugs}
            for result in specialty_results
        }

        reviews: list[SpecialtyReview] = []
        for result in specialty_results:
            own_drugs = [item.drug_name for item in result.recommended_drugs_topk if item.drug_name]
            other_avoid = set().union(
                *[
                    drugs
                    for specialty, drugs in avoid_by_specialty.items()
                    if specialty != result.specialty_name
                ]
            ) if avoid_by_specialty else set()
            cautioned = sorted(set(own_drugs) & other_avoid)
            accepted = [drug for drug in own_drugs if drug not in cautioned]

            conflict_notes = []
            if cautioned:
                conflict_notes.append(
                    f"{result.specialty_name}建议中的 {', '.join(cautioned)} 被其他专科标记为低优先级，需在共识阶段降权。"
                )
            if result.risk_alerts:
                conflict_notes.append(
                    f"{result.specialty_name}触发 {len(result.risk_alerts)} 条风险提醒，建议安全审核阶段重点复核。"
                )
            if not conflict_notes:
                conflict_notes.append(f"{result.specialty_name}建议未发现明显跨专科冲突。")

            related_diagnoses = routing.specialty_related_diagnoses.get(result.specialty_name, [])
            priority_comment = (
                f"{result.specialty_name}与当前病例 {len(related_diagnoses)} 条诊断相关，"
                f"建议保留 {len(accepted)} 个无明显冲突候选药物。"
            )
            if result.specialty_name == routing.lead_specialty:
                priority_comment += " 该专科为初始主导专科，在共识方案中给予适度优先权。"

            reviews.append(
                SpecialtyReview(
                    reviewer_specialty=result.specialty_name,
                    accepted_drugs=accepted,
                    cautioned_drugs=cautioned,
                    conflict_notes=conflict_notes,
                    priority_comment=priority_comment,
                )
            )

        if not reviews and all_recommended:
            reviews.append(
                SpecialtyReview(
                    reviewer_specialty="MDT",
                    accepted_drugs=sorted(all_recommended),
                    cautioned_drugs=[],
                    conflict_notes=["未生成专科审阅意见，保留全部候选药物进入共识阶段。"],
                    priority_comment="需人工复核该病例的专科参与范围。",
                )
            )
        return reviews

    def _build_consensus_plans(
        self,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
        review_round: list[SpecialtyReview],
    ) -> list[CandidatePlan]:
        lead_specialty = routing.lead_specialty
        vote_counter: Counter[str] = Counter()
        supporters: defaultdict[str, set[str]] = defaultdict(set)
        cautioned_drugs = {
            drug.lower()
            for review in review_round
            for drug in review.cautioned_drugs
        }

        for result in specialty_results:
            for item in result.recommended_drugs_topk:
                if not item.drug_name:
                    continue
                base = 1.0
                if result.specialty_name == lead_specialty:
                    base += 0.35
                if item.drug_name.lower() in cautioned_drugs:
                    base -= 0.45
                vote_counter[item.drug_name] += max(0.05, base + item.confidence)
                supporters[item.drug_name].add(result.specialty_name)

        sorted_drugs = [drug for drug, _ in vote_counter.most_common(12)]
        lead_drugs = []
        if lead_specialty:
            lead_result = next(
                (item for item in specialty_results if item.specialty_name == lead_specialty),
                None,
            )
            if lead_result:
                lead_drugs = [item.drug_name for item in lead_result.recommended_drugs_topk[:5]]

        consensus_drugs = self._dedupe(
            [drug for review in review_round for drug in review.accepted_drugs] + sorted_drugs
        )[:6]
        lead_first_drugs = self._dedupe(lead_drugs + consensus_drugs)[:6]
        conservative_drugs = self._dedupe(
            [drug for drug in sorted_drugs if drug.lower() not in cautioned_drugs]
        )[:4]
        contextual_layers = self._collect_contextual_layer_candidates(specialty_results)
        consensus_layers = self._merge_medication_layers(
            self._build_medication_layers(consensus_drugs, cautioned_drugs),
            contextual_layers,
        )
        lead_first_layers = self._merge_medication_layers(
            self._build_medication_layers(lead_first_drugs, cautioned_drugs),
            contextual_layers,
        )
        conservative_layers = self._merge_medication_layers(
            self._build_medication_layers(conservative_drugs, cautioned_drugs),
            contextual_layers,
        )

        return [
            CandidatePlan(
                plan_id="mdt_consensus",
                plan_name="MDT多专科共识方案",
                drugs=consensus_drugs,
                medication_layers=consensus_layers,
                supporting_specialties=sorted({name for drug in consensus_drugs for name in supporters.get(drug, set())}),
                rationale="由各专科智能体交叉审阅后保留无明显冲突且共识度较高的建议。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in consensus_drugs),
            ),
            CandidatePlan(
                plan_id="lead_specialty_adjusted",
                plan_name="主专科优先修订方案",
                drugs=lead_first_drugs,
                medication_layers=lead_first_layers,
                supporting_specialties=sorted({name for drug in lead_first_drugs for name in supporters.get(drug, set())}),
                rationale="在MDT共识基础上适度突出初始主导专科意见。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in lead_first_drugs),
            ),
            CandidatePlan(
                plan_id="conservative_consensus",
                plan_name="保守低冲突方案",
                drugs=conservative_drugs,
                medication_layers=conservative_layers,
                supporting_specialties=sorted({name for drug in conservative_drugs for name in supporters.get(drug, set())}),
                rationale="剔除交叉审阅中被提示低优先级的候选药物，保留少量共识度较高建议。",
                aggregate_score=sum(vote_counter.get(drug, 0) for drug in conservative_drugs),
            ),
        ]

    def _collect_contextual_layer_candidates(
        self,
        specialty_results: list[SpecialtyAgentResult],
    ) -> dict[str, list[str]]:
        layers = {
            "disease_directed_therapy": [],
            "risk_modifying_therapy": [],
            "supportive_or_symptomatic_therapy": [],
            "general_inpatient_medication": [],
            "requires_review": [],
        }
        for result in specialty_results:
            for item in result.avoid_or_low_priority_drugs:
                drug = item.drug_name
                normalized = drug.lower()
                if any(keyword in normalized for keyword in ["sodium chloride", "dextrose", "flush", "lactated ringer", "sterile water", "vaccine"]):
                    layers["general_inpatient_medication"].append(drug)
                elif any(keyword in normalized for keyword in ["acetaminophen", "ondansetron", "polyethylene glycol", "senna", "docusate", "bisacodyl", "morphine", "oxycodone", "hydromorphone", "lorazepam"]):
                    layers["supportive_or_symptomatic_therapy"].append(drug)
                elif any(keyword in normalized for keyword in ["heparin", "warfarin", "enoxaparin", "apixaban", "aspirin", "furosemide", "metoprolol"]):
                    layers["requires_review"].append(drug)
        return {key: self._dedupe(values)[:6] for key, values in layers.items()}

    def _merge_medication_layers(
        self,
        base_layers: dict[str, list[str]],
        extra_layers: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        merged = {key: list(values) for key, values in base_layers.items()}
        for key, values in extra_layers.items():
            merged.setdefault(key, [])
            merged[key] = self._dedupe(merged[key] + values)
        return merged

    def _build_medication_layers(
        self,
        drugs: list[str],
        cautioned_drugs: set[str],
    ) -> dict[str, list[str]]:
        layers = {
            "disease_directed_therapy": [],
            "risk_modifying_therapy": [],
            "supportive_or_symptomatic_therapy": [],
            "general_inpatient_medication": [],
            "requires_review": [],
        }
        for drug in drugs:
            normalized = drug.lower()
            if normalized in cautioned_drugs:
                layers["requires_review"].append(drug)
                continue
            if any(keyword in normalized for keyword in ["sodium chloride", "dextrose", "flush", "lactated ringer", "sterile water", "vaccine"]):
                layers["general_inpatient_medication"].append(drug)
            elif any(keyword in normalized for keyword in ["heparin", "warfarin", "enoxaparin", "apixaban", "aspirin", "insulin", "furosemide", "torsemide", "metoprolol", "labetalol", "nifedipine", "atorvastatin"]):
                layers["risk_modifying_therapy"].append(drug)
            elif any(keyword in normalized for keyword in ["acetaminophen", "ondansetron", "polyethylene glycol", "senna", "docusate", "bisacodyl", "morphine", "oxycodone", "hydromorphone", "lorazepam"]):
                layers["supportive_or_symptomatic_therapy"].append(drug)
            elif any(keyword in normalized for keyword in ["pantoprazole", "omeprazole", "levothyroxine", "calcium carbonate", "ceftriaxone", "metronidazole", "ciprofloxacin", "albuterol", "ipratropium", "prednisone", "tamsulosin"]):
                layers["disease_directed_therapy"].append(drug)
            else:
                layers["requires_review"].append(drug)
        return layers

    def _build_consensus_notes(
        self,
        routing: DiagnosisRouting,
        specialty_results: list[SpecialtyAgentResult],
        review_round: list[SpecialtyReview],
        candidate_plans: list[CandidatePlan],
    ) -> list[str]:
        specialties = [result.specialty_name for result in specialty_results]
        notes = [
            f"本次MDT协商共纳入 {len(specialties)} 个专科：{', '.join(specialties)}。",
            f"初始主导专科为 {routing.lead_specialty or '未识别'}，但最终方案由各专科交叉审阅后形成。",
        ]
        cautioned_count = sum(len(review.cautioned_drugs) for review in review_round)
        notes.append(f"交叉审阅阶段共标记 {cautioned_count} 个需降权或复核的候选药物。")
        if candidate_plans:
            notes.append(f"共识阶段生成 {len(candidate_plans)} 个候选方案，并交由安全审核智能体进一步筛查。")
        return notes

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen = set()
        ordered = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered
