from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
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


def panel(ax, x, y, w, h, title, body, color, face, fs=9.0):
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=face,
        edgecolor=color,
        linewidth=2,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h - 0.032, title, ha="center", va="top", fontsize=11.5, fontweight="bold", color=color)
    ax.text(x + 0.014, y + h - 0.072, body, ha="left", va="top", fontsize=fs, color="#111827", linespacing=1.28)


def arrow(ax, x1, y1, x2, y2, color="#64748B", rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.8,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def main() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(20, 12))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title("cloud_mdt_case_0 多专科 MDT 智能体结果总览", fontsize=24, fontweight="bold", pad=18)

    # Case input and routing
    case_body = (
        "患者: 48岁女性\n"
        "hadm_id: 27988844\n"
        "主诊断: 左股骨颈囊内骨折\n"
        "合并症: 骨质疏松、抗凝药长期使用、偏头痛、二尖瓣脱垂等\n"
        "关键检验: Na 146, K 4.2, Cr 0.9, INR 1.1"
    )
    panel(ax, 0.03, 0.76, 0.22, 0.17, "① 病例输入", case_body, "#2563EB", "#EFF6FF", 8.8)

    route_body = (
        "唤起专科: 内分泌/代谢、神经、消化、心血管\n"
        "初始主专科: 内分泌/代谢\n"
        "依据: 各专科相关诊断数量\n"
        "诊断数: 内分泌4条，神经3条，消化3条，心血管3条"
    )
    panel(ax, 0.30, 0.76, 0.25, 0.17, "② 初始诊断路由", route_body, "#059669", "#ECFDF5", 8.8)
    arrow(ax, 0.25, 0.845, 0.30, 0.845)

    # Round 1 independent assessments
    ax.text(0.03, 0.69, "第一轮：各专科独立诊断评估与建议", fontsize=14, fontweight="bold", color="#374151")
    specs = [
        ("内分泌/代谢", "诊断相关: 4条\n建议: insulin, levothyroxine sodium, calcium carbonate\n风险: 钠 146 触发中度水钠风险\n置信度: 0.76", "#EA580C", "#FFF7ED"),
        ("神经", "诊断相关: 3条\n建议: 无明确候选药物\n风险: 钠 146 触发中度神经风险\n置信度: 0.49", "#7C3AED", "#FAF5FF"),
        ("消化", "诊断相关: 3条\n建议: pantoprazole, polyethylene glycol\n风险: 未触发\n置信度: 0.65", "#B45309", "#FFFBEB"),
        ("心血管", "诊断相关: 3条\n建议: furosemide, metoprolol, heparin, aspirin, warfarin\n风险: 未触发\n置信度: 0.89", "#2563EB", "#EFF6FF"),
    ]
    x_positions = [0.03, 0.275, 0.52, 0.765]
    for (name, body, color, face), x in zip(specs, x_positions):
        panel(ax, x, 0.48, 0.21, 0.18, f"{name}智能体", body, color, face, 8.2)
        arrow(ax, 0.42, 0.76, x + 0.105, 0.66, color, rad=0.08)

    # Round 2 cross review
    ax.text(0.03, 0.42, "第二轮：交叉审阅与冲突/风险反馈", fontsize=14, fontweight="bold", color="#374151")
    review_body = (
        "内分泌/代谢: 保留3个候选药物；提示钠异常需安全复核\n"
        "神经: 无候选药物；提示钠异常可能影响意识/癫痫风险\n"
        "消化: 保留2个候选药物；未发现明显跨专科冲突\n"
        "心血管: 保留5个候选药物；未发现明显跨专科冲突\n"
        "交叉审阅结果: 0个候选药物被标记为需降权或复核"
    )
    panel(ax, 0.08, 0.25, 0.38, 0.15, "③ 专科交叉审阅意见", review_body, "#0F766E", "#F0FDFA", 8.5)
    for x in x_positions:
        arrow(ax, x + 0.105, 0.48, 0.27, 0.40, "#0F766E", rad=0.08)

    # Round 3 consensus plans
    consensus_body = (
        "共识说明:\n"
        "纳入4个专科；初始主导专科为内分泌/代谢；最终由各专科交叉审阅后形成。\n\n"
        "候选方案:\n"
        "1. mdt_consensus：得分12.75，药物6个\n"
        "2. lead_specialty_adjusted：得分12.75，药物6个\n"
        "3. conservative_consensus：得分8.85，药物4个"
    )
    panel(ax, 0.53, 0.25, 0.22, 0.20, "④ 第三轮：MDT共识修订", consensus_body, "#7C3AED", "#FAF5FF", 8.4)
    arrow(ax, 0.46, 0.325, 0.53, 0.35, "#7C3AED")

    # Safety
    safety_body = (
        "触发风险规则: 2条\n"
        "1. 内分泌/代谢 sodium_24h = 146，中度风险\n"
        "2. 神经 sodium_24h = 146，中度风险\n\n"
        "风险惩罚: 2分\n"
        "mdt_consensus: 12.75 → 10.75\n"
        "lead_specialty_adjusted: 12.75 → 10.75\n"
        "conservative_consensus: 8.85 → 6.85"
    )
    panel(ax, 0.79, 0.25, 0.18, 0.20, "⑤ 安全审核", safety_body, "#DC2626", "#FEF2F2", 8.2)
    arrow(ax, 0.75, 0.35, 0.79, 0.35, "#DC2626")

    # Final output
    final_body = (
        "最终方案: mdt_consensus\n"
        "方案名称: MDT多专科共识方案\n"
        "支持专科: 内分泌/代谢、心血管、消化\n"
        "最终得分: 10.75\n\n"
        "建议药物:\n"
        "insulin, levothyroxine sodium, calcium carbonate,\n"
        "pantoprazole, polyethylene glycol, furosemide"
    )
    panel(ax, 0.30, 0.05, 0.42, 0.15, "⑥ 最终输出结果", final_body, "#16A34A", "#F0FDF4", 8.8)
    arrow(ax, 0.88, 0.25, 0.72, 0.13, "#16A34A", rad=-0.12)

    # Legend
    ax.text(
        0.03,
        0.02,
        "图示逻辑：病例输入 → 初始路由 → 四个专科独立评估 → 交叉审阅 → MDT共识修订 → 安全审核 → 最终方案。",
        fontsize=10,
        color="#475569",
    )

    output_path = OUTPUT_DIR / "cloud_mdt_case_0_mdt_detailed_result.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output_path)


if __name__ == "__main__":
    main()
