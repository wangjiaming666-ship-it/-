from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


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


def wrap_text(value: object, width: int = 28) -> str:
    return "\n".join(
        textwrap.wrap(str(value), width=width, break_long_words=False, replace_whitespace=False)
    )


def draw_panel(ax, x: float, y: float, w: float, h: float, title: str, color: str, face: str = "white") -> None:
    panel = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=face,
        edgecolor=color,
        linewidth=2.0,
    )
    ax.add_patch(panel)
    ax.add_patch(Rectangle((x, y + h - 0.052), w, 0.052, facecolor=color, edgecolor=color))
    ax.text(x + w / 2, y + h - 0.026, title, ha="center", va="center", fontsize=12, fontweight="bold", color="white")


def draw_arrow(ax, start: tuple[float, float], end: tuple[float, float], color: str = "#64748B") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.8,
            color=color,
        )
    )


def fmt_drugs(items: list[dict], n: int = 5) -> str:
    rows = []
    for item in items[:n]:
        rows.append(f"{item['rank']}. {item['drug_name']} ({item['confidence']:.2f})")
    return "\n".join(rows)


def main() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(INPUT_JSON, "r", encoding="utf-8") as file:
        data = json.load(file)

    case = data["case_record"]
    patient = case["patient_info"]
    routing = data["routing"]
    specialty_results = data["specialty_results"]
    plans = data["candidate_plans"]
    safety = data["safety_result"]
    final_plan = safety["final_plan"]
    labs = case["key_labs"]

    fig, ax = plt.subplots(figsize=(18, 11))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title("cloud_mdt_case_0 多智能体诊断与商议结果总览", fontsize=22, fontweight="bold", pad=18)

    # Top row: case and routing
    draw_panel(ax, 0.03, 0.74, 0.28, 0.19, "① 病例输入", "#2563EB", "#EFF6FF")
    case_text = (
        f"subject_id: {patient['subject_id']}    hadm_id: {patient['hadm_id']}\n"
        f"性别/年龄: {patient.get('gender')} / {patient.get('age')}\n"
        f"主诊断: {case['primary_diagnosis']}\n"
        f"合并症数量: {len(case.get('comorbidity_list', []))}\n"
        f"关键检验: Cr {labs.get('creatinine_24h')}, BUN {labs.get('bun_24h')}, "
        f"K {labs.get('potassium_24h')}, Na {labs.get('sodium_24h')}, "
        f"Glucose {labs.get('glucose_24h')}, INR {labs.get('inr_24h')}, TBil {labs.get('bilirubin_total_24h')}"
    )
    ax.text(0.045, 0.865, case_text, ha="left", va="top", fontsize=10.2, color="#111827", linespacing=1.35)

    draw_panel(ax, 0.36, 0.74, 0.25, 0.19, "② 初始诊断路由", "#059669", "#ECFDF5")
    route_text = (
        f"唤起专科: {'、'.join(routing['active_specialties'])}\n"
        f"初始主专科: {routing['lead_specialty']}\n"
        f"消化相关诊断: {len(routing['specialty_related_diagnoses'].get('消化', []))} 条\n"
        f"心血管相关诊断: {len(routing['specialty_related_diagnoses'].get('心血管', []))} 条\n"
        f"路由依据: {wrap_text(routing['rationale'], 25)}"
    )
    ax.text(0.375, 0.865, route_text, ha="left", va="top", fontsize=10.2, color="#111827", linespacing=1.35)
    draw_arrow(ax, (0.31, 0.835), (0.36, 0.835), "#64748B")

    draw_panel(ax, 0.66, 0.74, 0.31, 0.19, "③ 关键病例信息解释", "#7C3AED", "#FAF5FF")
    interpretation = (
        "病例以吞咽困难为主诊断，诊断映射唤起消化与心血管两个专科。\n"
        "关键检验未见明显肾功能、凝血、电解质或胆红素风险。\n"
        "后续建议主要来自消化专科病药映射证据，心血管专科提供并行参考。"
    )
    ax.text(0.675, 0.865, interpretation, ha="left", va="top", fontsize=10.2, color="#111827", linespacing=1.45)
    draw_arrow(ax, (0.61, 0.835), (0.66, 0.835), "#64748B")

    # Middle row: specialty results
    panel_specs = [(0.03, 0.43, 0.45, 0.25, specialty_results[0], "#EA580C", "#FFF7ED"), (0.52, 0.43, 0.45, 0.25, specialty_results[1], "#2563EB", "#EFF6FF")]
    for x, y, w, h, result, color, face in panel_specs:
        specialty = result["specialty_name"]
        draw_panel(ax, x, y, w, h, f"④ {specialty}专科智能体输出", color, face)
        diagnoses = routing["specialty_related_diagnoses"].get(specialty, [])
        diagnosis_preview = "\n".join([f"- {wrap_text(item, 38)}" for item in diagnoses[:3]])
        drugs = fmt_drugs(result["recommended_drugs_topk"], 5)
        body = (
            f"相关诊断 {len(diagnoses)} 条:\n{diagnosis_preview}\n\n"
            f"推荐药物 Top5:\n{drugs}\n\n"
            f"低优先级/避免提示: {len(result.get('avoid_or_low_priority_drugs', []))} 条    "
            f"风险提醒: {len(result.get('risk_alerts', []))} 条    "
            f"总体置信度: {result.get('overall_confidence')}"
        )
        ax.text(x + 0.015, y + h - 0.075, body, ha="left", va="top", fontsize=8.6, color="#111827", linespacing=1.23)

    draw_arrow(ax, (0.485, 0.555), (0.52, 0.555), "#64748B")

    # Candidate plans
    draw_panel(ax, 0.03, 0.17, 0.46, 0.21, "⑤ 候选方案商议/排序", "#7C3AED", "#FAF5FF")
    plan_lines = []
    for plan in plans:
        plan_lines.append(
            f"{plan['plan_id']}｜{plan['plan_name']}｜得分 {plan['aggregate_score']:.2f}\n"
            f"药物: {', '.join(plan['drugs'])}"
        )
    ax.text(0.045, 0.32, "\n\n".join(plan_lines), ha="left", va="top", fontsize=9.0, color="#111827", linespacing=1.25)

    draw_panel(ax, 0.53, 0.17, 0.20, 0.21, "⑥ 安全审核", "#DC2626", "#FEF2F2")
    risk_text = "未触发风险规则" if not safety.get("triggered_risks") else f"触发 {len(safety['triggered_risks'])} 条风险"
    ranked_text = "\n".join(
        [
            f"{item['plan_id']}: 原始 {item['aggregate_score']:.2f}, 扣分 {item['risk_penalty']}, 最终 {item['final_score']:.2f}"
            for item in safety.get("ranked_plans", [])
        ]
    )
    ax.text(0.545, 0.32, f"{risk_text}\n\n{ranked_text}", ha="left", va="top", fontsize=9.0, color="#111827", linespacing=1.35)
    draw_arrow(ax, (0.49, 0.275), (0.53, 0.275), "#64748B")

    draw_panel(ax, 0.78, 0.17, 0.19, 0.21, "⑦ 最终输出", "#0F766E", "#F0FDFA")
    final_text = (
        f"最终方案: {final_plan['plan_id']} {final_plan['plan_name']}\n"
        f"支持专科: {', '.join(final_plan.get('supporting_specialties', []))}\n"
        f"最终得分: {final_plan.get('aggregate_score', 0):.2f}\n\n"
        f"药物:\n- " + "\n- ".join(final_plan["drugs"])
    )
    ax.text(0.795, 0.32, final_text, ha="left", va="top", fontsize=9.0, color="#111827", linespacing=1.25)
    draw_arrow(ax, (0.73, 0.275), (0.78, 0.275), "#64748B")

    note = (
        "说明：本图严格依据 cloud_mdt_case_0.json 绘制。该 JSON 为旧版输出结构，包含路由、专科建议、候选方案排序与安全审核；"
        "未包含新版 MDT review_round 字段。"
    )
    ax.text(
        0.03,
        0.065,
        note,
        ha="left",
        va="center",
        fontsize=10,
        color="#475569",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#F8FAFC", "edgecolor": "#CBD5E1"},
    )

    output_path = OUTPUT_DIR / "cloud_mdt_case_0_detailed_result.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output_path)


if __name__ == "__main__":
    main()
