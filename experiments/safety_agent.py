from __future__ import annotations

import json
from typing import Any

from experiments.config import CursorSettings, ExperimentPaths, LLMSettings
from experiments.cursor_client import CursorCloudAgentClient
from experiments.knowledge_base import KnowledgeBaseIndex, SpecialtyKnowledgeLoader
from experiments.llm_client import OpenAICompatibleClient
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


def build_baseline_risk_record(
    specialty: str,
    rule: dict[str, Any],
    lab_value: float,
    risk_level: str,
) -> dict[str, Any]:
    return {
        "specialty_name": specialty,
        "rule_id": rule.get("rule_id"),
        "lab_name": rule.get("lab_name"),
        "lab_value": lab_value,
        "risk_level": risk_level,
        "risk_source": "baseline_first24h_lab",
        "risk_message": rule.get("risk_message"),
        "baseline_interpretation": (
            "该风险由入院后首 24 小时检验识别，表示患者入院早期已经存在的基线风险背景。"
        ),
        "causality_statement": "该风险不表示候选药物导致检验异常。",
        "plan_adaptation": (
            "用于评估候选方案是否适合当前基线风险背景；中度风险以提示和监测为主，高风险才考虑显著降权或排除。"
        ),
    }


def build_plan_adaptation_notes(plan: CandidatePlan, triggered_risks: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    plan_drugs = [drug.lower() for drug in plan.drugs]
    for risk in triggered_risks:
        lab_name = str(risk.get("lab_name", ""))
        risk_level = str(risk.get("risk_level", ""))
        if lab_name == "sodium_24h":
            sodium_sensitive = [
                drug for drug in plan.drugs
                if any(keyword in drug.lower() for keyword in ["furosemide", "torsemide", "hydrochlorothiazide", "sodium"])
            ]
            if sodium_sensitive:
                notes.append(
                    f"患者入院早期钠离子异常，{', '.join(sodium_sensitive)} 可能影响水电解质或容量状态，建议监测并人工复核。"
                )
            else:
                notes.append("患者入院早期钠离子异常，当前方案未识别到明确水钠相关药物，但仍建议复查电解质。")
        elif lab_name in {"creatinine_24h", "bun_24h"}:
            notes.append("患者入院早期存在肾功能相关风险背景，需复核候选药物的肾排泄和肾毒性。")
        elif lab_name == "inr_24h":
            anticoagulants = [
                drug for drug in plan.drugs
                if any(keyword in drug.lower() for keyword in ["warfarin", "heparin", "apixaban", "enoxaparin", "aspirin"])
            ]
            if anticoagulants:
                notes.append(
                    f"患者入院早期凝血风险升高，{', '.join(anticoagulants)} 相关抗凝/抗血小板方案需谨慎复核。"
                )
            else:
                notes.append("患者入院早期凝血风险升高，建议人工复核出血风险。")
        elif lab_name == "bilirubin_total_24h":
            notes.append("患者入院早期存在肝胆代谢风险背景，需复核肝代谢负担较重药物。")
        elif lab_name == "glucose_24h":
            glucose_related = [
                drug for drug in plan.drugs
                if any(keyword in drug.lower() for keyword in ["insulin", "prednisone", "methylpred", "hydrocortisone"])
            ]
            if glucose_related:
                notes.append(
                    f"患者入院早期血糖异常，{', '.join(glucose_related)} 相关方案需结合血糖监测调整。"
                )
            else:
                notes.append("患者入院早期血糖异常，建议结合血糖趋势复核方案。")
        else:
            notes.append(f"患者入院早期 {lab_name} 触发 {risk_level} 风险，建议结合临床背景复核方案。")

    # Remove duplicate notes while preserving order.
    seen: set[str] = set()
    deduped = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            deduped.append(note)
    return deduped


def collect_patient_safety_context(case_record: CaseRecord) -> dict[str, Any]:
    labs = case_record.key_labs
    context = {
        "key_labs": labs,
        "past_history": case_record.past_history,
        "key_vitals": case_record.key_vitals,
        "procedure_features": case_record.procedure_features,
        "microbiology_features": case_record.microbiology_features,
        "icu_features": case_record.icu_features,
        "comorbidities": case_record.comorbidity_list,
        "context_flags": [],
    }

    flags: list[str] = []
    sodium = labs.get("sodium_24h")
    potassium = labs.get("potassium_24h")
    creatinine = labs.get("creatinine_24h")
    inr = labs.get("inr_24h")
    glucose = labs.get("glucose_24h")
    bilirubin = labs.get("bilirubin_total_24h")

    if sodium is not None and (sodium < 135 or sodium > 145):
        flags.append(f"入院早期钠异常: {sodium}")
    if potassium is not None and (potassium < 3.5 or potassium > 5.0):
        flags.append(f"入院早期钾异常: {potassium}")
    if creatinine is not None and creatinine >= 1.5:
        flags.append(f"入院早期肌酐升高: {creatinine}")
    if inr is not None and inr > 1.5:
        flags.append(f"入院早期 INR 升高: {inr}")
    if glucose is not None and (glucose < 70 or glucose > 180):
        flags.append(f"入院早期血糖异常: {glucose}")
    if bilirubin is not None and bilirubin > 2.0:
        flags.append(f"入院早期总胆红素升高: {bilirubin}")

    history = case_record.past_history or {}
    for key, label in [
        ("history_diabetes", "既往糖尿病"),
        ("history_heart_failure", "既往心力衰竭"),
        ("history_coronary_disease", "既往冠心病"),
        ("history_stroke", "既往卒中"),
        ("history_copd", "既往 COPD"),
        ("history_chronic_kidney_disease", "既往慢性肾病"),
        ("history_chronic_liver_disease", "既往慢性肝病"),
        ("history_malignancy", "既往恶性肿瘤"),
    ]:
        if str(history.get(key, "")).strip() in {"1", "1.0", "True", "true"}:
            flags.append(label)

    vitals = case_record.key_vitals or {}
    if _to_float(vitals.get("spo2_min_24h")) is not None and _to_float(vitals.get("spo2_min_24h")) < 90:
        flags.append(f"首 24h SpO2 最低值偏低: {vitals.get('spo2_min_24h')}")
    if _to_float(vitals.get("mbp_min_24h")) is not None and _to_float(vitals.get("mbp_min_24h")) < 65:
        flags.append(f"首 24h 平均动脉压偏低: {vitals.get('mbp_min_24h')}")

    procedure = case_record.procedure_features or {}
    if _to_float(procedure.get("procedure_mechanical_ventilation")) == 1:
        flags.append("本次住院存在机械通气相关操作")
    if _to_float(procedure.get("procedure_renal_replacement")) == 1:
        flags.append("本次住院存在肾脏替代治疗相关操作")

    micro = case_record.microbiology_features or {}
    if _to_float(micro.get("culture_positive_flag")) == 1:
        flags.append("微生物培养阳性")
    if _to_float(micro.get("resistant_result_flag")) == 1:
        flags.append("存在耐药相关结果")

    icu = case_record.icu_features or {}
    if _to_float(icu.get("icu_admission_flag")) == 1:
        flags.append("存在 ICU 暴露")

    context["context_flags"] = flags
    return context


def assess_medication_impacts(plan: CandidatePlan, context: dict[str, Any]) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    labs = context.get("key_labs", {})
    flags = context.get("context_flags", [])
    for drug in plan.drugs:
        normalized = drug.lower()
        drug_impacts: list[str] = []
        suggested_action = "保留，常规监测"
        severity = "low"

        if any(keyword in normalized for keyword in ["furosemide", "torsemide", "hydrochlorothiazide"]):
            drug_impacts.append("可能影响容量状态和水电解质平衡")
            if labs.get("sodium_24h") is not None and (labs["sodium_24h"] < 135 or labs["sodium_24h"] > 145):
                severity = "moderate"
                suggested_action = "保留但需复查电解质和容量状态，必要时人工复核"
        if any(keyword in normalized for keyword in ["warfarin", "heparin", "enoxaparin", "apixaban", "aspirin"]):
            drug_impacts.append("涉及抗凝或抗血小板相关出血风险")
            if labs.get("inr_24h") is not None and labs["inr_24h"] > 1.5:
                severity = "high"
                suggested_action = "显著降权或人工复核出血风险后再使用"
        if "insulin" in normalized:
            drug_impacts.append("影响血糖控制，需结合血糖趋势调整")
            if labs.get("glucose_24h") is not None and (labs["glucose_24h"] < 70 or labs["glucose_24h"] > 180):
                severity = "moderate"
                suggested_action = "保留但需加强血糖监测"
        if any(keyword in normalized for keyword in ["ciprofloxacin", "gentamicin", "vancomycin"]):
            drug_impacts.append("抗感染药物需结合肾功能、培养和耐药结果复核")
            if any("慢性肾病" in flag or "肌酐升高" in flag for flag in flags):
                severity = "moderate"
                suggested_action = "复核肾功能和剂量"
        if any(keyword in normalized for keyword in ["pantoprazole", "omeprazole"]):
            drug_impacts.append("胃酸抑制相关支持/治疗药物，通常安全性较高")
        if "polyethylene glycol" in normalized:
            drug_impacts.append("通便/肠道准备相关药物，需结合容量和电解质状态")
        if "levothyroxine" in normalized:
            drug_impacts.append("甲状腺激素相关治疗，需结合甲状腺功能和心血管背景")
        if "calcium carbonate" in normalized:
            drug_impacts.append("钙剂相关治疗，需结合钙磷代谢和肾功能背景")

        if drug_impacts:
            impacts.append(
                {
                    "drug_name": drug,
                    "potential_impacts": drug_impacts,
                    "severity": severity,
                    "suggested_action": suggested_action,
                }
            )

    return impacts


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None


class SafetyAgent:
    def __init__(
        self,
        paths: ExperimentPaths,
        llm_settings: LLMSettings | None = None,
        cursor_settings: CursorSettings | None = None,
    ) -> None:
        self.kb_index = KnowledgeBaseIndex(paths)
        self.kb_loader = SpecialtyKnowledgeLoader(self.kb_index)
        self.llm_settings = llm_settings
        self.llm_client = (
            OpenAICompatibleClient(llm_settings)
            if llm_settings is not None and llm_settings.enabled
            else None
        )
        self.cursor_settings = cursor_settings or CursorSettings()
        self.cursor_client = (
            CursorCloudAgentClient(self.cursor_settings)
            if self.cursor_settings.enabled
            else None
        )

    def screen(
        self,
        case_record: CaseRecord,
        candidate_plans: list[CandidatePlan],
        specialty_outputs: list[SpecialtyAgentResult],
    ) -> SafetyScreeningResult:
        triggered_risks: list[dict[str, Any]] = []
        patient_safety_context = collect_patient_safety_context(case_record)

        for specialty in case_record.active_specialties:
            kb = self.kb_loader.load(specialty)
            for rule in kb["risk_rules"]:
                lab_name = rule["lab_name"]
                lab_value = case_record.key_labs.get(lab_name)
                risk_level = evaluate_risk_rule(rule, lab_value)
                if risk_level is None:
                    continue
                triggered_risks.append(build_baseline_risk_record(specialty, rule, lab_value, risk_level))

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
            baseline_risk_penalty = high_risk_count * 3 + moderate_risk_count
            risk_penalty = baseline_risk_penalty + avoid_penalty
            internal_priority_score = plan.aggregate_score - risk_penalty
            adaptation_notes = build_plan_adaptation_notes(plan, triggered_risks)
            medication_impacts = assess_medication_impacts(plan, patient_safety_context)
            medication_penalty = sum(2 if item["severity"] == "high" else 1 for item in medication_impacts if item["severity"] != "low")
            internal_priority_score -= medication_penalty
            review_flags = []
            if high_risk_count:
                review_flags.append("存在高风险基线指标")
            if moderate_risk_count:
                review_flags.append("存在中度基线风险")
            if avoid_penalty:
                review_flags.append("包含低优先级或需避免药物")
            if medication_penalty:
                review_flags.append("候选药物与患者风险背景存在适配性问题")
            if not review_flags:
                review_flags.append("未发现明确安全冲突")
            ranked_plans.append(
                {
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "drugs": plan.drugs,
                    "medication_layers": plan.medication_layers,
                    "supporting_specialties": plan.supporting_specialties,
                    "_internal_priority_score": internal_priority_score,
                    "review_flags": review_flags,
                    "safety_decision": "需人工复核" if high_risk_count or medication_penalty >= 2 else "可作为候选",
                    "patient_context_flags": patient_safety_context["context_flags"],
                    "medication_impact_review": medication_impacts,
                    "plan_adaptation_notes": adaptation_notes,
                    "safety_interpretation": (
                        "安全审核综合入院早期基线风险、患者多维临床背景、候选药物潜在影响和低优先级药物提示；不表示候选药物导致检验异常。"
                    ),
                    "rationale": plan.rationale,
                }
            )

        ranked_plans = sorted(ranked_plans, key=lambda item: item["_internal_priority_score"], reverse=True)
        llm_safety_review: dict[str, Any] = {}
        preferred_plan_id: str | None = None
        if self.cursor_client is not None:
            try:
                llm_safety_review = self._review_with_cursor(
                    case_record=case_record,
                    ranked_plans=ranked_plans,
                    triggered_risks=triggered_risks,
                    specialty_outputs=specialty_outputs,
                    patient_safety_context=patient_safety_context,
                )
                candidate_id = llm_safety_review.get("preferred_plan_id")
                if isinstance(candidate_id, str) and any(plan["plan_id"] == candidate_id for plan in ranked_plans):
                    preferred_plan_id = candidate_id
            except Exception as exc:  # noqa: BLE001
                llm_safety_review = {
                    "enabled": True,
                    "provider": "cursor_cloud_agent",
                    "status": "failed",
                    "error": str(exc),
                    "fallback": "使用规则型基线风险适配审核结果。",
                }
        elif self.llm_client is not None:
            try:
                llm_safety_review = self._review_with_llm(
                    case_record=case_record,
                    ranked_plans=ranked_plans,
                    triggered_risks=triggered_risks,
                    specialty_outputs=specialty_outputs,
                    patient_safety_context=patient_safety_context,
                )
                candidate_id = llm_safety_review.get("preferred_plan_id")
                if isinstance(candidate_id, str) and any(plan["plan_id"] == candidate_id for plan in ranked_plans):
                    preferred_plan_id = candidate_id
            except Exception as exc:  # noqa: BLE001
                llm_safety_review = {
                    "enabled": True,
                    "status": "failed",
                    "error": str(exc),
                    "fallback": "使用规则型基线风险适配审核结果。",
                }

        top = next((plan for plan in ranked_plans if plan["plan_id"] == preferred_plan_id), ranked_plans[0])
        final_plan = CandidatePlan(
            plan_id=top["plan_id"],
            plan_name=top["plan_name"],
            drugs=top["drugs"],
            medication_layers=top.get("medication_layers", {}),
            supporting_specialties=top["supporting_specialties"],
            rationale=top["rationale"],
            aggregate_score=float(top["_internal_priority_score"]),
        )
        summary = (
            "安全智能体已综合入院早期检验、既往史、生命体征、操作/微生物/ICU 信息及候选药物潜在影响，"
            "对候选方案做风险适配审核；风险提示不表示候选药物导致检验异常。"
        )
        if llm_safety_review and llm_safety_review.get("status") == "completed":
            summary = (
                "安全智能体已结合规则型基线风险识别和大模型安全审核技能，对候选方案进行适配性复核；"
                "检验异常被解释为入院早期基线风险，不归因于候选药物。"
            )

        public_ranked_plans = []
        for index, plan in enumerate(ranked_plans, start=1):
            public_plan = {key: value for key, value in plan.items() if key != "_internal_priority_score"}
            public_plan["priority_order"] = index
            public_ranked_plans.append(public_plan)

        return SafetyScreeningResult(
            final_plan=final_plan,
            ranked_plans=public_ranked_plans,
            triggered_risks=triggered_risks,
            safety_summary=summary,
            llm_safety_review=llm_safety_review,
        )

    def _review_with_llm(
        self,
        case_record: CaseRecord,
        ranked_plans: list[dict[str, Any]],
        triggered_risks: list[dict[str, Any]],
        specialty_outputs: list[SpecialtyAgentResult],
        patient_safety_context: dict[str, Any],
    ) -> dict[str, Any]:
        system_prompt = (
            "你是 MDT 多智能体系统中的安全审核智能体，具备“临床安全审核技能”。"
            "你的任务不是判断药物导致了入院早期检验异常，而是基于首24小时检验识别患者基线风险，"
            "并评估候选方案与该风险背景是否适配。"
            "必须输出 JSON，不得输出额外文本。"
            "安全审核技能清单："
            "1. 区分基线风险和药物不良反应；"
            "2. 综合患者指标、既往史、生命体征、操作、微生物、ICU 暴露和候选药物影响做适配性审核；"
            "3. 对可能加重风险背景的候选药物给出监测、降权或人工复核建议；"
            "4. 中度风险以提示和监测为主，高风险才建议显著降权或排除；"
            "5. 不得编造病例中不存在的检查、诊断或药物。"
            "输出字段：status, preferred_plan_id, baseline_risk_assessment, medication_fit_review, "
            "monitoring_recommendations, human_review_required, safety_explanation。"
        )
        payload = {
            "case_record": case_record.to_dict(),
            "patient_safety_context": patient_safety_context,
            "ranked_plans_from_rules": ranked_plans,
            "baseline_risks_from_rules": triggered_risks,
            "specialty_outputs": [item.to_dict() for item in specialty_outputs],
            "instruction": (
                "请复核规则型安全审核结果。preferred_plan_id 必须来自 ranked_plans_from_rules。"
                "请重点说明基线风险与候选药物因果无关，只用于方案适配审核。"
            ),
        }
        result = self.llm_client.chat_json(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2))
        result["enabled"] = True
        result["provider"] = "openai_compatible"
        result["status"] = result.get("status", "completed")
        return result

    def _review_with_cursor(
        self,
        case_record: CaseRecord,
        ranked_plans: list[dict[str, Any]],
        triggered_risks: list[dict[str, Any]],
        specialty_outputs: list[SpecialtyAgentResult],
        patient_safety_context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = self._build_safety_review_prompt(
            case_record=case_record,
            ranked_plans=ranked_plans,
            triggered_risks=triggered_risks,
            specialty_outputs=specialty_outputs,
            patient_safety_context=patient_safety_context,
        )
        result = self.cursor_client.run_json_prompt(prompt)
        result["enabled"] = True
        result["provider"] = "cursor_cloud_agent"
        result["status"] = result.get("status", "completed")
        return result

    def _build_safety_review_prompt(
        self,
        case_record: CaseRecord,
        ranked_plans: list[dict[str, Any]],
        triggered_risks: list[dict[str, Any]],
        specialty_outputs: list[SpecialtyAgentResult],
        patient_safety_context: dict[str, Any],
    ) -> str:
        payload = {
            "case_record": case_record.to_dict(),
            "patient_safety_context": patient_safety_context,
            "ranked_plans_from_rules": ranked_plans,
            "baseline_risks_from_rules": triggered_risks,
            "specialty_outputs": [item.to_dict() for item in specialty_outputs],
            "instruction": (
                "请复核规则型安全审核结果。preferred_plan_id 必须来自 ranked_plans_from_rules。"
                "请重点说明基线风险与候选药物因果无关，只用于方案适配审核。"
            ),
        }
        return "\n\n".join(
            [
                "你现在扮演 MDT 多智能体系统中的安全审核智能体，具备临床安全审核技能。",
                "你的任务不是判断药物导致了入院早期检验异常，而是基于首24小时检验识别患者基线风险，并评估候选方案与该风险背景是否适配。",
                "安全审核技能清单：1. 区分基线风险和药物不良反应；2. 综合患者指标、既往史、生命体征、操作、微生物、ICU 暴露和候选药物影响做适配性审核；3. 对可能加重风险背景的候选药物给出监测、降权或人工复核建议；4. 中度风险以提示和监测为主，高风险才建议显著降权或排除；5. 不得编造病例中不存在的检查、诊断或药物。",
                "你必须严格输出 JSON，不允许输出 Markdown，不允许输出额外解释。",
                "输出字段：status, preferred_plan_id, baseline_risk_assessment, medication_fit_review, monitoring_recommendations, human_review_required, safety_explanation。",
                "输入数据如下：",
                json.dumps(payload, ensure_ascii=False, indent=2),
            ]
        )
