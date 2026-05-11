from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from experiments.case_builder import CaseBuilder
from experiments.config import CursorSettings, ExperimentPaths
from experiments.cursor_client import CursorCloudAgentClient
from experiments.knowledge_base import KnowledgeBaseIndex, SpecialtyKnowledgeLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-chain Cursor MDT prescription generation.")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--workers", type=int, default=5)
    return parser.parse_args()


def sanitize_case_for_prompt(case_record: Any) -> dict[str, Any]:
    data = case_record.to_dict()
    raw_summary = dict(data.get("raw_case_summary", {}))
    # The current-admission prescription is the evaluation label and must not be visible
    # to the model when it generates recommendations.
    raw_summary.pop("drug_list", None)
    data["raw_case_summary"] = raw_summary
    return data


def build_knowledge_payload(paths: ExperimentPaths, specialties: list[str]) -> dict[str, Any]:
    loader = SpecialtyKnowledgeLoader(KnowledgeBaseIndex(paths))
    payload: dict[str, Any] = {}
    for specialty in specialties:
        try:
            knowledge = loader.build_prompt_payload(specialty)
        except Exception as exc:  # noqa: BLE001
            payload[specialty] = {"load_error": str(exc)}
            continue
        payload[specialty] = {
            "core_diseases": knowledge.get("core_diseases", [])[:12],
            "core_drugs": knowledge.get("core_drugs", [])[:16],
            "supportive_or_general": knowledge.get("supportive_or_general", [])[:12],
            "disease_drug_map": knowledge.get("disease_drug_map", [])[:18],
            "risk_rules": knowledge.get("risk_rules", [])[:10],
        }
    return payload


def build_prompt(case_record: Any, knowledge_payload: dict[str, Any]) -> str:
    payload = {
        "case_record_without_current_prescription": sanitize_case_for_prompt(case_record),
        "specialty_knowledge": knowledge_payload,
        "instructions": [
            "你要模拟完整多智能体 MDT 共病处方推荐链路，而不是只做安全审核。",
            "必须按以下链路推理：1) 诊断路由；2) 各专科智能体独立评估；3) MDT 交叉审阅；4) 生成多个候选处方；5) 安全审核；6) 输出最终完整处方。",
            "当前住院真实处方 drug_list 不在输入中，不能猜测或声称看到真实处方。",
            "最终处方应尽量完整，覆盖疾病直接治疗、风险控制、症状支持、护理/管路、预防、补液/溶媒/冲管、操作相关、营养电解质支持和需复核药物等层级。",
            "所有推荐必须来自病例诊断/共病/检验信息、专科知识库和 MDT 推理，不得引用当前病例真实处方。",
        ],
    }
    output_shape = {
        "routing": {
            "active_specialties": ["string"],
            "lead_specialty": "string",
            "specialty_related_diagnoses": {"specialty": ["diagnosis"]},
            "rationale": "string",
        },
        "specialty_results": [
            {
                "specialty_name": "string",
                "recommended_drugs_topk": [
                    {"rank": 1, "drug_name": "string", "confidence": 0.0, "reason": "string"}
                ],
                "recommendation_reasons": {"key": "string"},
                "risk_alerts": [],
                "avoid_or_low_priority_drugs": [{"drug_name": "string", "reason": "string"}],
                "overall_confidence": 0.0,
                "summary_reason": "string",
                "conversation_text": "string",
            }
        ],
        "mdt_discussion": {
            "review_round": [
                {
                    "reviewer_specialty": "string",
                    "accepted_drugs": ["string"],
                    "cautioned_drugs": ["string"],
                    "conflict_notes": ["string"],
                    "priority_comment": "string",
                }
            ],
            "consensus_notes": ["string"],
            "candidate_plans": [
                {
                    "plan_id": "string",
                    "plan_name": "string",
                    "drugs": ["string"],
                    "medication_layers": {
                        "disease_directed_therapy": ["string"],
                        "risk_modifying_therapy": ["string"],
                        "symptom_supportive_medication": ["string"],
                        "nursing_support_medication": ["string"],
                        "prophylaxis_prevention_medication": ["string"],
                        "fluid_diluent_flush_medication": ["string"],
                        "procedure_related_medication": ["string"],
                        "nutrition_electrolyte_medication": ["string"],
                        "requires_review": ["string"],
                    },
                    "supporting_specialties": ["string"],
                    "rationale": "string",
                    "aggregate_score": 0.0,
                }
            ],
        },
        "safety_result": {
            "final_plan": "CandidatePlan",
            "ranked_plans": [],
            "triggered_risks": [],
            "safety_summary": "string",
            "llm_safety_review": {"provider": "cursor_cloud_agent", "status": "completed"},
        },
        "transcript": [],
    }
    return "\n\n".join(
        [
            "你是一个由诊断路由、专科医生、MDT 协商和安全审核共同组成的多智能体处方推荐系统。",
            "请严格输出 JSON，不要输出 Markdown，不要输出额外解释。",
            "输出 JSON 结构必须包含以下顶层字段：routing, specialty_results, mdt_discussion, candidate_plans, safety_result, transcript。",
            f"输出结构参考：{json.dumps(output_shape, ensure_ascii=False)}",
            "输入数据如下：",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def normalize_candidate_plans(result: dict[str, Any]) -> list[dict[str, Any]]:
    plans = result.get("candidate_plans")
    if isinstance(plans, list):
        return plans
    mdt = result.get("mdt_discussion", {})
    if isinstance(mdt, dict) and isinstance(mdt.get("candidate_plans"), list):
        return mdt["candidate_plans"]
    return []


def run_one(index: int, output_dir: Path) -> dict[str, Any]:
    paths = ExperimentPaths()
    case_record = CaseBuilder(paths).build_case_by_index(index)
    client = CursorCloudAgentClient(CursorSettings())
    knowledge_payload = build_knowledge_payload(paths, case_record.active_specialties)
    result = client.run_json_prompt(build_prompt(case_record, knowledge_payload))
    result["candidate_plans"] = normalize_candidate_plans(result)
    result.setdefault("mdt_discussion", {}).setdefault("candidate_plans", result["candidate_plans"])
    output = {
        "case_record": case_record.to_dict(),
        "routing": result.get("routing", {}),
        "specialty_results": result.get("specialty_results", []),
        "mdt_discussion": result.get("mdt_discussion", {}),
        "candidate_plans": result.get("candidate_plans", []),
        "safety_result": result.get("safety_result", {}),
        "transcript": result.get("transcript", []),
        "cursor_enabled": True,
        "cursor_full_chain": True,
    }
    output_path = output_dir / f"test_case_{index + 1:03d}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"index": index, "path": str(output_path), "hadm_id": case_record.patient_info.hadm_id}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    indices = list(range(args.start_index, args.start_index + args.count))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_one, index, output_dir) for index in indices]
        for future in as_completed(futures):
            item = future.result()
            print(f"完成 case_index={item['index']} hadm_id={item['hadm_id']} -> {item['path']}", flush=True)


if __name__ == "__main__":
    main()
