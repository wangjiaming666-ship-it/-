from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
KB_DIR = BASE_DIR / "knowledge_base"

SPECIALTY_DIRS = {
    "心血管": "cardiology",
    "神经": "neurology",
    "呼吸": "respiratory",
    "肾内/泌尿": "nephrology",
    "内分泌/代谢": "endocrinology",
    "消化": "gastroenterology",
}

LAB_COLUMNS = [
    "creatinine_24h",
    "bun_24h",
    "potassium_24h",
    "sodium_24h",
    "glucose_24h",
    "inr_24h",
    "bilirubin_total_24h",
]

DRUG_CATALOG_TOP_N = 20
DRUG_CATALOG_EXCLUDED_ROLES: set[str] = set()

DIAGNOSIS_RELEVANCE_LABELS = {
    "primary_specialty_disease": "专科主要疾病",
    "specialty_related_condition": "专科相关状态",
    "cross_specialty_comorbidity": "跨专科合并症",
    "low_relevance_or_noise": "低相关或噪声",
}

TREATMENT_ROLE_LABELS = {
    "disease_directed_therapy": "疾病直接治疗",
    "risk_modifying_therapy": "风险控制治疗",
    "supportive_or_symptomatic_therapy": "支持/对症治疗",
    "general_inpatient_medication": "住院通用药物",
    "low_priority_or_uncertain": "低优先级或不确定",
}

SUPPORTIVE_DRUGS = {
    "acetaminophen": "支持治疗药",
    "acetaminophen iv": "支持治疗药",
    "senna": "支持治疗药",
    "docusate sodium": "支持治疗药",
    "ondansetron": "支持治疗药",
    "hydromorphone (dilaudid)": "支持治疗药",
    "oxycodone (immediate release)": "支持治疗药",
    "lorazepam": "支持治疗药",
    "ibuprofen": "支持治疗药",
    "ketorolac": "支持治疗药",
    "morphine sulfate": "支持治疗药",
    "bisacodyl": "支持治疗药",
    "simethicone": "支持治疗药",
    "diphenhydramine": "支持治疗药",
}

GENERIC_AUXILIARY_KEYWORDS = [
    "sodium chloride",
    "dextrose",
    "ringer",
    "flush",
    "mini bag plus",
    "sterile water",
    "influenza vaccine",
    "vaccine",
    "potassium chloride replacement",
    "bottle",
    "d5 ",
    "d10",
]

EXACT_GENERIC_DRUGS = {
    "ns",
    "sw",
}

BACKGROUND_DISEASE_KEYWORDS = [
    "accidental puncture",
    "laceration",
    "postprocedural",
    "other procedure",
    "complicating",
    "complication",
    "malfunction",
]

SPECIALTY_CORE_DISEASE_KEYWORDS = {
    "心血管": [
        "heart",
        "card",
        "coronary",
        "myocard",
        "atrial",
        "ventric",
        "mitral",
        "aortic",
        "tricuspid",
        "arrhythm",
        "tachy",
        "hypertension",
        "hypertensive",
        "heart failure",
        "angina",
        "infarction",
        "ischemi",
        "embolism",
        "thrombosis",
        "endocarditis",
        "pulmonary embol",
        "aneurysm",
    ],
    "神经": [
        "brain",
        "cerebr",
        "intracran",
        "migraine",
        "epilep",
        "seizure",
        "mening",
        "encephal",
        "neurop",
        "parkinson",
        "sclerosis",
        "hydrocephal",
        "alzheimer",
        "dementia",
        "palsy",
        "myelit",
        "myelopathy",
        "neuralgia",
        "stroke",
        "headache",
        "sleep apnea",
        "polyneuro",
        "cord syndrome",
    ],
    "呼吸": [
        "respirat",
        "pulmon",
        "pneumon",
        "asthma",
        "copd",
        "bronch",
        "lung",
        "pleur",
        "emphysema",
        "airway",
        "pharyng",
        "sinus",
        "epiglott",
        "nasopharyng",
        "sleep apnea",
        "asbestosis",
    ],
    "肾内/泌尿": [
        "kidney",
        "renal",
        "neph",
        "urinary",
        "ureter",
        "bladder",
        "prostat",
        "pyelo",
        "cystitis",
        "hydroneph",
        "calcul",
        "hematuria",
        "dialysis",
        "genitourinary",
        "penis",
        "testis",
        "phimosis",
        "prepuce",
    ],
    "内分泌/代谢": [
        "diabetes",
        "thyroid",
        "obesity",
        "lipid",
        "cholesterol",
        "metab",
        "adrenal",
        "pituitar",
        "glucose",
        "hypo-osmol",
        "hyponatr",
        "hypokal",
        "vitamin",
        "nutrition",
        "malnutrition",
        "phosphorus",
        "ketoacidosis",
        "porphyria",
    ],
    "消化": [
        "gastro",
        "reflux",
        "liver",
        "hepatic",
        "append",
        "bowel",
        "bile",
        "pancrea",
        "colitis",
        "crohn",
        "ulcer",
        "rect",
        "anal",
        "peritone",
        "stomach",
        "constipation",
        "cholecyst",
        "ileus",
        "intestin",
        "duoden",
        "gastric",
        "esophag",
        "gallbladder",
        "hernia",
    ],
}

