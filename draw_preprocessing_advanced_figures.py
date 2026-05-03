from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "figures" / "preprocessing_advanced"
SPECIALTIES = ["心血管", "神经", "呼吸", "肾内/泌尿", "内分泌/代谢", "消化"]


def configure_matplotlib() -> None:
    font_candidates = [
        ("Microsoft YaHei", Path("C:/Windows/Fonts/msyh.ttc")),
        ("SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
        ("SimSun", Path("C:/Windows/Fonts/simsun.ttc")),
    ]
    available_font_names: list[str] = []
    for font_name, font_path in font_candidates:
        if font_path.exists():
            mpl.font_manager.fontManager.addfont(str(font_path))
            available_font_names.append(font_name)

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = available_font_names + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def read_csv_flexible(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding, usecols=usecols, low_memory=False)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path} -> {last_error}") from last_error


def count_rows(path: Path, usecols: list[str] | None = None) -> int:
    total = 0
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=300_000, low_memory=False):
        total += len(chunk)
    return total


def count_unique_hadm(path: Path) -> int:
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id"], dtype=str, chunksize=300_000, low_memory=False):
        values.update(chunk["hadm_id"].dropna().astype(str).tolist())
    return len(values)


def draw_band(ax: Any, x0: float, y0: float, x1: float, y1: float, width: float, color: str, alpha: float = 0.28) -> None:
    top0 = y0 + width / 2
    bot0 = y0 - width / 2
    top1 = y1 + width / 2
    bot1 = y1 - width / 2
    mid = (x0 + x1) / 2
    path = MplPath(
        [
            (x0, top0),
            (mid, top0),
            (mid, top1),
            (x1, top1),
            (x1, bot1),
            (mid, bot1),
            (mid, bot0),
            (x0, bot0),
            (x0, top0),
        ],
        [
            MplPath.MOVETO,
            MplPath.CURVE4,
            MplPath.CURVE4,
            MplPath.CURVE4,
            MplPath.LINETO,
            MplPath.CURVE4,
            MplPath.CURVE4,
            MplPath.CURVE4,
            MplPath.CLOSEPOLY,
        ],
    )
    ax.add_patch(PathPatch(path, facecolor=color, edgecolor="none", alpha=alpha))


