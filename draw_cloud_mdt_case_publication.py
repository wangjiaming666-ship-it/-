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


def wrap(value: object, width: int) -> str:
    return "\n".join(textwrap.wrap(str(value), width=width, break_long_words=False))


def box(ax, x, y, w, h, title, body, edge="#334155", face="#F8FAFC", title_color="#0F172A", body_size=9):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.010,rounding_size=0.012",
        facecolor=face,
        edgecolor=edge,
        linewidth=1.6,
    )
    ax.add_patch(patch)
    ax.text(x + 0.012, y + h - 0.030, title, ha="left", va="top", fontsize=10.5, fontweight="bold", color=title_color)
    ax.text(x + 0.012, y + h - 0.070, body, ha="left", va="top", fontsize=body_size, color="#111827", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color="#64748B"):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.5,
            color=color,
        )
    )


def main() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(INPUT_JSON, "r", encoding="utf-8") as file:
        data = json.load(file)

    case = data["case_record"]
    patient = case["patient_info"]
    routing = data["routing"]
    specialty_results = data["specialty_results"]
    mdt = data.get("mdt_discussion", {})
    safety = data["safety_result"]
    final_plan = safety["final_plan"]

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.965, "MDT 多智能体诊断流程与结果（cloud_mdt_case_0）", ha="center", va="top", fontsize=18, fontweight="bold", color="#111827")
    ax.text(0.5, 0.925, "病例输入 → 初始路由 → 专科独立评估 → 交叉审阅 → 共识修订 → 安全审核 → 最终方案", ha="center", va="top", fontsize=10.5, color="#475569")

    # Stage cards
    labs = case.get("key_labs", {})
    case_body = (
        f"48岁女性，hadm_id {patient['hadm_id']}\n"
        f"主诊断：{wrap(case['primary_diagnosis'], 24)}\n"
        f"关键检验：Na {labs.get('sodium_24h')}，K {labs.get('potassium_24h')}，Cr {labs.get('creatinine_24h')}，INR {labs.get('inr_24h')}"
    )
    route_body = (
        f"唤起专科：{'、'.join(routing['active_specialties'])}\n"
        f"初始主专科：{routing['lead_specialty']}\n"
        "依据：各专科相关诊断数量"
    )
    review_count = sum(len(item.get("cautioned_drugs", [])) for item in mdt.get("review_round", []))
    review_body = (
        f"参与专科：{len(specialty_results)} 个\n"
        f"交叉审阅意见：{len(mdt.get('review_round', []))} 条\n"
        f"需降权/复核药物：{review_count} 个"
    )
    consensus_body = "\n".join(
        [
            f"{plan['plan_id']}：{plan['aggregate_score']:.2f}"
            for plan in mdt.get("candidate_plans", data.get("candidate_plans", []))
        ]
    )
    risk_body = (
        f"触发风险规则：{len(safety.get('triggered_risks', []))} 条\n"
        + "\n".join([f"{r['specialty_name']}：{r['lab_name']}={r['lab_value']}（{r['risk_level']}）" for r in safety.get("triggered_risks", [])])
    )

    stages = [
        ("① 病例输入", case_body, "#2563EB", "#EFF6FF"),
        ("② 初始路由", route_body, "#059669", "#ECFDF5"),
        ("③ 交叉审阅", review_body, "#7C3AED", "#FAF5FF"),
        ("④ 共识方案", consensus_body, "#9333EA", "#F5F3FF"),
        ("⑤ 安全审核", risk_body, "#DC2626", "#FEF2F2"),
    ]
    x0, y0, w, h, gap = 0.035, 0.735, 0.175, 0.145, 0.020
    centers = []
    for idx, (title, body, edge, face) in enumerate(stages):
        x = x0 + idx * (w + gap)
        box(ax, x, y0, w, h, title, body, edge=edge, face=face, title_color=edge, body_size=8.2)
        centers.append((x + w, y0 + h / 2, x + w + gap, y0 + h / 2))
    for x1, y1, x2, y2 in centers[:-1]:
        arrow(ax, x1, y1, x2, y2)

    # Specialty assessment table
    ax.text(0.035, 0.655, "A. 各专科独立评估结果", ha="left", va="center", fontsize=12, fontweight="bold", color="#111827")
    table_x, table_y, table_w, row_h = 0.035, 0.405, 0.93, 0.050
    headers = ["专科", "相关诊断数", "Top 建议", "风险提醒", "置信度/说明"]
    col_ws = [0.14, 0.12, 0.37, 0.16, 0.21]
    col_xs = [table_x]
    for cw in col_ws[:-1]:
        col_xs.append(col_xs[-1] + table_w * cw)
    ax.add_patch(FancyBboxPatch((table_x, table_y + row_h * 4), table_w, row_h, boxstyle="round,pad=0.004,rounding_size=0.006", facecolor="#E2E8F0", edgecolor="#CBD5E1"))
    for x, cw, head in zip(col_xs, col_ws, headers):
        ax.text(x + table_w * cw / 2, table_y + row_h * 4.5, head, ha="center", va="center", fontsize=9.5, fontweight="bold", color="#0F172A")

    for r, result in enumerate(specialty_results):
        y = table_y + row_h * (3 - r)
        face = "#FFFFFF" if r % 2 == 0 else "#F8FAFC"
        ax.add_patch(FancyBboxPatch((table_x, y), table_w, row_h, boxstyle="round,pad=0.002,rounding_size=0.004", facecolor=face, edgecolor="#E2E8F0"))
        specialty = result["specialty_name"]
        diag_n = len(routing["specialty_related_diagnoses"].get(specialty, []))
        drugs = ", ".join([item["drug_name"] for item in result.get("recommended_drugs_topk", [])[:3]]) or "无明确候选药物"
        risk_n = len(result.get("risk_alerts", []))
        confidence = result.get("overall_confidence", "")
        values = [specialty, str(diag_n), wrap(drugs, 34), f"{risk_n} 条", str(confidence)]
        for x, cw, value in zip(col_xs, col_ws, values):
            ax.text(x + 0.008, y + row_h / 2, value, ha="left", va="center", fontsize=8.5, color="#111827")

    # MDT and final table
    ax.text(0.035, 0.350, "B. MDT 共识与安全审核结果", ha="left", va="center", fontsize=12, fontweight="bold", color="#111827")
    left_body = "\n".join(mdt.get("consensus_notes", [])[:4])
    box(ax, 0.035, 0.165, 0.42, 0.155, "MDT 协商摘要", left_body, edge="#7C3AED", face="#FAF5FF", title_color="#7C3AED", body_size=8.6)

    final_drugs = ", ".join(final_plan["drugs"])
    final_body = (
        f"最终方案：{final_plan['plan_id']}（{final_plan['plan_name']}）\n"
        f"支持专科：{'、'.join(final_plan.get('supporting_specialties', []))}\n"
        f"最终得分：{final_plan.get('aggregate_score', 0):.2f}\n"
        f"建议药物：{wrap(final_drugs, 42)}"
    )
    box(ax, 0.515, 0.165, 0.45, 0.155, "最终输出", final_body, edge="#16A34A", face="#F0FDF4", title_color="#16A34A", body_size=8.6)
    arrow(ax, 0.455, 0.242, 0.515, 0.242, "#16A34A")

    note = "说明：本图依据 cloud_mdt_case_0.json 的新版 MDT 输出绘制，展示独立评估、交叉审阅、共识修订、安全审核和最终方案。"
    ax.text(0.035, 0.090, note, ha="left", va="center", fontsize=9.2, color="#475569")

    output_path = OUTPUT_DIR / "cloud_mdt_case_0_publication_result.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output_path)


if __name__ == "__main__":
    main()
