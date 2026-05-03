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


def box(ax, x, y, w, h, title, body, edge, face, fs=9):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.010,rounding_size=0.012",
        facecolor=face,
        edgecolor=edge,
        linewidth=1.5,
    )
    ax.add_patch(patch)
    ax.text(x + 0.012, y + h - 0.030, title, ha="left", va="top", fontsize=10.5, fontweight="bold", color=edge)
    ax.text(x + 0.012, y + h - 0.070, body, ha="left", va="top", fontsize=fs, color="#111827", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color="#64748B"):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.4,
            color=color,
        )
    )


def main() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.965, "MDT 多智能体诊断流程与结果（cloud_mdt_case_0）", ha="center", va="top", fontsize=18, fontweight="bold", color="#111827")
    ax.text(0.5, 0.925, "病例输入 → 初始路由 → 四专科独立评估 → 交叉审阅 → 共识修订 → 安全审核 → 最终方案", ha="center", va="top", fontsize=10.5, color="#475569")

    stages = [
        ("① 病例输入", "48岁女性｜hadm_id 27988844\n主诊断：左股骨颈囊内骨折\n关键检验：Na 146，K 4.2，Cr 0.9，INR 1.1", "#2563EB", "#EFF6FF"),
        ("② 初始路由", "唤起专科：内分泌/代谢、神经、消化、心血管\n初始主专科：内分泌/代谢\n相关诊断数：4 / 3 / 3 / 3", "#059669", "#ECFDF5"),
        ("③ 交叉审阅", "4 个专科完成交叉审阅\n需降权/复核药物：0 个\n内分泌、神经均提示钠异常风险", "#7C3AED", "#FAF5FF"),
        ("④ 共识方案", "mdt_consensus：12.75\nlead_specialty_adjusted：12.75\nconservative_consensus：8.85", "#9333EA", "#F5F3FF"),
        ("⑤ 安全审核", "触发风险规则：2 条\nNa 146：内分泌/代谢中度风险\nNa 146：神经中度风险\n风险惩罚：2 分", "#DC2626", "#FEF2F2"),
    ]
    x0, y0, w, h, gap = 0.035, 0.735, 0.175, 0.150, 0.020
    for i, (title, body, edge, face) in enumerate(stages):
        x = x0 + i * (w + gap)
        box(ax, x, y0, w, h, title, body, edge, face, fs=8.3)
        if i < len(stages) - 1:
            arrow(ax, x + w, y0 + h / 2, x + w + gap, y0 + h / 2)

    ax.text(0.035, 0.650, "A. 各专科独立评估结果", ha="left", va="center", fontsize=12, fontweight="bold", color="#111827")
    rows = [
        ("内分泌/代谢", "4", "insulin；levothyroxine sodium；calcium carbonate", "Na中度风险 1条", "0.76"),
        ("神经", "3", "无明确候选药物", "Na中度风险 1条", "0.49"),
        ("消化", "3", "pantoprazole；polyethylene glycol", "无", "0.65"),
        ("心血管", "3", "furosemide；metoprolol；heparin；aspirin；warfarin", "无", "0.89"),
    ]
    headers = ["专科", "诊断数", "主要建议", "风险提醒", "置信度"]
    col_x = [0.035, 0.175, 0.280, 0.655, 0.825]
    col_w = [0.13, 0.09, 0.36, 0.16, 0.10]
    table_y, row_h = 0.405, 0.050
    ax.add_patch(FancyBboxPatch((0.035, table_y + row_h * 4), 0.895, row_h, boxstyle="round,pad=0.004,rounding_size=0.006", facecolor="#E2E8F0", edgecolor="#CBD5E1"))
    for x, cw, head in zip(col_x, col_w, headers):
        ax.text(x + cw / 2, table_y + row_h * 4.5, head, ha="center", va="center", fontsize=9.5, fontweight="bold", color="#0F172A")
    for idx, row in enumerate(rows):
        y = table_y + row_h * (3 - idx)
        face = "#FFFFFF" if idx % 2 == 0 else "#F8FAFC"
        ax.add_patch(FancyBboxPatch((0.035, y), 0.895, row_h, boxstyle="round,pad=0.002,rounding_size=0.004", facecolor=face, edgecolor="#E2E8F0"))
        for x, value in zip(col_x, row):
            ax.text(x + 0.006, y + row_h / 2, value, ha="left", va="center", fontsize=8.3, color="#111827")

    ax.text(0.035, 0.350, "B. MDT 共识与安全审核结果", ha="left", va="center", fontsize=12, fontweight="bold", color="#111827")
    consensus = (
        "MDT 协商摘要：\n"
        "纳入 4 个专科；初始主导专科为内分泌/代谢；\n"
        "交叉审阅阶段标记 0 个需降权或复核药物；\n"
        "共识阶段生成 3 个候选方案，并进入安全审核。"
    )
    box(ax, 0.035, 0.165, 0.42, 0.155, "MDT 协商摘要", consensus, "#7C3AED", "#FAF5FF", fs=8.6)

    final = (
        "最终方案：mdt_consensus（MDT多专科共识方案）\n"
        "支持专科：内分泌/代谢、心血管、消化\n"
        "最终得分：10.75（原始 12.75，风险惩罚 2）\n"
        "建议药物：insulin, levothyroxine sodium, calcium carbonate,\n"
        "pantoprazole, polyethylene glycol, furosemide"
    )
    box(ax, 0.515, 0.165, 0.45, 0.155, "最终输出", final, "#16A34A", "#F0FDF4", fs=8.6)
    arrow(ax, 0.455, 0.242, 0.515, 0.242, "#16A34A")

    ax.text(0.035, 0.090, "说明：本图依据用户提供的新版 cloud_mdt_case_0 输出绘制，展示独立评估、交叉审阅、共识修订、安全审核与最终方案。", ha="left", va="center", fontsize=9.2, color="#475569")

    output = OUTPUT_DIR / "cloud_mdt_case_0_publication_result_from_prompt.png"
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
