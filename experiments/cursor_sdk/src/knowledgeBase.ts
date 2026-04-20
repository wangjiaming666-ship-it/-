import fs from "node:fs";

import { parse } from "csv-parse/sync";

import { KNOWLEDGE_BASE_DIR } from "./config.js";
import { parsePipeList, readJsonFile } from "./utils.js";

export interface KnowledgeBaseEntry {
  specialty_name: string;
  folder_name: string;
  disease_catalog: string;
  drug_catalog: string;
  lab_profile: string;
  risk_rules: string;
  disease_drug_map: string;
  example_cases: string;
}

const SPECIALTY_ALIASES: Record<string, string> = {
  心内: "心血管",
  心血管: "心血管",
  神经: "神经",
  呼吸: "呼吸",
  肾内: "肾内/泌尿",
  泌尿: "肾内/泌尿",
  肾内泌尿: "肾内/泌尿",
  "肾内/泌尿": "肾内/泌尿",
  内分泌: "内分泌/代谢",
  代谢: "内分泌/代谢",
  内分泌代谢: "内分泌/代谢",
  "内分泌/代谢": "内分泌/代谢",
  消化: "消化",
};

function readCsv(filePath: string): Array<Record<string, string>> {
  const content = fs.readFileSync(filePath, "utf-8");
  return parse(content, {
    columns: true,
    skip_empty_lines: true,
  }) as Array<Record<string, string>>;
}

function normalizeSpecialtyName(value: string): string {
  const normalized = value.replace(/\uFEFF/g, "").trim();
  const compact = normalized.replace(/\s+/g, "");
  return SPECIALTY_ALIASES[compact] ?? normalized;
}

function summarizeCaseExamples(exampleCases: Record<string, unknown>) {
  const singleExamples = Array.isArray(exampleCases.single_specialty_examples)
    ? exampleCases.single_specialty_examples
    : [];
  const multiExamples = Array.isArray(exampleCases.multi_specialty_examples)
    ? exampleCases.multi_specialty_examples
    : [];

  const pickSummary = (item: any) => {
    const caseSummary = item?.case_summary ?? {};
    return {
      hadm_id: item?.hadm_id ?? caseSummary?.hadm_id ?? "",
      primary_diagnosis: caseSummary?.primary_diagnosis ?? "",
      comorbidity_list: parsePipeList(caseSummary?.comorbidity_list).slice(0, 5),
      drug_list: parsePipeList(caseSummary?.drug_list).slice(0, 8),
      key_labs: {
        creatinine_24h: caseSummary?.creatinine_24h ?? null,
        bun_24h: caseSummary?.bun_24h ?? null,
        potassium_24h: caseSummary?.potassium_24h ?? null,
        sodium_24h: caseSummary?.sodium_24h ?? null,
        glucose_24h: caseSummary?.glucose_24h ?? null,
        inr_24h: caseSummary?.inr_24h ?? null,
        bilirubin_total_24h: caseSummary?.bilirubin_total_24h ?? null,
      },
    };
  };

  return {
    single_specialty_count: singleExamples.length,
    multi_specialty_count: multiExamples.length,
    single_specialty_examples: singleExamples.slice(0, 2).map(pickSummary),
    multi_specialty_examples: multiExamples.slice(0, 2).map(pickSummary),
  };
}

export class KnowledgeBaseIndex {
  private readonly rows: KnowledgeBaseEntry[];

  constructor() {
    this.rows = readCsv(`${KNOWLEDGE_BASE_DIR}\\kb_index.csv`).map((row) => ({
      specialty_name: normalizeSpecialtyName(row.specialty_name ?? row["\uFEFFspecialty_name"] ?? ""),
      folder_name: row.folder_name,
      disease_catalog: row.disease_catalog,
      drug_catalog: row.drug_catalog,
      lab_profile: row.lab_profile,
      risk_rules: row.risk_rules,
      disease_drug_map: row.disease_drug_map,
      example_cases: row.example_cases,
    }));
  }

  getEntry(specialtyName: string): KnowledgeBaseEntry {
    const normalizedName = normalizeSpecialtyName(specialtyName);
    const entry = this.rows.find((row) => row.specialty_name === normalizedName);
    if (!entry) {
      throw new Error(`未找到专科知识库索引: ${specialtyName}`);
    }
    return entry;
  }
}

export function loadSpecialtyKnowledge(specialtyName: string) {
  const kbIndex = new KnowledgeBaseIndex();
  const entry = kbIndex.getEntry(specialtyName);
  const diseaseCatalog = readCsv(entry.disease_catalog);
  const drugCatalog = readCsv(entry.drug_catalog);
  const diseaseDrugMap = readCsv(entry.disease_drug_map);
  const riskRules = readJsonFile<Array<Record<string, unknown>>>(entry.risk_rules);
  const exampleCases = readJsonFile<Record<string, unknown>>(entry.example_cases);

  const coreDiseases = diseaseCatalog
    .filter((row) => row.disease_role === "核心病种")
    .slice(0, 10)
    .map((row) => ({
      diagnosis_name: row.diagnosis_name,
      frequency: row.frequency,
      notes: row.notes,
    }));
  const coreDrugs = drugCatalog
    .filter((row) => row.drug_role === "核心治疗药")
    .slice(0, 10)
    .map((row) => ({
      drug_name: row.drug_name,
      frequency: row.frequency,
      notes: row.notes,
    }));
  const usableMap = diseaseDrugMap
    .filter((row) => row.mapping_quality === "可直接使用")
    .slice(0, 12)
    .map((row) => ({
      diagnosis_name: row.diagnosis_name,
      recommended_drugs: parsePipeList(row.recommended_drugs).slice(0, 6),
      avoid_or_low_priority_drugs: parsePipeList(row.avoid_or_low_priority_drugs).slice(0, 6),
      evidence_source: row.evidence_source,
    }));
  const summarizedRiskRules = riskRules.slice(0, 8).map((rule) => ({
    rule_id: rule.rule_id,
    lab_name: rule.lab_name,
    threshold_type: rule.threshold_type,
    moderate_risk_threshold: rule.moderate_risk_threshold,
    high_risk_threshold: rule.high_risk_threshold,
    risk_message: rule.risk_message,
    action: rule.action,
  }));
  const summarizedExamples = summarizeCaseExamples(exampleCases);

  return {
    entry,
    diseaseCatalog,
    drugCatalog,
    diseaseDrugMap,
    riskRules,
    exampleCases,
    promptPayload: {
      specialty_name: specialtyName,
      knowledge_base_dir: entry.folder_name,
      core_diseases: coreDiseases,
      core_drugs: coreDrugs,
      disease_drug_map: usableMap,
      risk_rules: summarizedRiskRules,
      example_cases: summarizedExamples,
    },
  };
}

export function extractAvoidDrugs(rows: Array<Record<string, string>>): string[] {
  const values = rows.flatMap((row) => parsePipeList(row.avoid_or_low_priority_drugs));
  return Array.from(new Set(values));
}
