from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.case_builder import CaseBuilder
from experiments.config import ExperimentPaths


def sanitize_json_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出单个病例为 Cursor SDK 可消费的 JSON")
    parser.add_argument("--case-index", type=int, default=0, help="病例索引")
    parser.add_argument("--hadm-id", type=str, default="", help="直接指定 hadm_id")
    parser.add_argument("--output", type=str, default="", help="输出路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ExperimentPaths()
    builder = CaseBuilder(paths)
    case_record = (
        builder.build_case_by_hadm_id(args.hadm_id)
        if args.hadm_id
        else builder.build_case_by_index(args.case_index)
    )

    output_path = (
        Path(args.output)
        if args.output
        else paths.outputs_dir / f"{case_record.patient_info.hadm_id}_case_bundle.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_json_value(case_record.to_dict())

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, allow_nan=False)

    print(str(output_path))


if __name__ == "__main__":
    main()
