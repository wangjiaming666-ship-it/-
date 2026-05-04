from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "evaluation" / "mdt_framework"
DEFAULT_FIGURE_DIR = ROOT_DIR / "figures" / "evaluation"


def configure_matplotlib() -> None:
    for font_name, font_path in [
        ("Microsoft YaHei", Path("C:/Windows/Fonts/msyh.ttc")),
        ("SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
        ("SimSun", Path("C:/Windows/Fonts/simsun.ttc")),
    ]:
        if font_path.exists():
            mpl.font_manager.fontManager.addfont(str(font_path))
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def normalize_drug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text)
    text = re.sub(r"\b(iv|po|tab|tablet|cap|capsule|syringe|inj|injection)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json_outputs(output_dir: Path, pattern: str) -> list[tuple[Path, dict[str, Any]]]:
    rows = []
    for path in sorted(output_dir.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            hadm_id = data.get("case_record", {}).get("patient_info", {}).get("hadm_id")
            final_plan = data.get("safety_result", {}).get("final_plan")
            if hadm_id and final_plan:
                rows.append((path, data))
        except Exception:  # noqa: BLE001
            continue
    return rows


def load_drug_roles(kb_dir: Path) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    for path in kb_dir.glob("*/drug_catalog.csv"):
        df = pd.read_csv(path, low_memory=False)
        for row in df.to_dict(orient="records"):
            drug = normalize_drug(row.get("drug_name"))
            if not drug:
                continue
            role = str(row.get("treatment_role") or row.get("drug_role") or "unknown")
            roles.setdefault(drug, set()).add(role)
    return roles


def load_real_prescriptions(prescription_path: Path, hadm_ids: set[str]) -> dict[str, set[str]]:
    result = {hadm_id: set() for hadm_id in hadm_ids}
    for chunk in pd.read_csv(
        prescription_path,
        usecols=["hadm_id", "drug_name"],
        dtype=str,
        chunksize=300_000,
        low_memory=False,
    ):
        chunk = chunk[chunk["hadm_id"].isin(hadm_ids)]
        if chunk.empty:
            continue
        for hadm_id, group in chunk.groupby("hadm_id"):
            result.setdefault(str(hadm_id), set()).update(
                normalize_drug(value) for value in group["drug_name"].dropna().tolist()
            )
    return result


def extract_final_drugs(data: dict[str, Any]) -> set[str]:
    final_plan = data.get("safety_result", {}).get("final_plan", {})
    return {normalize_drug(value) for value in final_plan.get("drugs", []) if normalize_drug(value)}


def extract_recommended_drugs(data: dict[str, Any]) -> set[str]:
    drugs = set(extract_final_drugs(data))
    for result in data.get("specialty_results", []):
        for item in result.get("recommended_drugs_topk", []):
            drug = normalize_drug(item.get("drug_name"))
            if drug:
                drugs.add(drug)
    return drugs


def extract_avoid_drugs(data: dict[str, Any]) -> set[str]:
    drugs = set()
    for result in data.get("specialty_results", []):
        for item in result.get("avoid_or_low_priority_drugs", []):
            drug = normalize_drug(item.get("drug_name"))
            if drug:
                drugs.add(drug)
    return drugs


def drug_roles(drugs: set[str], role_map: dict[str, set[str]]) -> set[str]:
    roles = set()
    for drug in drugs:
        roles.update(role_map.get(drug, {"unknown"}))
    return roles


def safe_ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def evaluate_case(
    path: Path,
    data: dict[str, Any],
    true_prescriptions: dict[str, set[str]],
    role_map: dict[str, set[str]],
) -> dict[str, Any]:
    hadm_id = str(data.get("case_record", {}).get("patient_info", {}).get("hadm_id", ""))
    final_drugs = extract_final_drugs(data)
    all_recommended = extract_recommended_drugs(data)
    true_drugs = true_prescriptions.get(hadm_id, set())
    avoid_drugs = extract_avoid_drugs(data)

    intersection = final_drugs & true_drugs
    union = final_drugs | true_drugs
    precision = safe_ratio(len(intersection), len(final_drugs))
    recall = safe_ratio(len(intersection), len(true_drugs))
    f1 = safe_ratio(2 * precision * recall, precision + recall)
    jaccard = safe_ratio(len(intersection), len(union))

    final_roles = drug_roles(final_drugs, role_map)
    true_roles = drug_roles(true_drugs, role_map)
    role_intersection = final_roles & true_roles
    role_coverage = safe_ratio(len(role_intersection), len(true_roles))
    role_precision = safe_ratio(len(role_intersection), len(final_roles))

    mdt = data.get("mdt_discussion", {})
    safety = data.get("safety_result", {})
    ranked_plans = safety.get("ranked_plans", [])
    triggered_risks = safety.get("triggered_risks", [])
    risk_adaptation_notes = sum(len(plan.get("plan_adaptation_notes", [])) for plan in ranked_plans)
    medication_reviews = sum(len(plan.get("medication_impact_review", [])) for plan in ranked_plans)
    final_avoid_overlap = final_drugs & avoid_drugs

    return {
        "file_name": path.name,
        "hadm_id": hadm_id,
        "active_specialty_count": len(data.get("routing", {}).get("active_specialties", [])),
        "final_drug_count": len(final_drugs),
        "true_prescription_count": len(true_drugs),
        "drug_overlap_count": len(intersection),
        "drug_precision": precision,
        "drug_recall": recall,
        "drug_f1": f1,
        "drug_jaccard": jaccard,
        "role_precision": role_precision,
        "role_coverage": role_coverage,
        "mdt_has_review_round": bool(mdt.get("review_round")),
        "mdt_review_count": len(mdt.get("review_round", [])),
        "mdt_candidate_plan_count": len(mdt.get("candidate_plans", data.get("candidate_plans", []))),
        "safety_triggered_risk_count": len(triggered_risks),
        "safety_has_context_review": any("medication_impact_review" in plan for plan in ranked_plans),
        "risk_adaptation_note_count": risk_adaptation_notes,
        "medication_impact_review_count": medication_reviews,
        "final_avoid_drug_overlap_count": len(final_avoid_overlap),
        "final_drugs": " | ".join(sorted(final_drugs)),
        "true_drugs_sample": " | ".join(sorted(list(true_drugs))[:20]),
        "final_roles": " | ".join(sorted(final_roles)),
        "true_roles": " | ".join(sorted(true_roles)),
    }


def plot_metric_summary(summary: pd.DataFrame, figure_dir: Path) -> Path:
    metrics = [
        ("药名Precision", summary.loc["mean", "drug_precision"]),
        ("药名Recall", summary.loc["mean", "drug_recall"]),
        ("药名F1", summary.loc["mean", "drug_f1"]),
        ("Jaccard", summary.loc["mean", "drug_jaccard"]),
        ("治疗角色Precision", summary.loc["mean", "role_precision"]),
        ("治疗角色覆盖", summary.loc["mean", "role_coverage"]),
    ]
    labels = [item[0] for item in metrics]
    values = [item[1] for item in metrics]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.plot(values, labels, color="#CBD5E1", linewidth=4, zorder=1)
    ax.scatter(values, labels, color="#2563EB", s=130, zorder=2)
    for value, label in zip(values, labels):
        ax.text(value + 0.015, label, f"{value:.2f}", va="center", fontsize=10)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("均值")
    ax.set_title("推荐药物与真实处方的一致性及治疗角色覆盖", fontsize=15, fontweight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    output_path = figure_dir / "01_alignment_metrics.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_alignment_comparison(case_df: pd.DataFrame, figure_dir: Path) -> Path:
    plot_df = case_df[["drug_f1", "role_coverage"]].copy()
    plot_df = plot_df.rename(columns={"drug_f1": "药名F1", "role_coverage": "治疗角色覆盖"})
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.boxplot(
        [plot_df["药名F1"], plot_df["治疗角色覆盖"]],
        labels=["药名一致性(F1)", "治疗角色覆盖率"],
        patch_artist=True,
        boxprops={"facecolor": "#DBEAFE", "color": "#2563EB"},
        medianprops={"color": "#DC2626", "linewidth": 2},
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("指标值")
    ax.set_title("药名一致性与治疗角色覆盖分布", fontsize=15, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    output_path = figure_dir / "02_name_vs_role_alignment.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评估 MDT 多智能体框架与真实处方的一致性。")
    parser.add_argument("--outputs-dir", type=Path, default=ROOT_DIR / "experiments" / "outputs")
    parser.add_argument("--pattern", type=str, default="*.json")
    parser.add_argument("--prescriptions", type=Path, default=ROOT_DIR / "cleaned_prescriptions.csv")
    parser.add_argument("--kb-dir", type=Path, default=ROOT_DIR / "knowledge_base")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.figure_dir.mkdir(parents=True, exist_ok=True)

    outputs = load_json_outputs(args.outputs_dir, args.pattern)
    if not outputs:
        raise FileNotFoundError(f"未找到 MDT 输出 JSON: {args.outputs_dir / args.pattern}")

    hadm_ids = {
        str(data.get("case_record", {}).get("patient_info", {}).get("hadm_id", ""))
        for _, data in outputs
    }
    hadm_ids.discard("")
    role_map = load_drug_roles(args.kb_dir)
    true_prescriptions = load_real_prescriptions(args.prescriptions, hadm_ids)

    rows = [evaluate_case(path, data, true_prescriptions, role_map) for path, data in outputs]
    case_df = pd.DataFrame(rows)
    numeric_cols = [
        "drug_precision",
        "drug_recall",
        "drug_f1",
        "drug_jaccard",
        "role_precision",
        "role_coverage",
        "active_specialty_count",
        "final_drug_count",
        "true_prescription_count",
        "mdt_review_count",
        "mdt_candidate_plan_count",
        "safety_triggered_risk_count",
        "risk_adaptation_note_count",
        "medication_impact_review_count",
        "final_avoid_drug_overlap_count",
    ]
    summary = case_df[numeric_cols].agg(["count", "mean", "median", "min", "max"]).round(4)

    case_path = args.output_dir / "case_level_alignment.csv"
    summary_path = args.output_dir / "summary_metrics.csv"
    case_df.to_csv(case_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, encoding="utf-8-sig")
    figures = [
        plot_metric_summary(summary, args.figure_dir),
        plot_alignment_comparison(case_df, args.figure_dir),
    ]

    print("MDT框架评估完成：")
    print(case_path)
    print(summary_path)
    for figure in figures:
        print(figure)


if __name__ == "__main__":
    main()
