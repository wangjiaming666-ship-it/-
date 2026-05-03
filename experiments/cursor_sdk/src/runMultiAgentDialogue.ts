import path from "node:path";

import { ACTIVE_SPECIALTIES, OUTPUTS_DIR } from "./config.js";
import { exportCaseBundle } from "./caseBridge.js";
import { buildJsonPrompt, runCursorAgent } from "./cursorAgentRunner.js";
import { extractAvoidDrugs, loadSpecialtyKnowledge } from "./knowledgeBase.js";
import type {
  CandidatePlan,
  CaseRecord,
  DiagnosisRouting,
  SafetyResult,
  SpecialtyAgentResult,
} from "./types.js";
import { writeJsonFile } from "./utils.js";

function getArg(name: string, defaultValue = ""): string {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    return defaultValue;
  }
  return process.argv[index + 1] ?? defaultValue;
}

function parseJsonText<T>(text: string): T {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1) {
    throw new Error("Cursor Agent 未返回可解析 JSON。");
  }
  return JSON.parse(text.slice(start, end + 1)) as T;
}

function buildDiagnosisFallback(caseRecord: CaseRecord): DiagnosisRouting {
  let leadSpecialty = caseRecord.active_specialties[0] ?? null;
  let maxCount = -1;
  for (const specialty of caseRecord.active_specialties) {
    const count = (caseRecord.specialty_diagnosis_map[specialty] ?? []).length;
    if (count > maxCount) {
      maxCount = count;
      leadSpecialty = specialty;
    }
  }
  return {
    active_specialties: caseRecord.active_specialties,
    lead_specialty: leadSpecialty,
    specialty_related_diagnoses: caseRecord.specialty_diagnosis_map,
    rationale: "按病例内各专科相关诊断数量最多原则确定主专科。",
  };
}

async function runDiagnosisAgent(caseRecord: CaseRecord): Promise<DiagnosisRouting> {
  const payload = {
    patient_info: caseRecord.patient_info,
    primary_diagnosis: caseRecord.primary_diagnosis,
    active_specialties: caseRecord.active_specialties,
    specialty_diagnosis_map: caseRecord.specialty_diagnosis_map,
    comorbidity_list: caseRecord.comorbidity_list,
  };
  const prompt = buildJsonPrompt(
    "诊断智能体",
    "你的任务是根据病例已有的专科候选和相关诊断，确认需要唤起的专科、主专科，以及每个专科应重点关注的相关诊断。",
    payload,
    "{ active_specialties: string[], lead_specialty: string, specialty_related_diagnoses: Record<string,string[]>, rationale: string }",
  );

  try {
    const text = await runCursorAgent(prompt);
    const data = parseJsonText<DiagnosisRouting>(text);
    data.active_specialties = data.active_specialties.filter((item) => ACTIVE_SPECIALTIES.includes(item));
    return data;
  } catch {
    return buildDiagnosisFallback(caseRecord);
  }
}

async function runSpecialtyAgent(
  specialtyName: string,
  caseRecord: CaseRecord,
  routing: DiagnosisRouting,
): Promise<SpecialtyAgentResult> {
  const kb = loadSpecialtyKnowledge(specialtyName);
  const payload = {
    patient_info: caseRecord.patient_info,
    primary_diagnosis: caseRecord.primary_diagnosis,
    specialty_name: specialtyName,
    specialty_related_diagnoses: routing.specialty_related_diagnoses[specialtyName] ?? [],
    comorbidity_list: caseRecord.comorbidity_list,
    key_labs: caseRecord.key_labs,
    specialty_knowledge: kb.promptPayload,
  };
  const prompt = buildJsonPrompt(
    `${specialtyName}专科智能体`,
    "你需要基于本专科知识库给出候选药物 Top-K、推荐理由、风险提示、不建议药物和整体置信度。若知识不足，可适当保守。",
    payload,
    "{ specialty_name: string, recommended_drugs_topk: {rank:number, drug_name:string, confidence:number, reason:string}[], recommendation_reasons: Record<string,string>, risk_alerts: any[], avoid_or_low_priority_drugs: {drug_name:string, reason:string}[], overall_confidence:number, summary_reason:string, conversation_text:string }",
  );

  const text = await runCursorAgent(prompt);
  return parseJsonText<SpecialtyAgentResult>(text);
}