SPECIALTY_EXCLUDE_DISEASE_KEYWORDS = {
    "心血管": [
        "intracerebral",
        "subarachnoid",
        "cerebral aneurysm",
        "infection",
        "portal vein",
        "cerebrovascular",
        "aphasia",
        "brain",
    ],
    "神经": ["septicemia", "septicemias", "streptococcal sore throat"],
    "呼吸": ["viral meningitis", "avian flu virus"],
    "肾内/泌尿": [
        "uterus",
        "uterine",
        "ovary",
        "ovarian",
        "vaginal",
        "endometriosis",
        "menstruation",
        "amenorrhea",
        "salping",
        "vulva",
        "bartholin",
        "breast",
        "pelvic",
        "cervix",
        "cervical",
        "endometrial",
        "infertility",
        "dysmenorrhea",
        "vaginitis",
        "vulvitis",
        "female genital",
        "hematosalpinx",
        "corpus luteum",
        "hyperstimulation of ovaries",
        "intrauterine",
    ],
    "内分泌/代谢": [],
    "消化": ["herpes", "salivary gland"],
}

SPECIALTY_CORE_DRUG_KEYWORDS = {
    "心血管": [
        "aspirin",
        "warfarin",
        "heparin",
        "heparin sodium",
        "apixaban",
        "enoxaparin",
        "alteplase",
        "metoprolol",
        "amiodarone",
        "carvedilol",
        "lisinopril",
        "captopril",
        "hydralazine",
        "labetalol",
        "furosemide",
        "spironolactone",
        "atorvastatin",
        "digoxin",
        "hydrochlorothiazide",
        "valsartan",
        "torsemide",
        "diltiazem",
        "ticagrelor",
        "clopidogrel",
    ],
    "神经": [
        "levetiracetam",
        "phenytoin",
        "lamotrig",
        "lacosamide",
        "clobazam",
        "gabapentin",
        "baclofen",
        "donepezil",
        "ropinirole",
        "carbidopa",
        "amantadine",
        "midazolam",
        "diazepam",
        "pregabalin",
        "oxcarbazepine",
        "zonisamide",
        "topiramate",
    ],
    "呼吸": [
        "albuterol",
        "ipratropium",
        "tiotropium",
        "prednisone",
        "methylpred",
        "fluticasone",
        "acetylcysteine",
        "guaifenesin",
        "azithromycin",
        "benzonatate",
        "fluticasone-salmeterol",
        "umeclidin",
        "levalbuterol",
        "methylprednisolone",
    ],
    "肾内/泌尿": [
        "phenazopyridine",
        "tamsulosin",
        "finasteride",
        "heparin (hemodialysis)",
        "ferric gluconate",
        "neutra-phos",
        "furosemide",
        "ceftriaxone",
        "gentamicin",
        "gentamicin sulfate",
        "neutra-phos",
        "calcium carbonate",
        "labetalol",
        "nifedipine",
        "amiloride",
        "doxercalciferol",
        "calcitriol",
        "tramadol",
        "lidocaine jelly",
    ],
    "内分泌/代谢": [
        "insulin",
        "levothyroxine",
        "hydrocortisone",
        "desmopressin",
        "vitamin d",
        "cyanocobalamin",
        "calcium carbonate",
        "methimazole",
        "propranolol",
        "atenolol",
        "cholestyramine",
        "sodium bicarbonate",
        "prednisone",
        "methylprednisolone",
    ],
    "消化": [
        "pantoprazole",
        "omeprazole",
        "metronidazole",
        "acetylcysteine",
        "creon",
        "lactulose",
        "rifaximin",
        "ciprofloxacin",
        "ceftriaxone",
        "infliximab",
        "mesalamine",
        "budesonide",
        "hydrocortisone",
        "methylprednisolone",
        "cholestyramine",
        "polyethylene glycol",
        "ursodiol",
    ],
}