def plot_case_flow(root_dir: Path, output_dir: Path) -> Path:
    cohort = count_unique_hadm(root_dir / "cohort_admissions.csv")
    mapped = count_unique_hadm(root_dir / "cleaned_diagnosis_specialty_detail_6.csv")
    single = count_unique_hadm(root_dir / "single_specialty_cases.csv")
    multi = count_unique_hadm(root_dir / "multi_specialty_cases_v2.csv")
    mature = count_unique_hadm(root_dir / "case_summary_mature.csv")

    fig, ax = plt.subplots(figsize=(15, 7.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("成人住院病例队列构建与分析分支", fontsize=17, fontweight="bold", pad=14)

    max_count = max(cohort, mapped, single + multi, mature, 1)
    box_w, box_h = 0.16, 0.13

    def draw_box(x: float, y: float, title: str, count: int, color: str, subtitle: str = "") -> None:
        ax.add_patch(
            Rectangle(
                (x - box_w / 2, y - box_h / 2),
                box_w,
                box_h,
                facecolor="white",
                edgecolor=color,
                linewidth=2.4,
            )
        )
        ax.text(x, y + 0.028, title, ha="center", va="center", fontsize=12, fontweight="bold", color=color)
        ax.text(x, y - 0.02, f"{count:,}", ha="center", va="center", fontsize=11, color="#111827")
        if subtitle:
            ax.text(x, y - 0.052, subtitle, ha="center", va="center", fontsize=8.5, color="#6B7280")

    # Main cohort
    cohort_x, cohort_y = 0.10, 0.52
    mapped_x, mapped_y = 0.34, 0.70
    mature_x, mature_y = 0.34, 0.33
    single_x, single_y = 0.62, 0.82
    multi_x, multi_y = 0.62, 0.58
    kb_x, kb_y = 0.88, 0.82
    mdt_x, mdt_y = 0.88, 0.58
    feature_x, feature_y = 0.62, 0.30

    # Bands, separated into two logical branches
    draw_band(ax, cohort_x + box_w / 2, cohort_y + 0.04, mapped_x - box_w / 2, mapped_y, 0.075 * mapped / max_count + 0.02, "#2563EB", 0.25)
    draw_band(ax, mapped_x + box_w / 2, mapped_y, single_x - box_w / 2, single_y, 0.075 * single / max_count + 0.018, "#F97316", 0.26)
    draw_band(ax, mapped_x + box_w / 2, mapped_y, multi_x - box_w / 2, multi_y, 0.075 * multi / max_count + 0.018, "#F59E0B", 0.26)
    draw_band(ax, cohort_x + box_w / 2, cohort_y - 0.05, mature_x - box_w / 2, mature_y, 0.075 * mature / max_count + 0.02, "#7C3AED", 0.18)
    draw_band(ax, mature_x + box_w / 2, mature_y, feature_x - box_w / 2, feature_y, 0.055 * mature / max_count + 0.015, "#7C3AED", 0.18)
    draw_band(ax, single_x + box_w / 2, single_y, kb_x - box_w / 2, kb_y, 0.04, "#10B981", 0.22)
    draw_band(ax, multi_x + box_w / 2, multi_y, mdt_x - box_w / 2, mdt_y, 0.055, "#F59E0B", 0.22)

    draw_box(cohort_x, cohort_y, "成人住院\n基础队列", cohort, "#2563EB", "主键/时间有效")
    draw_box(mapped_x, mapped_y, "六专科\n可映射病例", mapped, "#059669", "研究分析队列")
    draw_box(single_x, single_y, "单专科\n病例", single, "#F97316", "用于建库")
    draw_box(multi_x, multi_y, "多专科\n病例", multi, "#F59E0B", "用于MDT实验")
    draw_box(mature_x, mature_y, "成熟病例\n总表", mature, "#7C3AED", "覆盖基础队列")

    ax.add_patch(Rectangle((feature_x - box_w / 2, feature_y - box_h / 2), box_w, box_h, facecolor="white", edgecolor="#7C3AED", linewidth=2.0))
    ax.text(feature_x, feature_y + 0.032, "多维临床\n特征整合", ha="center", va="center", fontsize=12, fontweight="bold", color="#7C3AED")
    ax.text(feature_x, feature_y - 0.025, "诊断/处方/检验/生命体征\n既往史/操作/微生物/ICU/结局", ha="center", va="center", fontsize=8.5, color="#374151")

    ax.add_patch(Rectangle((kb_x - box_w / 2, kb_y - box_h / 2), box_w, box_h, facecolor="#ECFDF5", edgecolor="#10B981", linewidth=2.0))
    ax.text(kb_x, kb_y + 0.02, "六专科\n知识库", ha="center", va="center", fontsize=12, fontweight="bold", color="#047857")
    ax.text(kb_x, kb_y - 0.04, "诊断/药物/检验/风险", ha="center", va="center", fontsize=8.5, color="#374151")

    ax.add_patch(Rectangle((mdt_x - box_w / 2, mdt_y - box_h / 2), box_w, box_h, facecolor="#FFF7ED", edgecolor="#F59E0B", linewidth=2.0))
    ax.text(mdt_x, mdt_y + 0.02, "MDT多智能体\n协商实验", ha="center", va="center", fontsize=12, fontweight="bold", color="#B45309")
    ax.text(mdt_x, mdt_y - 0.04, "多专科评估与共识", ha="center", va="center", fontsize=8.5, color="#374151")

    ax.text(0.27, 0.92, "分支一：六专科研究队列与病例分层", ha="left", fontsize=11, color="#065F46", fontweight="bold")
    ax.text(0.27, 0.12, "分支二：成熟病例总表与多维特征整合", ha="left", fontsize=11, color="#5B21B6", fontweight="bold")
    ax.text(
        0.50,
        0.045,
        "说明：成熟病例总表覆盖成人基础队列；六专科病例是用于知识库构建与 MDT 实验的研究分析分支。",
        ha="center",
        fontsize=10,
        color="#374151",
    )

    output_path = output_dir / "01_case_selection_sankey_like.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_raw_processed_dumbbell(root_dir: Path, output_dir: Path) -> Path:
    lab_coverage = read_csv_flexible(root_dir / "cohort_first24h_labs_coverage.csv")
    raw_lab_records = int(pd.to_numeric(lab_coverage["raw_lab_record_count"], errors="coerce").fillna(0).sum())
    structured_lab_items = int(lab_coverage["itemid"].nunique())
    metrics = [
        ("诊断记录", count_rows(root_dir / "cohort_diagnoses.csv", ["hadm_id"]), count_rows(root_dir / "cleaned_diagnosis_specialty_detail_6.csv", ["hadm_id"])),
        ("处方记录", count_rows(root_dir / "cohort_prescriptions.csv", ["hadm_id"]), count_rows(root_dir / "cleaned_prescriptions.csv", ["hadm_id"])),
        ("检验事件→项目", raw_lab_records, structured_lab_items),
    ]
    df = pd.DataFrame(metrics, columns=["metric", "raw", "processed"])
    df["raw_log"] = df["raw"].clip(lower=1).apply(lambda x: np.log10(x))
    df["processed_log"] = df["processed"].clip(lower=1).apply(lambda x: np.log10(x))

    fig, ax = plt.subplots(figsize=(12, 6))
    y_positions = range(len(df))
    for y, row in zip(y_positions, df.itertuples(index=False)):
        ax.plot([row.raw_log, row.processed_log], [y, y], color="#94A3B8", linewidth=3, zorder=1)
        ax.scatter(row.raw_log, y, color="#2563EB", s=120, label="预处理前/原始层" if y == 0 else "", zorder=2)
        ax.scatter(row.processed_log, y, color="#F97316", s=120, label="预处理后/结构化层" if y == 0 else "", zorder=2)
        ax.text(row.raw_log, y + 0.16, f"{int(row.raw):,}", ha="center", fontsize=9, color="#1D4ED8")
        ax.text(row.processed_log, y - 0.24, f"{int(row.processed):,}", ha="center", fontsize=9, color="#C2410C")

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(df["metric"])
    ax.set_xlabel("记录规模 log10")
    ax.set_title("原始事件记录到结构化数据实体转换", fontsize=16, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    output_path = output_dir / "02_raw_vs_processed_dumbbell.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_lab_coverage_heatmap(root_dir: Path, output_dir: Path, top_n: int = 25) -> Path:
    coverage = read_csv_flexible(root_dir / "cohort_first24h_labs_coverage.csv")
    top_labs = coverage.sort_values(["coverage_pct", "non_null_case_count"], ascending=[False, False]).head(top_n)
    wanted = set(top_labs["lab_label"].astype(str).tolist())

    single = read_csv_flexible(root_dir / "single_specialty_cases.csv", usecols=["hadm_id", "specialty_group"])
    single["hadm_id"] = single["hadm_id"].astype(str)
    hadm_to_specialty = single.drop_duplicates("hadm_id").set_index("hadm_id")["specialty_group"]
    denom = single.groupby("specialty_group")["hadm_id"].nunique().to_dict()

    counts: dict[tuple[str, str], set[str]] = {(specialty, lab): set() for specialty in SPECIALTIES for lab in wanted}
    usecols = ["hadm_id", "lab_label"]
    for chunk in pd.read_csv(root_dir / "cohort_first24h_labs_all_long.csv", usecols=usecols, dtype=str, chunksize=500_000, low_memory=False):
        chunk = chunk[chunk["lab_label"].isin(wanted)].copy()
        if chunk.empty:
            continue
        chunk["specialty_group"] = chunk["hadm_id"].map(hadm_to_specialty)
        chunk = chunk.dropna(subset=["specialty_group"])
        for (specialty, lab), group in chunk.groupby(["specialty_group", "lab_label"]):
            counts.setdefault((specialty, lab), set()).update(group["hadm_id"].astype(str).tolist())

    matrix = []
    lab_order = top_labs["lab_label"].astype(str).tolist()
    for lab in lab_order:
        row = []
        for specialty in SPECIALTIES:
            total = denom.get(specialty, 0)
            pct = len(counts.get((specialty, lab), set())) * 100.0 / total if total else 0
            row.append(pct)
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(11, max(7, top_n * 0.28)))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(SPECIALTIES)))
    ax.set_xticklabels(SPECIALTIES, rotation=25)
    ax.set_yticks(range(len(lab_order)))
    ax.set_yticklabels(lab_order, fontsize=8)
    ax.set_title("六专科首 24 小时全量检验覆盖率热力图", fontsize=16, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("覆盖率 (%)")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value >= 60:
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="white")
            elif value >= 15:
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")

    output_path = output_dir / "03_lab_coverage_heatmap.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def count_hadm_with_any_non_null(path: Path, columns: list[str]) -> int:
    values: set[str] = set()
    usecols = ["hadm_id", *columns]
    for chunk in pd.read_csv(path, usecols=usecols, dtype=str, chunksize=300_000, low_memory=False):
        mask = chunk[columns].replace("", np.nan).notna().any(axis=1)
        values.update(chunk.loc[mask, "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def count_hadm_with_positive_numeric(path: Path, column: str) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id", column], chunksize=300_000, low_memory=False):
        numeric = pd.to_numeric(chunk[column], errors="coerce").fillna(0)
        values.update(chunk.loc[numeric > 0, "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def count_hadm_with_any_positive_flags(path: Path, columns: list[str]) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id", *columns], chunksize=300_000, low_memory=False):
        flag_frame = chunk[columns].apply(pd.to_numeric, errors="coerce").fillna(0)
        values.update(chunk.loc[flag_frame.gt(0).any(axis=1), "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def plot_feature_completeness_matrix(root_dir: Path, output_dir: Path) -> Path:
    mature_total = count_unique_hadm(root_dir / "case_summary_mature.csv")
    lab_cols = [
        "creatinine_24h",
        "bun_24h",
        "potassium_24h",
        "sodium_24h",
        "glucose_24h",
        "inr_24h",
        "bilirubin_total_24h",
    ]
    vital_cols = [
        "heart_rate_mean_24h",
        "respiratory_rate_mean_24h",
        "temperature_f_mean_24h",
        "spo2_mean_24h",
        "sbp_mean_24h",
        "dbp_mean_24h",
        "mbp_mean_24h",
    ]
    history_cols = [
        "history_hypertension",
        "history_diabetes",
        "history_heart_failure",
        "history_coronary_disease",
        "history_stroke",
        "history_copd",
        "history_chronic_kidney_disease",
        "history_chronic_liver_disease",
        "history_malignancy",
    ]
    measures = [
        ("六专科诊断", count_unique_hadm(root_dir / "cleaned_diagnosis_specialty_detail_6.csv"), "覆盖"),
        ("处方用药", count_unique_hadm(root_dir / "cleaned_prescriptions.csv"), "覆盖"),
        ("关键检验", count_hadm_with_any_non_null(root_dir / "cohort_first24h_labs.csv", lab_cols), "覆盖"),
        ("全量检验", count_unique_hadm(root_dir / "cohort_first24h_labs_all_long.csv"), "覆盖"),
        ("生命体征", count_hadm_with_any_non_null(root_dir / "cohort_first24h_vitals.csv", vital_cols), "有记录"),
        ("既往病史", count_hadm_with_any_positive_flags(root_dir / "past_history_flags.csv", history_cols), "阳性"),
        ("本次合并症", count_hadm_with_positive_numeric(root_dir / "comorbidity_summary.csv", "comorbidity_count"), "阳性"),
        ("操作治疗", count_hadm_with_positive_numeric(root_dir / "procedure_features.csv", "procedure_count"), "有记录"),
        ("微生物", count_hadm_with_positive_numeric(root_dir / "microbiology_features.csv", "microbiology_record_count"), "有记录"),
        ("ICU", count_hadm_with_positive_numeric(root_dir / "icu_features.csv", "icu_admission_flag"), "有记录"),
        ("结局", count_hadm_with_any_non_null(root_dir / "outcome_features.csv", ["hospital_los_days"]), "覆盖"),
    ]
    labels = [f"{name}\n({kind})" for name, _, kind in measures]
    values = [[count * 100.0 / mature_total if mature_total else 0.0] for _, count, _ in measures]

    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(values, cmap="PuBuGn", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks([0])
    ax.set_xticklabels(["有效信息比例"])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title("成熟病例多维特征有效信息矩阵", fontsize=16, fontweight="bold")
    for i, row in enumerate(values):
        ax.text(0, i, f"{row[0]:.1f}%", ha="center", va="center", color="white" if row[0] > 60 else "#111827", fontweight="bold")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("覆盖率 (%)")

    output_path = output_dir / "04_feature_completeness_matrix.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成高级数据预处理可视化图。")
    parser.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = [
        plot_case_flow(args.root_dir, output_dir),
        plot_raw_processed_dumbbell(args.root_dir, output_dir),
        plot_lab_coverage_heatmap(args.root_dir, output_dir),
        plot_feature_completeness_matrix(args.root_dir, output_dir),
    ]
    print("高级预处理图表生成完成：")
    for path in saved:
        print(path)


if __name__ == "__main__":
    main()
