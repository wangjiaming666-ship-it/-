from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
INPUT_JSON = ROOT / "experiments" / "outputs" / "cloud_mdt_case_0.json"
OUTPUT_DIR = ROOT / "figures" / "mdt_cases"


def configure_matplotlib() -> None:
    for font_name, font_path in [
        ("Microsoft YaHei", Path("C:/Windows/Fonts/msyh.ttc")),
        ("SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
        ("SimSun", Path("C:/Windows/Fonts/simsun.ttc")),
    ]:
        if font_path.exists():
            mpl.font_manager.fontManager.addfont(str(font_path))
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def wrap_text(value: object, width: int = 18) -> str:
    return "\n".join(
        textwrap.wrap(str(value), width=width, break_long_words=False, replace_whitespace=False)
    )


def draw_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    color: str,
    face: str,
    fs: float = 10,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=face,
        edgecolor=color,
        linewidth=2,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=12, fontweight="bold", color=color)
    ax.text(x + 0.018, y + h - 0.08, body, ha="left", va="top", fontsize=fs, color="#111827", linespacing=1.35)


def draw_arrow(ax, x1: float, y1: float, x2: float, y2: float, color: str = "#64748B") -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=2,
            color=color,
        )
    )


def main() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(INPUT_JSON, "r", encoding="utf-8") as file:
        data = json.load(file)

    case = data["case_record"]
    routing = data["routing"]
    specialty_results = data["specialty_results"]
    plans = data["candidate_plans"]
    safety = data["safety_result"]
    final_plan = safety["final_plan"]
    risks = safety.get("triggered_risks", [])

    fig, ax = plt.subplots(figsize=(18, 10.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title("cloud_mdt_case_0 多智能体诊断流程与结果", fontsize=22, fontweight="bold", pad=18)

    patient = case["patient_info"]
    labs = case.get("key_labs", {})
    case_body = (
        f"subject_id: {patient['subject_id']}\n"
        f"hadm_id: {patient['hadm_id']}\n"
        f"性别/年龄: {patient.get('gender')} / {patient.get('age')}\n"
        f"主诊断:\n{wrap_text(case['primary_diagnosis'], 24)}\n"
        f"关键检验: Cr {labs.get('creatinine_24h')}, K {labs.get('potassium_24h')}, INR {labs.get('inr_24h')}"
    )
    draw_box(ax, 0.03, 0.67, 0.19, 0.23, "① 病例输入", case_body, "#2563EB", "#EFF6FF", 9.2)

    route_body = (
        f"唤起专科: {'、'.join(routing['active_specialties'])}\n"
        f"初始主专科: {routing['lead_specialty']}\n"
        f"依据: {wrap_text(routing['rationale'], 18)}"
    )
    draw_box(ax, 0.27, 0.67, 0.19, 0.23, "② 初始诊断路由", route_body, "#059669", "#ECFDF5", 9.2)
    draw_arrow(ax, 0.22, 0.785, 0.27, 0.785)

    for idx, result in enumerate(specialty_results[:2]):
        y = [0.70, 0.39][idx]
        color = ["#EA580C", "#2563EB"][idx]
        face = ["#FFF7ED", "#EFF6FF"][idx]
        specialty = result["specialty_name"]
        diagnoses = routing["specialty_related_diagnoses"].get(specialty, [])[:2]
        drugs = [item["drug_name"] for item in result["recommended_drugs_topk"][:3]]
        body = (
            f"相关诊断数: {len(routing['specialty_related_diagnoses'].get(specialty, []))}\n"
            + "代表诊断:\n- "
            + "\n- ".join(wrap_text(item, 24) for item in diagnoses)
            + f"\n\nTop建议:\n{wrap_text(', '.join(drugs), 32)}\n"
            + f"低优先级提示: {len(result.get('avoid_or_low_priority_drugs', []))} 条\n"
            + f"风险提醒: {len(result.get('risk_alerts', []))} 条"
        )
        draw_box(ax, 0.50, y, 0.23, 0.24, f"③ {specialty}专科智能体", body, color, face, 8.2)
        draw_arrow(ax, 0.46, 0.785, 0.50, y + 0.13, color)

    plan_lines = []
    for plan in plans:
        plan_lines.append(
            f"{plan['plan_id']}：{plan['plan_name']}\n"
            f"得分 {plan.get('aggregate_score', 0):.2f}｜药物 {len(plan['drugs'])} 个"
        )
    draw_box(
        ax,
        0.77,
        0.59,
        0.20,
        0.30,
        "④ 候选方案商议/排序",
        "\n".join(plan_lines),
        "#7C3AED",
        "#FAF5FF",
        8.8,
    )
    draw_arrow(ax, 0.73, 0.80, 0.77, 0.76, "#7C3AED")
    draw_arrow(ax, 0.73, 0.51, 0.77, 0.68, "#7C3AED")

    risk_text = "未触发风险规则" if not risks else f"触发风险: {len(risks)} 条"
    rank_text = "\n".join(
        [
            f"{plan['plan_id']}: final {plan.get('final_score', 0):.2f}, penalty {plan.get('risk_penalty', 0)}"
            for plan in safety.get("ranked_plans", [])[:3]
        ]
    )
    safety_body = f"{risk_text}\n{rank_text}\n\n结论: 选择风险惩罚后最高分方案"
    draw_box(ax, 0.77, 0.27, 0.20, 0.24, "⑤ 安全审核", safety_body, "#DC2626", "#FEF2F2", 8.5)
    draw_arrow(ax, 0.87, 0.59, 0.87, 0.51, "#DC2626")

    final_body = (
        f"最终方案: {final_plan['plan_name']}\n"
        f"支持专科: {', '.join(final_plan.get('supporting_specialties', []))}\n"
        f"药物:\n{wrap_text(', '.join(final_plan['drugs']), 48)}\n"
        f"最终得分: {final_plan.get('aggregate_score', 0):.2f}"
    )
    draw_box(ax, 0.27, 0.18, 0.45, 0.21, "⑥ 结果输出", final_body, "#0F766E", "#F0FDFA", 9.0)
    draw_arrow(ax, 0.77, 0.38, 0.72, 0.30, "#0F766E")

    note = (
        "商议过程说明：该 JSON 未包含新版 MDT review_round 字段；图中按实际输出展示为："
        "各专科独立建议 → 候选方案排序 → 安全审核 → 最终方案。"
    )
    ax.text(
        0.03,
        0.08,
        note,
        ha="left",
        va="center",
        fontsize=10,
        color="#475569",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "#F8FAFC", "edgecolor": "#CBD5E1"},
    )

    output_path = OUTPUT_DIR / "cloud_mdt_case_0_diagnostic_flow.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output_path)


if __name__ == "__main__":
    main()
