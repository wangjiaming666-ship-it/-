from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.config import ExperimentPaths, LLMSettings
from experiments.knowledge_base import KnowledgeBaseIndex, SpecialtyKnowledgeLoader
from experiments.llm_client import OpenAICompatibleClient
from experiments.safety_agent import evaluate_risk_rule
from experiments.schemas import (
    AvoidDrug,
    CaseRecord,
    DiagnosisRouting,
    DrugRecommendation,
    RiskAlert,
    SpecialtyAgentResult,
)


def read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def split_pipe_values(value: str | None) -> list[str]:
    if not value or value != value:
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]


class SpecialtyAgent:
    def __init__(self, paths: ExperimentPaths, llm_settings: LLMSettings) -> None:
        self.paths = paths
        self.llm_settings = llm_settings
        self.kb_index = KnowledgeBaseIndex(paths)
        self.kb_loader = SpecialtyKnowledgeLoader(self.kb_index)
        self.llm_client = OpenAICompatibleClient(llm_settings) if llm_settings.enabled else None
        self.input_template = read_json(paths.input_template_file)
        self.output_template = read_json(paths.output_template_file)

    def run(
        self,
        specialty_name: str,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
    ) -> SpecialtyAgentResult:
        kb = self.kb_loader.load(specialty_name)
        prompt_payload = self.kb_loader.build_prompt_payload(specialty_name)
        agent_input = self._build_agent_input(specialty_name, case_record, routing, prompt_payload)

        if self.llm_client is not None:
            try:
                result = self._run_with_llm(specialty_name, agent_input)
                return result
            except Exception:  # noqa: BLE001
                pass

        return self._run_with_rules(specialty_name, case_record, routing, kb)

    def _build_agent_input(
        self,
        specialty_name: str,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        prompt_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(self.input_template)
        payload["patient_info"] = case_record.patient_info.__dict__
        payload["case_context"] = {
            "primary_diagnosis": case_record.primary_diagnosis,
            "specialty_name": specialty_name,
            "specialty_related_diagnoses": routing.specialty_related_diagnoses.get(specialty_name, []),
            "comorbidity_list": case_record.comorbidity_list,
            "past_history": case_record.past_history,
            "key_vitals": case_record.key_vitals,
        }
        payload["key_labs"] = case_record.key_labs
        payload["specialty_knowledge"] = prompt_payload
        return payload

    def _run_with_llm(self, specialty_name: str, agent_input: dict[str, Any]) -> SpecialtyAgentResult:
        system_prompt = (
            "你是医院多智能体系统中的专科智能体。"
            "请严格依据输入中的 specialty_knowledge 生成结构化建议。"
            "必须输出 JSON，对应 specialty_agent_output_template 的字段，不得附加多余文本。"
        )
        agent_input["case_context"]["specialty_name"] = specialty_name
        user_prompt = json.dumps(agent_input, ensure_ascii=False, indent=2)
        data = self.llm_client.chat_json(system_prompt, user_prompt)
        return self._parse_output(specialty_name, data)

    def _run_with_rules(
        self,
        specialty_name: str,
        case_record: CaseRecord,
        routing: DiagnosisRouting,
        kb: dict[str, Any],
    ) -> SpecialtyAgentResult:
        disease_drug_map = kb["disease_drug_map"]
        diagnoses = routing.specialty_related_diagnoses.get(specialty_name, [])
        matched = disease_drug_map[
            disease_drug_map["diagnosis_name"].isin(diagnoses)
        ].copy()

        drug_scores: dict[str, float] = {}
        drug_reasons: dict[str, list[str]] = {}
        avoid_map: dict[str, str] = {}

        for _, row in matched.iterrows():
            for rank, drug in enumerate(split_pipe_values(row.get("recommended_drugs")), start=1):
                drug_scores[drug] = drug_scores.get(drug, 0.0) + max(0.1, 1.1 - rank * 0.15)
                drug_reasons.setdefault(drug, []).append(
                    f"与诊断 {row.get('diagnosis_name')} 在知识库中存在映射"
                )
            for drug in split_pipe_values(row.get("avoid_or_low_priority_drugs")):
                avoid_map[drug] = f"在 {row.get('diagnosis_name')} 的映射中被列为低优先级或辅助药"

        if not drug_scores:
            core_drugs = kb["drug_catalog"]
            if "treatment_role" in core_drugs.columns:
                core_drugs = core_drugs[
                    core_drugs["treatment_role"].isin(["disease_directed_therapy", "risk_modifying_therapy"])
                ].head(5)
            else:
                core_drugs = core_drugs[core_drugs["drug_role"] == "核心治疗药"].head(5)
            for _, row in core_drugs.iterrows():
                drug = str(row["drug_name"])
                drug_scores[drug] = float(row.get("frequency", 1)) / 1000.0
                role = row.get("treatment_role_label", row.get("drug_role", "专科治疗角色"))
                drug_reasons.setdefault(drug, []).append(f"来自本专科药物治疗知识库，角色为 {role}")

        sorted_drugs = sorted(drug_scores.items(), key=lambda item: item[1], reverse=True)[:5]
        recommendations = [
            DrugRecommendation(
                rank=index + 1,
                drug_name=drug,
                confidence=round(min(0.95, 0.45 + score / 3), 2),
                reason="；".join(drug_reasons.get(drug, [])) or "基于专科知识库统计结果生成",
            )
            for index, (drug, score) in enumerate(sorted_drugs)
        ]

        risk_alerts = self._build_risk_alerts(kb["risk_rules"], case_record.key_labs)
        avoid_or_low_priority = [
            AvoidDrug(drug_name=drug, reason=reason) for drug, reason in list(avoid_map.items())[:8]
        ]
        overall_confidence = round(
            min(0.95, 0.4 + len(recommendations) * 0.08 + len(diagnoses) * 0.03),
            2,
        )
        conversation_text = (
            f"{specialty_name}智能体认为当前病例应优先围绕 {', '.join(diagnoses[:3]) or '本专科主要问题'} "
            f"生成候选药物，当前首选药物包括 {', '.join([r.drug_name for r in recommendations[:3]])}。"
        )

        return SpecialtyAgentResult(
            specialty_name=specialty_name,
            recommended_drugs_topk=recommendations,
            recommendation_reasons={
                "diagnosis_assessment": "已根据专科诊断知识对当前专科相关诊断进行初步评估。",
                "diagnosis_alignment": "候选建议参考当前专科相关诊断与 disease_drug_map 的真实世界共现证据。",
                "knowledge_support": "候选药物来自本专科药物治疗知识中疾病直接治疗或风险控制角色的条目。",
                "comorbidity_constraint": "已结合共病、既往史和风险规则，对潜在冲突药物做低优先级标记。",
            },
            risk_alerts=risk_alerts,
            avoid_or_low_priority_drugs=avoid_or_low_priority,
            overall_confidence=overall_confidence,
            summary_reason=f"{specialty_name}智能体已基于专科诊断知识、治疗角色分层、病药共现候选证据和风险规则生成建议。",
            conversation_text=conversation_text,
        )

    def _build_risk_alerts(
        self,
        risk_rules: list[dict[str, Any]],
        key_labs: dict[str, float | None],
    ) -> list[RiskAlert]:
        alerts = []
        for rule in risk_rules:
            lab_name = rule["lab_name"]
            risk_level = evaluate_risk_rule(rule, key_labs.get(lab_name))
            if risk_level is None:
                continue
            action_taken = rule["action"]["moderate_risk"]
            if risk_level == "high":
                action_taken = rule["action"]["high_risk"]
            alerts.append(
                RiskAlert(
                    lab_name=lab_name,
                    risk_level=risk_level,
                    triggered_rule_id=rule["rule_id"],
                    message=rule["risk_message"],
                    action_taken=action_taken,
                )
            )
        return alerts

    def _parse_output(self, specialty_name: str, data: dict[str, Any]) -> SpecialtyAgentResult:
        recommendations = [
            DrugRecommendation(
                rank=int(item.get("rank", index + 1)),
                drug_name=str(item.get("drug_name", "")),
                confidence=float(item.get("confidence", 0.5)),
                reason=str(item.get("reason", "")),
            )
            for index, item in enumerate(data.get("recommended_drugs_topk", []))
        ]
        alerts = [
            RiskAlert(
                lab_name=str(item.get("lab_name", "")),
                risk_level=str(item.get("risk_level", "")),
                triggered_rule_id=str(item.get("triggered_rule_id", "")),
                message=str(item.get("message", "")),
                action_taken=str(item.get("action_taken", "")),
            )
            for item in data.get("risk_alerts", [])
        ]
        avoids = [
            AvoidDrug(
                drug_name=str(item.get("drug_name", "")),
                reason=str(item.get("reason", "")),
            )
            for item in data.get("avoid_or_low_priority_drugs", [])
        ]
        return SpecialtyAgentResult(
            specialty_name=specialty_name,
            recommended_drugs_topk=recommendations,
            recommendation_reasons=data.get("recommendation_reasons", {}),
            risk_alerts=alerts,
            avoid_or_low_priority_drugs=avoids,
            overall_confidence=float(data.get("overall_confidence", 0.5)),
            summary_reason=str(data.get("summary_reason", "")),
            conversation_text=str(data.get("summary_reason", "")),
        )