RISK_RULES = {
    "心血管": [
        {
            "rule_id": "cardiology_potassium_risk",
            "lab_name": "potassium_24h",
            "lab_purpose": "评估电解质紊乱导致的心律失常风险",
            "threshold_type": "range",
            "moderate_risk_threshold": {
                "low": 3.5,
                "high": 5.0,
                "unit": "mmol/L",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 3.0,
                "high": 5.5,
                "unit": "mmol/L",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "钾离子明显异常时，心律失常、传导阻滞和药物诱发心电不稳定风险上升。",
            "action": {
                "moderate_risk": "对影响电解质或心律的候选药物降权，并提示复核补钾或降钾需要。",
                "high_risk": "将相关方案标记为高风险，不作为优先推荐，建议先纠正电解质后再决策。",
            },
            "threshold_basis": "结合心血管专科样本分布与临床常用参考范围设定。",
        },
        {
            "rule_id": "cardiology_inr_risk",
            "lab_name": "inr_24h",
            "lab_purpose": "评估抗凝相关出血风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 1.5, "operator": ">", "unit": ""},
            "high_risk_threshold": {"value": 2.0, "operator": ">", "unit": ""},
            "risk_message": "INR 升高提示凝血功能异常，抗凝、抗血小板或侵袭性操作相关方案的出血风险增加。",
            "action": {
                "moderate_risk": "对抗凝和联用抗血小板方案降权，并提示人工复核。",
                "high_risk": "暂停优先推荐强化抗凝方案，标记为高出血风险病例。",
            },
            "threshold_basis": "参考心血管病例 INR 分布和临床凝血风险经验阈值。",
        },
    ],
    "神经": [
        {
            "rule_id": "neurology_inr_risk",
            "lab_name": "inr_24h",
            "lab_purpose": "评估颅内出血及神经系统出血扩展风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 1.5, "operator": ">", "unit": ""},
            "high_risk_threshold": {"value": 2.0, "operator": ">", "unit": ""},
            "risk_message": "INR 升高时，颅内出血扩展或侵袭性神经操作相关出血风险增加。",
            "action": {
                "moderate_risk": "对抗凝、抗血小板及侵袭性治疗相关方案降权。",
                "high_risk": "将病例标记为高出血风险，暂停优先推荐相关高风险方案。",
            },
            "threshold_basis": "结合神经专科病例分布和神经系统出血风险控制经验阈值。",
        },
        {
            "rule_id": "neurology_sodium_risk",
            "lab_name": "sodium_24h",
            "lab_purpose": "评估意识状态、癫痫阈值及脑水肿相关风险",
            "threshold_type": "range",
            "moderate_risk_threshold": {
                "low": 135,
                "high": 145,
                "unit": "mmol/L",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 130,
                "high": 150,
                "unit": "mmol/L",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "钠离子异常可能诱发意识障碍、癫痫发作阈值改变或脑水肿风险上升。",
            "action": {
                "moderate_risk": "增加风险提示，降低可能加重电解质紊乱方案的优先级。",
                "high_risk": "将病例标记为高风险，建议先纠正钠异常后再进行方案排序。",
            },
            "threshold_basis": "参考神经专科常用电解质安全范围并结合样本四分位数。",
        },
    ],
    "呼吸": [
        {
            "rule_id": "respiratory_potassium_risk",
            "lab_name": "potassium_24h",
            "lab_purpose": "评估电解质异常对呼吸肌功能及支持治疗安全性的影响",
            "threshold_type": "range",
            "moderate_risk_threshold": {
                "low": 3.5,
                "high": 5.0,
                "unit": "mmol/L",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 3.0,
                "high": 5.5,
                "unit": "mmol/L",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "钾异常可能影响呼吸肌收缩、心肺联合稳定性及支持治疗安全性。",
            "action": {
                "moderate_risk": "增加监测提示，并降低可能加重电解质紊乱方案的优先级。",
                "high_risk": "将病例标记为高风险，优先建议纠正电解质后再推荐强化治疗方案。",
            },
            "threshold_basis": "参考呼吸专科样本分布与临床常用电解质安全范围。",
        },
        {
            "rule_id": "respiratory_glucose_risk",
            "lab_name": "glucose_24h",
            "lab_purpose": "评估感染、激素治疗及代谢失衡风险",
            "threshold_type": "bidirectional",
            "moderate_risk_threshold": {
                "low": 70,
                "high": 180,
                "unit": "mg/dL",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 54,
                "high": 250,
                "unit": "mg/dL",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "血糖过高或过低均会增加呼吸系统感染控制和全身代谢稳定风险，尤其在激素治疗场景下更明显。",
            "action": {
                "moderate_risk": "对增加糖代谢负担的方案降权，并提示复核血糖管理。",
                "high_risk": "标记为高代谢风险病例，暂停优先推荐高糖代谢负担方案。",
            },
            "threshold_basis": "参考住院常用血糖管理阈值，并结合呼吸专科样本中位数与上四分位数。",
        },
    ],
    "肾内/泌尿": [
        {
            "rule_id": "nephrology_creatinine_risk",
            "lab_name": "creatinine_24h",
            "lab_purpose": "评估肾功能受损及药物蓄积风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 1.5, "operator": ">=", "unit": "mg/dL"},
            "high_risk_threshold": {"value": 2.5, "operator": ">=", "unit": "mg/dL"},
            "risk_message": "肌酐升高提示肾小球滤过下降，肾毒性药物和需肾排泄药物的不良反应风险增加。",
            "action": {
                "moderate_risk": "降低潜在肾毒性药物优先级，并提示考虑剂量调整。",
                "high_risk": "将相关方案标记为高风险，优先避免肾毒性或需大量肾排泄的药物组合。",
            },
            "threshold_basis": "结合肾内专科肌酐分布（P75 约 1.8）和临床常用肾功能风险分层阈值。",
        },
        {
            "rule_id": "nephrology_bun_risk",
            "lab_name": "bun_24h",
            "lab_purpose": "评估肾前性或肾性损伤及代谢负荷风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 25, "operator": ">=", "unit": "mg/dL"},
            "high_risk_threshold": {"value": 40, "operator": ">=", "unit": "mg/dL"},
            "risk_message": "尿素氮升高提示肾功能或分解代谢负荷升高，联合高肌酐时需提高用药谨慎度。",
            "action": {
                "moderate_risk": "增加风险提示，降低高代谢负担方案优先级。",
                "high_risk": "标记为高风险病例，建议优先保留更保守、更易监测的治疗方案。",
            },
            "threshold_basis": "参考肾内样本中位数与上四分位数，并结合临床常用 BUN 风险分层。",
        },
        {
            "rule_id": "nephrology_potassium_risk",
            "lab_name": "potassium_24h",
            "lab_purpose": "评估肾功能受损背景下的高钾或低钾并发症风险",
            "threshold_type": "range",
            "moderate_risk_threshold": {
                "low": 3.5,
                "high": 5.0,
                "unit": "mmol/L",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 3.0,
                "high": 5.5,
                "unit": "mmol/L",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "肾内病例中的钾异常更容易提示致命性心律失常和电解质管理失败风险。",
            "action": {
                "moderate_risk": "对影响电解质平衡方案做额外审查，降低其排序分数。",
                "high_risk": "将病例标记为高风险，优先建议先纠正钾异常后再进行方案推荐。",
            },
            "threshold_basis": "参考肾内专科样本分布和临床电解质风险控制经验。",
        },
    ],
    "内分泌/代谢": [
        {
            "rule_id": "endocrinology_glucose_risk",
            "lab_name": "glucose_24h",
            "lab_purpose": "评估高血糖、低血糖及代谢失衡风险",
            "threshold_type": "bidirectional",
            "moderate_risk_threshold": {
                "low": 70,
                "high": 180,
                "unit": "mg/dL",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 54,
                "high": 250,
                "unit": "mg/dL",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "血糖显著偏离目标范围时，提示低血糖事件、酮症酸中毒或感染相关代谢失衡风险增加。",
            "action": {
                "moderate_risk": "调整降糖相关方案优先级，并提示复核血糖监测频率。",
                "high_risk": "将病例标记为高代谢风险，暂停优先推荐可能进一步加重波动的方案。",
            },
            "threshold_basis": "参考内分泌专科样本中位数与住院血糖管理常用阈值。",
        },
        {
            "rule_id": "endocrinology_sodium_risk",
            "lab_name": "sodium_24h",
            "lab_purpose": "评估代谢紊乱相关水电解质失衡风险",
            "threshold_type": "range",
            "moderate_risk_threshold": {
                "low": 135,
                "high": 145,
                "unit": "mmol/L",
                "outside_range_is_moderate_risk": True,
            },
            "high_risk_threshold": {
                "low": 130,
                "high": 150,
                "unit": "mmol/L",
                "outside_range_is_high_risk": True,
            },
            "risk_message": "明显低钠或高钠提示内分泌代谢性水电解质失衡，可能影响降糖与补液策略安全性。",
            "action": {
                "moderate_risk": "对强化补液和快速纠正方案降权，提示人工复核。",
                "high_risk": "标记为高风险病例，建议先处理水钠紊乱后再排序推荐方案。",
            },
            "threshold_basis": "参考内分泌代谢患者常用电解质管理阈值。",
        },
    ],
    "消化": [
        {
            "rule_id": "gastroenterology_bilirubin_risk",
            "lab_name": "bilirubin_total_24h",
            "lab_purpose": "评估肝胆代谢受损与胆汁淤积风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 2.0, "operator": ">", "unit": "mg/dL"},
            "high_risk_threshold": {"value": 3.0, "operator": ">", "unit": "mg/dL"},
            "risk_message": "总胆红素升高提示肝胆代谢负荷增加，可能影响肝代谢药物的安全性和耐受性。",
            "action": {
                "moderate_risk": "降低肝代谢负担较重药物的优先级，并提示复核肝胆状态。",
                "high_risk": "将病例标记为高肝胆风险，优先避免高肝毒性和高肝代谢负担组合。",
            },
            "threshold_basis": "结合消化专科样本分布（P75 约 1.8）和常用胆红素风险阈值设定。",
        },
        {
            "rule_id": "gastroenterology_inr_risk",
            "lab_name": "inr_24h",
            "lab_purpose": "评估肝合成功能受损及消化道出血风险",
            "threshold_type": "upper_bound",
            "moderate_risk_threshold": {"value": 1.5, "operator": ">", "unit": ""},
            "high_risk_threshold": {"value": 2.0, "operator": ">", "unit": ""},
            "risk_message": "INR 升高可能提示肝合成功能下降或凝血异常，消化道出血相关风险增加。",
            "action": {
                "moderate_risk": "对抗凝、侵袭性操作相关或易致出血方案降权。",
                "high_risk": "将病例标记为高出血风险，暂停优先推荐相关高风险方案。",
            },
            "threshold_basis": "参考消化专科病例 INR 分布与常用肝病凝血风险阈值。",
        },
    ],
}

REQUIRED_INPUTS = [
    "single_specialty_cases.csv",
    "multi_specialty_cases_v2.csv",
    "cleaned_diagnosis_specialty_detail_6.csv",
    "cleaned_prescriptions.csv",
    "specialty_top_diagnoses_clean.csv",
    "cohort_first24h_labs.csv",
]


def ensure_dirs() -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    for folder in SPECIALTY_DIRS.values():
        (KB_DIR / folder).mkdir(parents=True, exist_ok=True)


def validate_inputs() -> None:
    missing = [name for name in REQUIRED_INPUTS if not (BASE_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(
            "缺少以下输入文件，请先导出后再运行脚本:\n" + "\n".join(missing)
        )


def read_csv_flexible(file_name: str, usecols: Iterable[str] | None = None) -> pd.DataFrame:
    path = BASE_DIR / file_name
    encodings = ["utf-8-sig", "utf-8", "gb18030"]
    last_error = None
    for encoding in encodings:
        try:
            header = pd.read_csv(path, encoding=encoding, nrows=0)
            available_cols = list(header.columns)
            selected_cols = available_cols if usecols is None else [
                col for col in usecols if col in available_cols
            ]
            return pd.read_csv(
                path,
                encoding=encoding,
                usecols=selected_cols,
                dtype=str,
                low_memory=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件 {path}: {last_error}") from last_error


def safe_read_csv(file_name: str, usecols: Iterable[str] | None = None) -> pd.DataFrame | None:
    path = BASE_DIR / file_name
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        df = read_csv_flexible(file_name, usecols=usecols)
        if df.empty:
            return None
        return df
    except Exception:  # noqa: BLE001
        return None


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def contains_any(text: str, keywords: list[str]) -> bool:
    normalized = str(text).strip().lower()
    return any(keyword in normalized for keyword in keywords)


def review_diagnosis(specialty_name: str, diagnosis_name: str) -> tuple[int, str, str, str, str, str]:
    normalized = str(diagnosis_name).strip().lower()
    if contains_any(normalized, SPECIALTY_EXCLUDE_DISEASE_KEYWORDS.get(specialty_name, [])):
        return (
            0,
            "应剔除项",
            "明显跨专科或无助于专科知识库，已自动剔除",
            "low_relevance_or_noise",
            "exclude_keyword",
            "仅保留追溯，不进入专科诊断评估和推荐依据",
        )
    if contains_any(normalized, BACKGROUND_DISEASE_KEYWORDS):
        return (
            0,
            "背景共病",
            "术后/并发症/过程性疾病，降级为背景共病",
            "specialty_related_condition",
            "background_keyword",
            "用于解释病例复杂度和风险，不作为主要疾病推荐依据",
        )
    if contains_any(normalized, SPECIALTY_CORE_DISEASE_KEYWORDS.get(specialty_name, [])):
        return (
            1,
            "核心病种",
            "命中专科核心病种关键词",
            "primary_specialty_disease",
            "specialty_keyword",
            "作为专科诊断评估的主要依据",
        )
    return (
        0,
        "背景共病",
        "未命中明显专科核心关键词，保留为背景共病",
        "cross_specialty_comorbidity",
        "frequency_only",
        "提示可能存在跨专科合并症，进入 MDT 协商时供其他专科复核",
    )


def review_drug(specialty_name: str, drug_name: str) -> tuple[int, str, str, str, str, str, str]:
    normalized = str(drug_name).strip().lower()
    if normalized in SUPPORTIVE_DRUGS:
        return (
            0,
            SUPPORTIVE_DRUGS[normalized],
            "降级保留",
            "住院常见支持治疗药",
            "supportive_or_symptomatic_therapy",
            "supportive_drug_list",
            "用于对症或支持治疗，不作为疾病直接治疗证据",
        )
    if normalized in EXACT_GENERIC_DRUGS or contains_any(normalized, GENERIC_AUXILIARY_KEYWORDS):
        return (
            0,
            "通用辅助药",
            "降级保留",
            "通用液体/溶媒/辅助项",
            "general_inpatient_medication",
            "generic_medication_rule",
            "住院通用药物或溶媒，不作为专科治疗证据",
        )
    if contains_any(normalized, SPECIALTY_CORE_DRUG_KEYWORDS.get(specialty_name, [])):
        role = "risk_modifying_therapy" if contains_any(
            normalized,
            ["warfarin", "heparin", "apixaban", "enoxaparin", "insulin", "furosemide", "metoprolol", "labetalol"],
        ) else "disease_directed_therapy"
        return (
            1,
            "核心治疗药",
            "保留",
            "命中专科核心药物关键词",
            role,
            "specialty_drug_keyword",
            "可作为专科建议候选药物，但需结合诊断和安全规则复核",
        )
    return (
        0,
        "支持治疗药",
        "降级保留",
        "未命中专科核心药关键词，暂按支持治疗药保留",
        "low_priority_or_uncertain",
        "frequency_only",
        "仅作为真实世界用药候选证据，需人工或 MDT 复核",
    )


def build_disease_catalog() -> None:
    top_dx = read_csv_flexible(
        "specialty_top_diagnoses_clean.csv",
        usecols=["specialty_group", "diagnosis_name", "freq"],
    )
    if "freq" in top_dx.columns:
        top_dx["freq"] = to_numeric(top_dx["freq"])

    for specialty_name, folder in SPECIALTY_DIRS.items():
        sub = top_dx[top_dx["specialty_group"] == specialty_name].copy()
        if sub.empty:
            continue
        sub["specialty_name"] = specialty_name
        review = sub["diagnosis_name"].apply(lambda x: review_diagnosis(specialty_name, x))
        sub["is_core_disease"] = review.apply(lambda x: x[0])
        sub["disease_role"] = review.apply(lambda x: x[1])
        sub["diagnosis_relevance"] = review.apply(lambda x: x[3])
        sub["diagnosis_relevance_label"] = sub["diagnosis_relevance"].map(DIAGNOSIS_RELEVANCE_LABELS)
        sub["diagnosis_evidence_basis"] = review.apply(lambda x: x[4])
        sub["agent_use"] = review.apply(lambda x: x[5])
        sub["review_status"] = sub["disease_role"].map(
            {
                "核心病种": "保留",
                "背景共病": "降级保留",
                "应剔除项": "已剔除",
            }
        )
        sub["notes"] = review.apply(lambda x: x[2])
        removed = sub[sub["disease_role"] == "应剔除项"].copy()
        if not removed.empty:
            removed.rename(columns={"freq": "frequency"})[
                [
                    "specialty_name",
                    "diagnosis_name",
                    "frequency",
                    "is_core_disease",
                    "disease_role",
                    "diagnosis_relevance",
                    "diagnosis_relevance_label",
                    "diagnosis_evidence_basis",
                    "agent_use",
                    "review_status",
                    "notes",
                ]
            ].to_csv(
                KB_DIR / folder / "excluded_disease_catalog.csv",
                index=False,
                encoding="utf-8-sig",
            )
        output = sub.rename(columns={"freq": "frequency"})[
            [
                "specialty_name",
                "diagnosis_name",
                "frequency",
                "is_core_disease",
                "review_status",
                "notes",
            ]
        ]
        sub.rename(columns={"freq": "frequency"})[
            [
                "specialty_name",
                "diagnosis_name",
                "frequency",
                "is_core_disease",
                "disease_role",
                "diagnosis_relevance",
                "diagnosis_relevance_label",
                "diagnosis_evidence_basis",
                "agent_use",
                "review_status",
                "notes",
            ]
        ].to_csv(
            KB_DIR / folder / "disease_catalog.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_drug_catalog() -> None:
    single_cases = read_csv_flexible(
        "single_specialty_cases.csv",
        usecols=["subject_id", "hadm_id", "specialty_group"],
    )
    prescriptions = read_csv_flexible(
        "cleaned_prescriptions.csv",
        usecols=["subject_id", "hadm_id", "drug_name"],
    )
    top_drugs = (
        single_cases.merge(
            prescriptions,
            on=["subject_id", "hadm_id"],
            how="inner",
        )
        .dropna(subset=["drug_name"])
        .groupby(["specialty_group", "drug_name"])
        .size()
        .reset_index(name="freq")
    )
    top_drugs["freq"] = to_numeric(top_drugs["freq"])
    top_drugs = top_drugs.sort_values(
        by=["specialty_group", "freq", "drug_name"],
        ascending=[True, False, True],
    )

    for specialty_name, folder in SPECIALTY_DIRS.items():
        sub = top_drugs[top_drugs["specialty_group"] == specialty_name].copy()
        if sub.empty:
            continue
        sub["specialty_name"] = specialty_name
        review = sub["drug_name"].apply(lambda x: review_drug(specialty_name, x))
        sub["is_core_drug"] = review.apply(lambda x: x[0])
        sub["drug_role"] = review.apply(lambda x: x[1])
        sub["review_status"] = review.apply(lambda x: x[2])
        sub["notes"] = review.apply(lambda x: x[3])
        sub["treatment_role"] = review.apply(lambda x: x[4])
        sub["treatment_role_label"] = sub["treatment_role"].map(TREATMENT_ROLE_LABELS)
        sub["treatment_evidence_basis"] = review.apply(lambda x: x[5])
        sub["agent_use"] = review.apply(lambda x: x[6])
        sub = sub[~sub["drug_role"].isin(DRUG_CATALOG_EXCLUDED_ROLES)].head(DRUG_CATALOG_TOP_N)
        sub.rename(columns={"freq": "frequency"})[
            [
                "specialty_name",
                "drug_name",
                "frequency",
                "is_core_drug",
                "drug_role",
                "treatment_role",
                "treatment_role_label",
                "treatment_evidence_basis",
                "agent_use",
                "review_status",
                "notes",
            ]
        ].to_csv(
            KB_DIR / folder / "drug_catalog.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_lab_profile() -> None:
    single_cases = read_csv_flexible(
        "single_specialty_cases.csv",
        usecols=["subject_id", "hadm_id", "specialty_group"],
    )
    labs = read_csv_flexible(
        "cohort_first24h_labs.csv",
        usecols=["subject_id", "hadm_id", *LAB_COLUMNS],
    )
    merged = single_cases.merge(labs, on=["subject_id", "hadm_id"], how="inner")
    for lab_col in LAB_COLUMNS:
        if lab_col in merged.columns:
            merged[lab_col] = to_numeric(merged[lab_col])

    for specialty_name, folder in SPECIALTY_DIRS.items():
        sub = merged[merged["specialty_group"] == specialty_name].copy()
        if sub.empty:
            continue
        rows = []
        for lab_col in LAB_COLUMNS:
            if lab_col not in sub.columns:
                continue
            values = sub[lab_col].dropna()
            rows.append(
                {
                    "specialty_name": specialty_name,
                    "lab_name": lab_col,
                    "n_non_null": int(values.shape[0]),
                    "mean": round(values.mean(), 4) if not values.empty else None,
                    "median": round(values.median(), 4) if not values.empty else None,
                    "p25": round(values.quantile(0.25), 4) if not values.empty else None,
                    "p75": round(values.quantile(0.75), 4) if not values.empty else None,
                }
            )
        pd.DataFrame(rows).to_csv(
            KB_DIR / folder / "lab_profile.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_all_lab_profile() -> None:
    all_labs = safe_read_csv(
        "cohort_first24h_labs_all_long.csv",
        usecols=[
            "subject_id",
            "hadm_id",
            "itemid",
            "lab_label",
            "fluid",
            "category",
            "unit",
            "lab_record_count",
            "min_valuenum",
            "mean_valuenum",
            "max_valuenum",
        ],
    )
    if all_labs is None:
        return

    single_cases = read_csv_flexible(
        "single_specialty_cases.csv",
        usecols=["subject_id", "hadm_id", "specialty_group"],
    )
    merged = single_cases.merge(all_labs, on=["subject_id", "hadm_id"], how="inner")
    if merged.empty:
        return

    for value_col in ["lab_record_count", "min_valuenum", "mean_valuenum", "max_valuenum"]:
        if value_col in merged.columns:
            merged[value_col] = to_numeric(merged[value_col])

    for specialty_name, folder in SPECIALTY_DIRS.items():
        sub = merged[merged["specialty_group"] == specialty_name].copy()
        if sub.empty:
            continue
        grouped = (
            sub.groupby(["itemid", "lab_label", "fluid", "category", "unit"], dropna=False)
            .agg(
                case_count=("hadm_id", "nunique"),
                raw_lab_record_count=("lab_record_count", "sum"),
                min_value=("min_valuenum", "min"),
                mean_value=("mean_valuenum", "mean"),
                max_value=("max_valuenum", "max"),
            )
            .reset_index()
        )
        total_cases = single_cases[single_cases["specialty_group"] == specialty_name]["hadm_id"].nunique()
        grouped["coverage_pct"] = (
            grouped["case_count"] * 100.0 / total_cases if total_cases else 0
        )
        grouped["specialty_name"] = specialty_name
        grouped = grouped.sort_values(
            ["coverage_pct", "case_count", "lab_label"],
            ascending=[False, False, True],
        )
        grouped[
            [
                "specialty_name",
                "itemid",
                "lab_label",
                "fluid",
                "category",
                "unit",
                "case_count",
                "coverage_pct",
                "raw_lab_record_count",
                "min_value",
                "mean_value",
                "max_value",
            ]
        ].to_csv(
            KB_DIR / folder / "lab_profile_all.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_risk_rules() -> None:
    for specialty_name, folder in SPECIALTY_DIRS.items():
        with open(KB_DIR / folder / "risk_rules.json", "w", encoding="utf-8") as file:
            json.dump(RISK_RULES.get(specialty_name, []), file, ensure_ascii=False, indent=2)


def build_disease_drug_map() -> None:
    single_cases = read_csv_flexible(
        "single_specialty_cases.csv",
        usecols=["subject_id", "hadm_id", "specialty_group"],
    ).drop_duplicates()
    diagnoses = read_csv_flexible(
        "cleaned_diagnosis_specialty_detail_6.csv",
        usecols=["subject_id", "hadm_id", "specialty_group", "long_title"],
    ).rename(columns={"long_title": "diagnosis_name"})
    prescriptions = read_csv_flexible(
        "cleaned_prescriptions.csv",
        usecols=["subject_id", "hadm_id", "drug_name"],
    )

    merged = (
        single_cases.merge(
            diagnoses,
            on=["subject_id", "hadm_id", "specialty_group"],
            how="inner",
        )
        .merge(
            prescriptions,
            on=["subject_id", "hadm_id"],
            how="inner",
        )
        .dropna(subset=["diagnosis_name", "drug_name"])
    )

    disease_review = {
        (specialty, diagnosis): review_diagnosis(specialty, diagnosis)
        for specialty, diagnosis in merged[["specialty_group", "diagnosis_name"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    }
    drug_review = {
        (specialty, drug): review_drug(specialty, drug)
        for specialty, drug in merged[["specialty_group", "drug_name"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    }

    counts = (
        merged.groupby(["specialty_group", "diagnosis_name", "drug_name"])
        .size()
        .reset_index(name="cooccurrence")
    )
    counts["cooccurrence"] = to_numeric(counts["cooccurrence"])
    counts = counts.sort_values(
        by=["specialty_group", "diagnosis_name", "cooccurrence", "drug_name"],
        ascending=[True, True, False, True],
    )

    for specialty_name, folder in SPECIALTY_DIRS.items():
        sub = counts[counts["specialty_group"] == specialty_name].copy()
        if sub.empty:
            continue
        rows = []
        for diagnosis_name, group in sub.groupby("diagnosis_name", sort=False):
            disease_role = disease_review.get((specialty_name, diagnosis_name), (0, "背景共病", ""))[1]
            diagnosis_relevance = disease_review.get(
                (specialty_name, diagnosis_name),
                (0, "背景共病", "", "cross_specialty_comorbidity"),
            )[3]
            if disease_role == "应剔除项":
                continue
            if disease_role != "核心病种":
                rows.append(
                    {
                        "specialty_name": specialty_name,
                        "diagnosis_name": diagnosis_name,
                        "diagnosis_relevance": diagnosis_relevance,
                        "recommended_drugs": "",
                        "candidate_drug_pairs": "",
                        "avoid_or_low_priority_drugs": "",
                        "evidence_source": "single_specialty_cooccurrence",
                        "top_drug_evidence": "",
                        "mapping_quality": "仅用于诊断评估",
                        "evidence_interpretation": "共现仅提示病例背景或跨专科合并症，不作为治疗因果证据",
                        "notes": "该诊断不是本专科主要疾病，可用于诊断评估和 MDT 协商背景",
                    }
                )
                continue
            group = group.copy()
            group["drug_review_status"] = group["drug_name"].apply(
                lambda x: drug_review.get((specialty_name, x), (0, "支持治疗药", "降级保留", ""))[2]
            )
            group["drug_role"] = group["drug_name"].apply(
                lambda x: drug_review.get((specialty_name, x), (0, "支持治疗药", "", ""))[1]
            )
            group["treatment_role"] = group["drug_name"].apply(
                lambda x: drug_review.get((specialty_name, x), (0, "", "", "", "low_priority_or_uncertain"))[4]
            )
            kept_group = group[
                group["treatment_role"].isin(["disease_directed_therapy", "risk_modifying_therapy"])
            ].head(5)
            low_priority_group = group[
                ~group["treatment_role"].isin(["disease_directed_therapy", "risk_modifying_therapy"])
            ].head(5)
            recommended_drugs = " | ".join(kept_group["drug_name"].astype(str).tolist())
            low_priority_drugs = " | ".join(low_priority_group["drug_name"].astype(str).tolist())
            evidence = " | ".join(
                f"{row.drug_name}({int(row.cooccurrence)})" for row in kept_group.itertuples()
            )
            treatment_roles = " | ".join(
                f"{row.drug_name}:{row.treatment_role}" for row in kept_group.itertuples()
            )
            mapping_quality = "候选证据充分" if recommended_drugs else "仅保留低优先级方案"
            notes = (
                "已优先保留疾病直接治疗或风险控制药物，支持/通用药物移入低优先级"
                if low_priority_drugs and recommended_drugs
                else "当前未识别到明确核心治疗药，仅保留低优先级方案供参考"
            )
            rows.append(
                {
                    "specialty_name": specialty_name,
                    "diagnosis_name": diagnosis_name,
                    "diagnosis_relevance": diagnosis_relevance,
                    "recommended_drugs": recommended_drugs,
                    "candidate_drug_pairs": " | ".join(kept_group["drug_name"].astype(str).tolist()[:2]),
                    "avoid_or_low_priority_drugs": low_priority_drugs,
                    "evidence_source": "single_specialty_cooccurrence",
                    "top_drug_evidence": evidence,
                    "treatment_role_evidence": treatment_roles,
                    "mapping_quality": mapping_quality,
                    "evidence_interpretation": "单专科住院共现可作为真实世界候选证据，不代表治疗因果或临床指南推荐",
                    "notes": notes,
                }
            )

        pd.DataFrame(rows).to_csv(
            KB_DIR / folder / "disease_drug_map.csv",
            index=False,
            encoding="utf-8-sig",
        )


def build_example_cases() -> None:
    single_cases = read_csv_flexible(
        "single_specialty_cases.csv",
        usecols=["subject_id", "hadm_id", "specialty_group"],
    )
    multi_cases = read_csv_flexible(
        "multi_specialty_cases_v2.csv",
        usecols=["subject_id", "hadm_id", "specialty_cnt", "specialty_list"],
    )
    case_summary = safe_read_csv("case_summary.csv")
    if case_summary is not None and "hadm_id" in case_summary.columns:
        case_summary = case_summary.drop_duplicates(subset=["hadm_id"]).copy()
        case_summary["hadm_id"] = case_summary["hadm_id"].astype(str)

    for specialty_name, folder in SPECIALTY_DIRS.items():
        output = {
            "specialty_name": specialty_name,
            "single_specialty_examples": [],
            "multi_specialty_examples": [],
        }

        single_sub = single_cases[single_cases["specialty_group"] == specialty_name].head(10)
        for _, row in single_sub.iterrows():
            item = {
                "subject_id": row.get("subject_id"),
                "hadm_id": row.get("hadm_id"),
                "specialty_group": row.get("specialty_group"),
            }
            if case_summary is not None:
                matched = case_summary[case_summary["hadm_id"] == str(row.get("hadm_id"))]
                if not matched.empty:
                    item["case_summary"] = matched.iloc[0].to_dict()
            output["single_specialty_examples"].append(item)

        mask = multi_cases["specialty_list"].fillna("").str.contains(specialty_name, regex=False)
        multi_sub = multi_cases[mask].head(10)
        for _, row in multi_sub.iterrows():
            item = {
                "subject_id": row.get("subject_id"),
                "hadm_id": row.get("hadm_id"),
                "specialty_cnt": row.get("specialty_cnt"),
                "specialty_list": row.get("specialty_list"),
            }
            if case_summary is not None:
                matched = case_summary[case_summary["hadm_id"] == str(row.get("hadm_id"))]
                if not matched.empty:
                    item["case_summary"] = matched.iloc[0].to_dict()
            output["multi_specialty_examples"].append(item)

        with open(KB_DIR / folder / "example_cases.json", "w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)


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
                "lab_profile": str(base / "lab_profile.csv"),
                "lab_profile_all": str(base / "lab_profile_all.csv"),
                "risk_rules": str(base / "risk_rules.json"),
                "disease_drug_map": str(base / "disease_drug_map.csv"),
                "example_cases": str(base / "example_cases.json"),
            }
        )
    pd.DataFrame(rows).to_csv(KB_DIR / "kb_index.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    ensure_dirs()
    validate_inputs()
    build_disease_catalog()
    build_drug_catalog()
    build_lab_profile()
    build_all_lab_profile()
    build_risk_rules()
    build_disease_drug_map()
    build_example_cases()
    build_kb_index()
    print("六专科知识库初版构建完成。")
    print(f"输出目录: {KB_DIR}")


if __name__ == "__main__":
    main()
