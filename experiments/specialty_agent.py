from __future__ import annotations

import json
import re
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


def normalize_for_match(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def row_terms(row: Any, columns: list[str]) -> list[str]:
    terms: list[str] = []
    for column in columns:
        if column not in row:
            continue
        values = split_pipe_values(row.get(column))
        if not values and row.get(column) == row.get(column):
            values = [str(row.get(column))]
        terms.extend(normalize_for_match(value) for value in values if normalize_for_match(value))
    return terms


def has_text_overlap(left_terms: list[str], right_terms: list[str]) -> bool:
    for left in left_terms:
        for right in right_terms:
            if left and right and (left in right or right in left):
                return True
    return False


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
        disease_catalog = kb["disease_catalog"].fillna("")
        drug_catalog = kb["drug_catalog"].fillna("")
        diagnoses = [
            case_record.primary_diagnosis,
            *routing.specialty_related_diagnoses.get(specialty_name, []),
            *case_record.comorbidity_list,
        ]
        diagnosis_terms = [normalize_for_match(item) for item in diagnoses if normalize_for_match(item)]
        matched_diseases = []
        for _, row in disease_catalog.iterrows():
            terms = row_terms(row, ["disease_name", "diagnosis_name", "aliases"])
            if has_text_overlap(terms, diagnosis_terms):
                matched_diseases.append(row)

        drug_scores: dict[str, float] = {}
        drug_reasons: dict[str, list[str]] = {}

        matched_terms: list[str] = []
        for row in matched_diseases:
            matched_terms.extend(row_terms(row, ["disease_name", "diagnosis_name", "aliases"]))
        if not matched_terms:
            matched_terms = diagnosis_terms

        role_weights = {
            "disease_directed_therapy": 1.0,
            "risk_modifying_therapy": 0.85,
        }
        for order, (_, row) in enumerate(drug_catalog.iterrows()):
            role = str(row.get("treatment_role", ""))
            if role not in role_weights:
                continue
            drug = str(row.get("drug_name") or row.get("standard_drug_name"))
            if not drug:
                continue
            context_terms = row_terms(row, ["disease_context"])
            score = role_weights[role] + max(0.0, 0.2 - order * 0.002)
            if matched_terms and context_terms and has_text_overlap(context_terms, matched_terms):
                score += 0.6
                reason = "药物功能知识中的适用疾病背景与当前诊断相匹配"
            else:
                score -= 0.25
                reason = "来自公开药物功能知识，未找到更精确诊断匹配时作为本专科候选"
            drug_scores[drug] = max(drug_scores.get(drug, 0.0), score)
            label = row.get("treatment_role_label", role)
            function = row.get("mechanism_or_function", "")
            drug_reasons.setdefault(drug, []).append(f"{reason}；治疗角色为 {label}；{function}")

        if not drug_scores:
            for _, row in drug_catalog.head(5).iterrows():
                drug = str(row.get("drug_name") or row.get("standard_drug_name"))
                if not drug:
                    continue
                drug_scores[drug] = 0.4
                drug_reasons.setdefault(drug, []).append("来自本专科公开药物功能知识表")

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
            AvoidDrug(
                drug_name=str(row.get("drug_name") or row.get("standard_drug_name")),
                reason="该条目属于支持治疗或住院通用药物，不作为疾病直接治疗首选",
            )
            for _, row in drug_catalog[
                drug_catalog["treatment_role"].isin(
                    ["supportive_or_symptomatic_therapy", "general_inpatient_medication"]
                )
            ].head(8).iterrows()
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
                "diagnosis_alignment": "候选建议参考疾病诊断知识中的疾病名称、别名和诊断依据进行匹配。",
                "knowledge_support": "候选药物来自公开药物功能知识中疾病直接治疗或风险控制角色的条目。",
                "comorbidity_constraint": "已结合共病、既往史和外部治疗风险规则，对支持治疗或通用药物做低优先级标记。",
            },
            risk_alerts=risk_alerts,
            avoid_or_low_priority_drugs=avoid_or_low_priority,
            overall_confidence=overall_confidence,
            summary_reason=f"{specialty_name}智能体已基于疾病诊断知识、公开药物功能知识和外部治疗风险规则生成建议。",
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
