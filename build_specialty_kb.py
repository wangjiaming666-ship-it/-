from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
KB_DIR = BASE_DIR / "knowledge_base"
REFERENCE_DIR = KB_DIR / "reference"

SPECIALTY_DIRS = {
    "心血管": "cardiology",
    "神经": "neurology",
    "呼吸": "respiratory",
    "肾内/泌尿": "nephrology",
    "内分泌/代谢": "endocrinology",
    "消化": "gastroenterology",
}

DISEASE_REFERENCE_FILE = REFERENCE_DIR / "disease_diagnosis_reference.csv"
SPECIALTY_DRUG_REFERENCE_FILE = REFERENCE_DIR / "specialty_drug_reference.csv"
SUPPORTIVE_DRUG_REFERENCE_FILE = REFERENCE_DIR / "supportive_drug_reference.csv"
TREATMENT_RISK_REFERENCE_FILE = REFERENCE_DIR / "treatment_risk_reference.csv"

TREATMENT_ROLE_LABELS = {
    "disease_directed_therapy": "疾病直接治疗",
    "risk_modifying_therapy": "风险控制治疗",
    "supportive_or_symptomatic_therapy": "支持/对症服务药物",
    "general_inpatient_medication": "住院通用服务药物",
}


def read_csv_flexible(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False).fillna("")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path} ({last_error})") from last_error


def ensure_dirs() -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    for folder in SPECIALTY_DIRS.values():
        (KB_DIR / folder).mkdir(parents=True, exist_ok=True)


