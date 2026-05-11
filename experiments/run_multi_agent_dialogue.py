from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.case_builder import CaseBuilder
from experiments.config import CursorSettings, ExperimentPaths, LLMSettings
from experiments.diagnosis_agent import DiagnosisAgent
from experiments.mdt_discussion_agent import MDTDiscussionAgent
from experiments.safety_agent import SafetyAgent
from experiments.schemas import DialogueMessage
from experiments.specialty_agent import SpecialtyAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行多专科对话式多智能体实验骨架")
    parser.add_argument("--case-index", type=int, default=0, help="从 multi_specialty_cases_v2.csv 中选第几个病例")
    parser.add_argument("--hadm-id", type=str, default="", help="直接指定 hadm_id")
    parser.add_argument("--output", type=str, default="", help="输出结果 JSON 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ExperimentPaths()
    paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    llm_settings = LLMSettings()
    cursor_settings = CursorSettings()

    builder = CaseBuilder(paths)
    case_record = (
        builder.build_case_by_hadm_id(args.hadm_id)
        if args.hadm_id
        else builder.build_case_by_index(args.case_index)
    )

    diagnosis_agent = DiagnosisAgent()
    specialty_agent = SpecialtyAgent(paths, llm_settings)
    mdt_agent = MDTDiscussionAgent()
    safety_agent = SafetyAgent(paths, llm_settings, cursor_settings)

    transcript: list[DialogueMessage] = []
    routing = diagnosis_agent.route(case_record)
    transcript.append(
        DialogueMessage(
            round_id=0,
            speaker="diagnosis_agent",
            message_type="routing",
            content=routing.to_dict(),
        )
    )

    specialty_results = []
    for specialty in routing.active_specialties:
        result = specialty_agent.run(specialty, case_record, routing)
        specialty_results.append(result)
        transcript.append(
            DialogueMessage(
                round_id=1,
                speaker=f"{specialty}_agent",
                message_type="proposal",
                content=result.to_dict(),
            )
        )

    mdt_result = mdt_agent.discuss(case_record, routing, specialty_results)
    for review in mdt_result.review_round:
        transcript.append(
            DialogueMessage(
                round_id=2,
                speaker=f"{review.reviewer_specialty}_agent",
                message_type="cross_review",
                content=review.to_dict(),
            )
        )

    candidate_plans = mdt_result.candidate_plans
    transcript.append(
        DialogueMessage(
            round_id=3,
            speaker="mdt_discussion",
            message_type="consensus_plans",
            content={
                "consensus_notes": mdt_result.consensus_notes,
                "plans": [plan.to_dict() for plan in candidate_plans],
            },
        )
    )

    safety_result = safety_agent.screen(case_record, candidate_plans, specialty_results)
    transcript.append(
        DialogueMessage(
            round_id=4,
            speaker="safety_agent",
            message_type="screening",
            content=safety_result.to_dict(),
        )
    )

    output = {
        "case_record": case_record.to_dict(),
        "routing": routing.to_dict(),
        "specialty_results": [item.to_dict() for item in specialty_results],
        "mdt_discussion": mdt_result.to_dict(),
        "candidate_plans": [item.to_dict() for item in candidate_plans],
        "safety_result": safety_result.to_dict(),
        "transcript": [item.to_dict() for item in transcript],
        "llm_enabled": llm_settings.enabled,
        "cursor_enabled": cursor_settings.enabled,
    }

    output_path = Path(args.output) if args.output else paths.outputs_dir / f"{case_record.patient_info.hadm_id}.json"
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"病例 hadm_id={case_record.patient_info.hadm_id}")
    print(f"唤起专科: {', '.join(routing.active_specialties)}")
    print(f"主专科: {routing.lead_specialty}")
    print(f"最终方案: {', '.join(safety_result.final_plan.drugs)}")
    print(f"结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