async function runCoordinationAgent(
  caseRecord: CaseRecord,
  routing: DiagnosisRouting,
  specialtyResults: SpecialtyAgentResult[],
): Promise<CandidatePlan[]> {
  const payload = {
    patient_info: caseRecord.patient_info,
    primary_diagnosis: caseRecord.primary_diagnosis,
    lead_specialty: routing.lead_specialty,
    specialty_results: specialtyResults,
  };
  const prompt = buildJsonPrompt(
    "协调智能体",
    "你需要汇总各专科建议，输出 3 个候选处方方案：主专科优先方案、多专科平衡方案、保守低风险方案。",
    payload,
    "{ plans: { plan_id:string, plan_name:string, drugs:string[], supporting_specialties:string[], rationale:string, aggregate_score:number }[] }",
  );

  try {
    const text = await runCursorAgent(prompt);
    const data = parseJsonText<{ plans: CandidatePlan[] }>(text);
    return data.plans;
  } catch {
    const merged = new Map<string, { score: number; supporters: Set<string> }>();
    for (const result of specialtyResults) {
      for (const rec of result.recommended_drugs_topk) {
        const current = merged.get(rec.drug_name) ?? { score: 0, supporters: new Set<string>() };
        current.score += rec.confidence + (result.specialty_name === routing.lead_specialty ? 0.3 : 0);
        current.supporters.add(result.specialty_name);
        merged.set(rec.drug_name, current);
      }
    }
    const sorted = [...merged.entries()].sort((a, b) => b[1].score - a[1].score);
    const topDrugs = sorted.map((item) => item[0]);
    return [
      {
        plan_id: "plan_a",
        plan_name: "主专科优先方案",
        drugs: topDrugs.slice(0, 5),
        supporting_specialties: [...new Set(specialtyResults.map((item) => item.specialty_name))],
        rationale: "以主专科和高置信度药物为核心形成方案。",
        aggregate_score: 5,
      },
      {
        plan_id: "plan_b",
        plan_name: "多专科平衡方案",
        drugs: topDrugs.slice(0, 4),
        supporting_specialties: [...new Set(specialtyResults.map((item) => item.specialty_name))],
        rationale: "尽量保留多专科共同支持的药物。",
        aggregate_score: 4,
      },
      {
        plan_id: "plan_c",
        plan_name: "保守低风险方案",
        drugs: topDrugs.slice(0, 3),
        supporting_specialties: [...new Set(specialtyResults.map((item) => item.specialty_name))],
        rationale: "减少药物数量，形成保守方案。",
        aggregate_score: 3,
      },
    ];
  }
}

function evaluateRiskLevel(rule: any, labValue: number | null | undefined): string | null {
  if (labValue === null || labValue === undefined) {
    return null;
  }
  if (rule.threshold_type === "upper_bound") {
    if (labValue > Number(rule.high_risk_threshold?.value)) {
      return "high";
    }
    if (labValue > Number(rule.moderate_risk_threshold?.value)) {
      return "moderate";
    }
    return null;
  }
  if (rule.threshold_type === "range" || rule.threshold_type === "bidirectional") {
    const highLow = Number(rule.high_risk_threshold?.low);
    const highHigh = Number(rule.high_risk_threshold?.high);
    const modLow = Number(rule.moderate_risk_threshold?.low);
    const modHigh = Number(rule.moderate_risk_threshold?.high);
    if (labValue < highLow || labValue > highHigh) {
      return "high";
    }
    if (labValue < modLow || labValue > modHigh) {
      return "moderate";
    }
  }
  return null;
}

