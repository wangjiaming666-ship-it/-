import fs from "node:fs";
import path from "node:path";

import { parse } from "csv-parse/sync";

import { KNOWLEDGE_BASE_DIR } from "./config.js";
import { parsePipeList, readJsonFile } from "./utils.js";

export interface KnowledgeBaseEntry {
  specialty_name: string;
  folder_name: string;
  disease_catalog: string;
  drug_catalog: string;
  risk_rules: string;
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

function resolveKnowledgePath(rawPath: string, folderName: string): string {
  if (fs.existsSync(rawPath)) {
    return rawPath;
  }
  if (!path.isAbsolute(rawPath)) {
    const repoPath = path.join(KNOWLEDGE_BASE_DIR, "..", rawPath);
    if (fs.existsSync(repoPath)) {
      return repoPath;
    }
  }

  const fileName = path.win32.basename(rawPath);
  return path.join(KNOWLEDGE_BASE_DIR, folderName, fileName);
}

function normalizeSpecialtyName(value: string): string {
  const normalized = value.replace(/\uFEFF/g, "").trim();
  const compact = normalized.replace(/\s+/g, "");
  return SPECIALTY_ALIASES[compact] ?? normalized;
}

export class KnowledgeBaseIndex {
  private readonly rows: KnowledgeBaseEntry[];

  constructor() {
    this.rows = readCsv(path.join(KNOWLEDGE_BASE_DIR, "kb_index.csv")).map((row) => ({
      specialty_name: normalizeSpecialtyName(row.specialty_name ?? row["\uFEFFspecialty_name"] ?? ""),
      folder_name: row.folder_name,
      disease_catalog: resolveKnowledgePath(row.disease_catalog, row.folder_name),
      drug_catalog: resolveKnowledgePath(row.drug_catalog, row.folder_name),
      risk_rules: resolveKnowledgePath(row.risk_rules, row.folder_name),
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
  const riskRules = readJsonFile<Array<Record<string, unknown>>>(entry.risk_rules);

  const diagnosticKnowledge = diseaseCatalog.slice(0, 30).map((row) => ({
    disease_name: row.disease_name,
    aliases: parsePipeList(row.aliases),
    diagnostic_basis: row.diagnostic_basis,
    key_symptoms: parsePipeList(row.key_symptoms),
    key_labs_or_tests: parsePipeList(row.key_labs_or_tests),
    differential_diagnosis: parsePipeList(row.differential_diagnosis),
    reference_source: row.reference_source,
    reference_url: row.reference_url,
    agent_use: row.agent_use,
  }));
  const diseaseDirectedDrugs = drugCatalog
    .filter((row) => ["disease_directed_therapy", "risk_modifying_therapy"].includes(row.treatment_role))
    .slice(0, 30)
    .map((row) => ({
      standard_drug_name: row.standard_drug_name,
      aliases: parsePipeList(row.aliases),
      drug_class: row.drug_class,
      disease_context: parsePipeList(row.disease_context),
      treatment_role: row.treatment_role,
      order_category: row.order_category,
      mechanism_or_function: row.mechanism_or_function,
      major_cautions: row.major_cautions,
      reference_source: row.reference_source,
      reference_url: row.reference_url,
    }));
  const supportiveDrugs = drugCatalog
    .filter((row) =>
      ["supportive_or_symptomatic_therapy", "general_inpatient_medication"].includes(row.treatment_role),
    )
    .slice(0, 20)
    .map((row) => ({
      standard_drug_name: row.standard_drug_name,
      aliases: parsePipeList(row.aliases),
      drug_class: row.drug_class,
      treatment_role: row.treatment_role,
      order_category: row.order_category,
      mechanism_or_function: row.mechanism_or_function,
      major_cautions: row.major_cautions,
      reference_source: row.reference_source,
      reference_url: row.reference_url,
    }));
  const summarizedRiskRules = riskRules.slice(0, 8).map((rule) => ({
    rule_id: rule.rule_id,
    risk_target: rule.risk_target,
    related_treatments: rule.related_treatments,
    lab_name: rule.lab_name,
    threshold_type: rule.threshold_type,
    moderate_risk_threshold: rule.moderate_risk_threshold,
    high_risk_threshold: rule.high_risk_threshold,
    risk_message: rule.risk_message,
    action: rule.action,
    contraindication_or_caution: rule.contraindication_or_caution,
    monitoring_advice: rule.monitoring_advice,
    reference_source: rule.reference_source,
    reference_url: rule.reference_url,
  }));

  return {
    entry,
    diseaseCatalog,
    drugCatalog,
    riskRules,
    promptPayload: {
      specialty_name: specialtyName,
      knowledge_base_dir: entry.folder_name,
      diagnostic_knowledge: diagnosticKnowledge,
      drug_function_knowledge: {
        disease_directed_or_risk_modifying: diseaseDirectedDrugs,
        supportive_or_general: supportiveDrugs,
      },
      risk_rules: summarizedRiskRules,
    },
  };
}

export function extractAvoidDrugs(rows: Array<Record<string, string>>): string[] {
  const values = rows
    .filter((row) =>
      ["supportive_or_symptomatic_therapy", "general_inpatient_medication"].includes(row.treatment_role),
    )
    .flatMap((row) => [row.standard_drug_name, ...parsePipeList(row.aliases)])
    .filter(Boolean);
  return Array.from(new Set(values));
}