def validate_inputs() -> None:
    required_files = [
        DISEASE_REFERENCE_FILE,
        SPECIALTY_DRUG_REFERENCE_FILE,
        SUPPORTIVE_DRUG_REFERENCE_FILE,
        TREATMENT_RISK_REFERENCE_FILE,
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError("缺少知识库参考表: " + "；".join(missing))


def clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def parse_optional_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_threshold(row: pd.Series, prefix: str, threshold_type: str) -> dict[str, Any]:
    unit = clean_text(row.get("unit"))
    if threshold_type in {"range", "bidirectional"}:
        threshold: dict[str, Any] = {"unit": unit}
        low = parse_optional_float(row.get(f"{prefix}_low"))
        high = parse_optional_float(row.get(f"{prefix}_high"))
        if low is not None:
            threshold["low"] = low
        if high is not None:
            threshold["high"] = high
        threshold[f"outside_range_is_{prefix}_risk"] = True
        return threshold

    threshold = {"unit": unit}
    value = parse_optional_float(row.get(f"{prefix}_value"))
    operator = clean_text(row.get(f"{prefix}_operator"))
    if value is not None:
        threshold["value"] = value
    if operator:
        threshold["operator"] = operator
    return threshold


def infer_drug_class(row: pd.Series) -> str:
    explicit_class = clean_text(row.get("drug_class"))
    if explicit_class:
        return explicit_class
    explicit_category = clean_text(row.get("supportive_category"))
    if explicit_category:
        return explicit_category

    note = clean_text(row.get("reference_note")).lower()
    context = clean_text(row.get("disease_context")).lower()
    combined = f"{note} {context}"
    class_rules = [
        ("antiplatelet", "抗血小板药"),
        ("anticoagulant", "抗凝药"),
        ("beta blocker", "β受体阻滞剂"),
        ("ace inhibitor", "ACEI 类药物"),
        ("statin", "他汀类调脂药"),
        ("diuretic", "利尿剂"),
        ("antiepileptic", "抗癫痫药"),
        ("bronchodilator", "支气管扩张药"),
        ("corticosteroid", "糖皮质激素"),
        ("insulin", "胰岛素类降糖药"),
        ("proton pump", "质子泵抑制剂"),
        ("antibiotic", "抗感染药"),
        ("laxative", "通便药"),
    ]
    for keyword, label in class_rules:
        if keyword in combined:
            return label
    return "公开药物功能知识"


def infer_order_category(row: pd.Series, role: str) -> str:
    category = clean_text(row.get("supportive_category"))
    if category:
        if category in {"fluid_flush_diluent", "diluent", "line_flush", "fluid_resuscitation"}:
            return "fluid_diluent_flush"
        if category in {"vaccine", "stress_ulcer_prophylaxis"}:
            return "prophylaxis_prevention"
        if category in {"procedure_support", "skin_or_line_care"}:
            return "procedure_or_nursing"
        if category in {"nutrition_support", "vitamin_support", "anemia_support"}:
            return "nutrition_support"
        if category in {"electrolyte_repletion", "acid_base_support", "glycemic_support"}:
            return "nutrition_electrolyte_metabolic"
        if category in {"rescue_reversal", "emergency_rescue"}:
            return "emergency_rescue"
        return "symptom_support"
    if role == "disease_directed_therapy":
        return "disease_directed"
    if role == "risk_modifying_therapy":
        return "risk_modifying"
    if role == "general_inpatient_medication":
        return "general_inpatient_service"
    return "symptom_support"


def build_disease_catalog() -> None:
    reference = read_csv_flexible(DISEASE_REFERENCE_FILE)
    for specialty_name, folder in SPECIALTY_DIRS.items():
        rows = []
        for _, item in reference[reference["specialty_name"] == specialty_name].iterrows():
            disease_name = clean_text(item.get("disease_name"))
            rows.append(
                {
                    "specialty_name": specialty_name,
                    "disease_name": disease_name,
                    "diagnosis_name": disease_name,
                    "aliases": clean_text(item.get("aliases")),
                    "diagnostic_basis": clean_text(item.get("diagnostic_basis")),
                    "key_symptoms": clean_text(item.get("key_symptoms")),
                    "key_labs_or_tests": clean_text(item.get("key_labs_or_tests")),
                    "differential_diagnosis": clean_text(item.get("differential_diagnosis")),
                    "diagnosis_relevance": "primary_specialty_disease",
                    "diagnosis_relevance_label": "专科疾病诊断知识",
                    "reference_source": clean_text(item.get("reference_source")),
                    "reference_url": clean_text(item.get("reference_url")),
                    "agent_use": clean_text(item.get("agent_use")),
                }
            )
        pd.DataFrame(rows).to_csv(
            KB_DIR / folder / "disease_catalog.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_drug_catalog() -> None:
    specialty_reference = read_csv_flexible(SPECIALTY_DRUG_REFERENCE_FILE)
    supportive_reference = read_csv_flexible(SUPPORTIVE_DRUG_REFERENCE_FILE)
    for specialty_name, folder in SPECIALTY_DIRS.items():
        rows: list[dict[str, Any]] = []
        specialty_rows = specialty_reference[
            specialty_reference["specialty_name"] == specialty_name
        ]
        for _, item in specialty_rows.iterrows():
            role = clean_text(item.get("treatment_role")) or "disease_directed_therapy"
            drug_name = clean_text(item.get("standard_drug_name"))
            rows.append(
                {
                    "specialty_name": specialty_name,
                    "standard_drug_name": drug_name,
                    "drug_name": drug_name,
                    "aliases": clean_text(item.get("aliases")),
                    "drug_class": infer_drug_class(item),
                    "disease_context": clean_text(item.get("disease_context")),
                    "treatment_role": role,
                    "treatment_role_label": TREATMENT_ROLE_LABELS.get(role, role),
                    "order_category": infer_order_category(item, role),
                    "mechanism_or_function": clean_text(item.get("mechanism_or_function"))
                    or clean_text(item.get("reference_note")),
                    "major_cautions": clean_text(item.get("major_cautions")),
                    "reference_source": clean_text(item.get("reference_source")),
                    "reference_url": clean_text(item.get("reference_url")),
                    "agent_use": "作为公开药物功能知识进入候选药物解释，仍需结合诊断和风险规则复核",
                }
            )

        for _, item in supportive_reference.iterrows():
            role = clean_text(item.get("treatment_role")) or "supportive_or_symptomatic_therapy"
            drug_name = clean_text(item.get("standard_drug_name"))
            rows.append(
                {
                    "specialty_name": specialty_name,
                    "standard_drug_name": drug_name,
                    "drug_name": drug_name,
                    "aliases": clean_text(item.get("aliases")),
                    "drug_class": infer_drug_class(item),
                    "disease_context": "supportive care|general inpatient care",
                    "treatment_role": role,
                    "treatment_role_label": TREATMENT_ROLE_LABELS.get(role, role),
                    "order_category": infer_order_category(item, role),
                    "mechanism_or_function": clean_text(item.get("mechanism_or_function"))
                    or clean_text(item.get("reference_note")),
                    "major_cautions": clean_text(item.get("major_cautions")),
                    "reference_source": clean_text(item.get("reference_source")),
                    "reference_url": clean_text(item.get("reference_url")),
                    "agent_use": "作为支持治疗或住院通用药物功能知识，不单独作为疾病直接治疗证据",
                }
            )

        pd.DataFrame(rows).drop_duplicates(
            subset=["specialty_name", "standard_drug_name", "treatment_role"]
        ).to_csv(
            KB_DIR / folder / "drug_catalog.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_risk_rules() -> None:
    reference = read_csv_flexible(TREATMENT_RISK_REFERENCE_FILE)
    for specialty_name, folder in SPECIALTY_DIRS.items():
        rules = []
        for _, item in reference[reference["specialty_name"] == specialty_name].iterrows():
            threshold_type = clean_text(item.get("threshold_type"))
            rules.append(
                {
                    "rule_id": clean_text(item.get("rule_id")),
                    "risk_target": clean_text(item.get("risk_target")),
                    "related_treatments": clean_text(item.get("related_treatments")),
                    "lab_name": clean_text(item.get("lab_name")),
                    "lab_purpose": clean_text(item.get("lab_purpose")),
                    "threshold_type": threshold_type,
                    "moderate_risk_threshold": build_threshold(item, "moderate", threshold_type),
                    "high_risk_threshold": build_threshold(item, "high", threshold_type),
                    "risk_message": clean_text(item.get("risk_message")),
                    "action": {
                        "moderate_risk": clean_text(item.get("moderate_action")),
                        "high_risk": clean_text(item.get("high_action")),
                    },
                    "contraindication_or_caution": clean_text(
                        item.get("contraindication_or_caution")
                    ),
                    "monitoring_advice": clean_text(item.get("monitoring_advice")),
                    "reference_source": clean_text(item.get("reference_source")),
                    "reference_url": clean_text(item.get("reference_url")),
                    "threshold_basis": clean_text(item.get("threshold_basis")),
                }
            )
        with open(KB_DIR / folder / "risk_rules.json", "w", encoding="utf-8") as file:
            json.dump(rules, file, ensure_ascii=False, indent=2)


def build_kb_index() -> None:
    rows = []
    for specialty_name, folder in SPECIALTY_DIRS.items():
        base = KB_DIR / folder
        rows.append(
            {
                "specialty_name": specialty_name,
                "folder_name": folder,
                "disease_catalog": str(base / "disease_catalog.csv"),
                "drug_catalog": str(base / "drug_catalog.csv"),
                "risk_rules": str(base / "risk_rules.json"),
            }
        )
    pd.DataFrame(rows).to_csv(KB_DIR / "kb_index.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    ensure_dirs()
    validate_inputs()
    build_disease_catalog()
    build_drug_catalog()
    build_risk_rules()
    build_kb_index()
    print("六专科三类核心知识库构建完成。")
    print(f"输出目录: {KB_DIR}")


if __name__ == "__main__":
    main()