function runSafetyFallback(
  caseRecord: CaseRecord,
  candidatePlans: CandidatePlan[],
  specialtyResults: SpecialtyAgentResult[],
  fallbackReason?: string,
): SafetyResult {
  const triggeredRisks: Array<Record<string, unknown>> = [];
  for (const specialty of caseRecord.active_specialties) {
    const kb = loadSpecialtyKnowledge(specialty);
    for (const rule of kb.riskRules) {
      const labName = String(rule.lab_name);
      const level = evaluateRiskLevel(rule, caseRecord.key_labs[labName] ?? null);
      if (!level) {
        continue;
      }
      triggeredRisks.push({
        specialty_name: specialty,
        rule_id: rule.rule_id,
        lab_name: labName,
        lab_value: caseRecord.key_labs[labName] ?? null,
        risk_level: level,
        risk_message: rule.risk_message,
      });
    }
  }

  const avoidSet = new Set(
    specialtyResults.flatMap((item) =>
      item.avoid_or_low_priority_drugs.map((drug) => String((drug as any).drug_name).toLowerCase()),
    ),
  );

  const rankedPlans = candidatePlans
    .map((plan) => {
      const highRiskCount = triggeredRisks.filter((item) => item.risk_level === "high").length;
      const moderateRiskCount = triggeredRisks.filter((item) => item.risk_level === "moderate").length;
      const avoidPenalty = plan.drugs.filter((drug) => avoidSet.has(drug.toLowerCase())).length;
      const riskPenalty = highRiskCount * 3 + moderateRiskCount + avoidPenalty;
      const finalScore = plan.aggregate_score - riskPenalty;
      return {
        ...plan,
        risk_penalty: riskPenalty,
        final_score: finalScore,
      };
    })
    .sort((a, b) => b.final_score - a.final_score);

  const finalPlan = rankedPlans[0];
  return {
    final_plan: {
      plan_id: finalPlan.plan_id,
      plan_name: finalPlan.plan_name,
      drugs: finalPlan.drugs,
      supporting_specialties: finalPlan.supporting_specialties,
      rationale: finalPlan.rationale,
      aggregate_score: finalPlan.final_score,
    },
    ranked_plans: rankedPlans,
    triggered_risks: triggeredRisks,
    safety_summary: fallbackReason
      ? `Cursor 安全智能体调用失败，已回退到 risk_rules.json 规则筛查和排序：${fallbackReason}`
      : "安全智能体已基于 risk_rules.json 对候选方案做中高风险筛查和排序。",
    safety_review_source: "rule_fallback",
  };
}

async function runSafetyAgent(
  caseRecord: CaseRecord,
  candidatePlans: CandidatePlan[],
  specialtyResults: SpecialtyAgentResult[],
): Promise<SafetyResult> {
  const payload = {
    patient_info: caseRecord.patient_info,
    primary_diagnosis: caseRecord.primary_diagnosis,
    active_specialties: caseRecord.active_specialties,
    comorbidity_list: caseRecord.comorbidity_list,
    key_labs: caseRecord.key_labs,
    candidate_plans: candidatePlans,
    specialty_results: specialtyResults,
  };
  const prompt = buildJsonPrompt(
    "安全审核智能体",
    [
      "你需要像 MDT 安全审核成员一样复核候选方案。",
      "请基于病例关键检验值、共病、各专科风险提示、不建议药物和候选方案，识别触发风险、重排候选方案，并给出最终方案。",
      "注意：首 24 小时检验异常代表患者入院早期基线风险背景，不要把它直接归因于候选药物；请说明方案是否适配这些基线风险。",
      "final_plan 必须来自 ranked_plans 中的某一个候选方案。",
    ].join("\n"),
    payload,
    "{ final_plan: {plan_id:string, plan_name:string, drugs:string[], supporting_specialties:string[], rationale:string, aggregate_score:number}, ranked_plans: Record<string,unknown>[], triggered_risks: Record<string,unknown>[], safety_summary: string, safety_review_source?: string }",
  );

  try {
    const text = await runCursorAgent(prompt);
    const result = parseJsonText<SafetyResult>(text);
    return {
      ...result,
      safety_review_source: result.safety_review_source ?? "cursor_agent",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return runSafetyFallback(caseRecord, candidatePlans, specialtyResults, message);
  }
}

async function main() {
  const caseIndex = Number(getArg("--case-index", "0"));
  const hadmId = getArg("--hadm-id", "");
  const output = getArg("--output", "");

  const caseRecord = exportCaseBundle(caseIndex, hadmId);
  const routing = await runDiagnosisAgent(caseRecord);

  const specialtyResults: SpecialtyAgentResult[] = [];
  for (const specialty of routing.active_specialties) {
    const result = await runSpecialtyAgent(specialty, caseRecord, routing);
    specialtyResults.push(result);
  }

  const candidatePlans = await runCoordinationAgent(caseRecord, routing, specialtyResults);
  const safetyResult = await runSafetyAgent(caseRecord, candidatePlans, specialtyResults);

  const outputPath =
    output || path.join(OUTPUTS_DIR, `${caseRecord.patient_info.hadm_id}_cursor_dialogue.json`);
  writeJsonFile(outputPath, {
    case_record: caseRecord,
    routing,
    specialty_results: specialtyResults,
    candidate_plans: candidatePlans,
    safety_result: safetyResult,
    cursor_mode: "cloud_agents_rest_v0",
  });

  console.log(`病例 hadm_id=${caseRecord.patient_info.hadm_id}`);
  console.log(`唤起专科: ${routing.active_specialties.join(", ")}`);
  console.log(`主专科: ${routing.lead_specialty ?? "unknown"}`);
  console.log(`最终方案: ${safetyResult.final_plan.drugs.join(", ")}`);
  console.log(`输出文件: ${outputPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
