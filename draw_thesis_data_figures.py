from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "figures" / "thesis_data"
SPECIALTIES = ["心血管", "神经", "呼吸", "肾内/泌尿", "内分泌/代谢", "消化"]
SPECIALTY_COLORS = {
    "心血管": "#2563EB",
    "神经": "#7C3AED",
    "呼吸": "#059669",
    "肾内/泌尿": "#0891B2",
    "内分泌/代谢": "#EA580C",
    "消化": "#B45309",
}


def configure_matplotlib() -> None:
    font_candidates = [
        ("Microsoft YaHei", Path("C:/Windows/Fonts/msyh.ttc")),
        ("SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
        ("SimSun", Path("C:/Windows/Fonts/simsun.ttc")),
    ]
    fonts: list[str] = []
    for font_name, font_path in font_candidates:
        if font_path.exists():
            mpl.font_manager.fontManager.addfont(str(font_path))
            fonts.append(font_name)
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = fonts + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def read_csv(path: Path, usecols: list[str] | None = None, dtype: Any | None = None) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, usecols=usecols, dtype=dtype, encoding=encoding, low_memory=False)
        except Exception:  # noqa: BLE001
            continue
    return pd.read_csv(path, usecols=usecols, dtype=dtype, low_memory=False)


def count_rows(path: Path, usecols: list[str] | None = None) -> int:
    total = 0
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=500_000, low_memory=False):
        total += len(chunk)
    return total


def count_unique_hadm(path: Path) -> int:
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id"], dtype=str, chunksize=500_000, low_memory=False):
        values.update(chunk["hadm_id"].dropna().astype(str).tolist())
    return len(values)


def count_hadm_with_any_non_null(path: Path, columns: list[str]) -> int:
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id", *columns], dtype=str, chunksize=300_000, low_memory=False):
        mask = chunk[columns].replace("", np.nan).notna().any(axis=1)
        values.update(chunk.loc[mask, "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def count_hadm_with_positive_numeric(path: Path, column: str) -> int:
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id", column], chunksize=300_000, low_memory=False):
        numeric = pd.to_numeric(chunk[column], errors="coerce").fillna(0)
        values.update(chunk.loc[numeric > 0, "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def count_hadm_with_any_positive_flags(path: Path, columns: list[str]) -> int:
    values: set[str] = set()
    for chunk in pd.read_csv(path, usecols=["hadm_id", *columns], chunksize=300_000, low_memory=False):
        flags = chunk[columns].apply(pd.to_numeric, errors="coerce").fillna(0)
        values.update(chunk.loc[flags.gt(0).any(axis=1), "hadm_id"].dropna().astype(str).tolist())
    return len(values)


def add_node(ax: Any, x: float, y: float, title: str, value: int, subtitle: str, color: str) -> None:
    box = FancyBboxPatch(
        (x - 0.13, y - 0.105),
        0.26,
        0.21,
        boxstyle="round,pad=0.016,rounding_size=0.02",
        facecolor="white",
        edgecolor=color,
        linewidth=2.2,
    )
    ax.add_patch(box)
    ax.text(x, y + 0.045, title, ha="center", va="center", fontsize=11.5, fontweight="bold", color=color)
    ax.text(x, y - 0.01, f"{value:,}", ha="center", va="center", fontsize=12, color="#111827")
    ax.text(x, y - 0.063, subtitle, ha="center", va="center", fontsize=8.5, color="#4B5563")


def add_arrow(ax: Any, start: tuple[float, float], end: tuple[float, float], color: str) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=2,
            color=color,
        )
    )


def plot_processing_entity_funnels(root_dir: Path, output_dir: Path) -> Path:
    diagnosis_raw = count_rows(root_dir / "cohort_diagnoses.csv", ["hadm_id"])
    diagnosis_clean = count_rows(root_dir / "cleaned_diagnosis_specialty_detail_6.csv", ["hadm_id"])
    diagnosis_cases = count_unique_hadm(root_dir / "cleaned_diagnosis_specialty_detail_6.csv")
    rx_raw = count_rows(root_dir / "cohort_prescriptions.csv", ["hadm_id"])
    rx_clean = count_rows(root_dir / "cleaned_prescriptions.csv", ["hadm_id"])
    rx_cases = count_unique_hadm(root_dir / "cleaned_prescriptions.csv")
    lab_coverage = read_csv(root_dir / "cohort_first24h_labs_coverage.csv")
    lab_events = int(pd.to_numeric(lab_coverage["raw_lab_record_count"], errors="coerce").fillna(0).sum())
    lab_case_items = count_rows(root_dir / "cohort_first24h_labs_all_long.csv", ["hadm_id"])
    lab_items = int(lab_coverage["itemid"].nunique())

    rows = [
        ("诊断数据", [("原始诊断记录", diagnosis_raw, "住院诊断明细"), ("六专科诊断记录", diagnosis_clean, "映射后诊断明细"), ("可映射病例", diagnosis_cases, "病例数")], "#2563EB"),
        ("处方数据", [("原始处方记录", rx_raw, "住院处方明细"), ("清洗后用药记录", rx_clean, "药名标准化后"), ("有处方案例", rx_cases, "病例数")], "#059669"),
        ("检验数据", [("首24h检验事件", lab_events, "数值型检验事件"), ("病例-检验项目", lab_case_items, "长表结构"), ("检验项目数", lab_items, "覆盖率统计")], "#EA580C"),
    ]
    arrow_labels = [
        ("诊断清洗与六专科映射", "按病例汇总"),
        ("药名清洗与去重", "按病例汇总"),
        ("限定首24小时并标准化", "按检验项目汇总"),
    ]
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.set_xlim(-0.06, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("原始临床事件到结构化分析实体转换", fontsize=17, fontweight="bold", pad=14)
    ys = [0.78, 0.50, 0.22]
    xs = [0.26, 0.55, 0.84]
    for y, (label, items, color), labels in zip(ys, rows, arrow_labels):
        ax.text(-0.025, y, label, ha="left", va="center", fontsize=13, fontweight="bold", color=color)
        for i, (title, value, subtitle) in enumerate(items):
            add_node(ax, xs[i], y, title, value, subtitle, color)
            if i < 2:
                add_arrow(ax, (xs[i] + 0.14, y), (xs[i + 1] - 0.14, y), color)
                ax.text((xs[i] + xs[i + 1]) / 2, y + 0.055, labels[i], ha="center", fontsize=9, color="#6B7280")
    output_path = output_dir / "01_processing_entity_funnels.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_specialty_involvement_bubble(root_dir: Path, output_dir: Path) -> Path:
    single = read_csv(root_dir / "single_specialty_cases.csv", usecols=["hadm_id", "specialty_group"], dtype=str)
    multi = read_csv(root_dir / "multi_specialty_cases_v2.csv", usecols=["hadm_id", "specialty_list"], dtype=str)
    single_counts = single.groupby("specialty_group")["hadm_id"].nunique().to_dict()
    multi_counts = {specialty: 0 for specialty in SPECIALTIES}
    for value in multi["specialty_list"].dropna().astype(str):
        for specialty in [part.strip() for part in value.split("|")]:
            if specialty in multi_counts:
                multi_counts[specialty] += 1
    df = pd.DataFrame([(s, single_counts.get(s, 0), multi_counts.get(s, 0)) for s in SPECIALTIES], columns=["specialty", "single", "multi"])
    df["total"] = df["single"] + df["multi"]
    fig, ax = plt.subplots(figsize=(10, 7.5))
    sizes = 300 + df["total"] / df["total"].max() * 1000
    for row, size in zip(df.itertuples(index=False), sizes):
        ax.scatter(row.single, row.multi, s=size, color=SPECIALTY_COLORS[row.specialty], alpha=0.75, edgecolor="white", linewidth=1.8)
        label = row.specialty.replace("/", "/\n") if "/" in row.specialty else row.specialty
        ax.text(row.single, row.multi, label, ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
    ax.set_xlabel("单专科病例数")
    ax.set_ylabel("多专科病例参与次数")
    ax.set_title("六专科病例参与结构气泡图", fontsize=16, fontweight="bold")
    x_min, x_max = df["single"].min(), df["single"].max()
    y_min, y_max = df["multi"].min(), df["multi"].max()
    x_pad = max((x_max - x_min) * 0.16, 1200)
    y_pad = max((y_max - y_min) * 0.12, 6000)
    ax.set_xlim(max(0, x_min - x_pad), x_max + x_pad)
    ax.set_ylim(max(0, y_min - y_pad), y_max + y_pad)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.text(0.02, 0.02, "气泡大小表示该专科在单专科与多专科病例中的总参与规模", transform=ax.transAxes, va="bottom", fontsize=9, color="#374151")
    output_path = output_dir / "02_specialty_involvement_bubble.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_effective_information_lollipop(root_dir: Path, output_dir: Path) -> Path:
    total = count_unique_hadm(root_dir / "case_summary_mature.csv")
    lab_cols = ["creatinine_24h", "bun_24h", "potassium_24h", "sodium_24h", "glucose_24h", "inr_24h", "bilirubin_total_24h"]
    vital_cols = ["heart_rate_mean_24h", "respiratory_rate_mean_24h", "temperature_f_mean_24h", "spo2_mean_24h", "sbp_mean_24h", "dbp_mean_24h", "mbp_mean_24h"]
    history_cols = ["history_hypertension", "history_diabetes", "history_heart_failure", "history_coronary_disease", "history_stroke", "history_copd", "history_chronic_kidney_disease", "history_chronic_liver_disease", "history_malignancy"]
    metrics = [
        ("六专科诊断覆盖", count_unique_hadm(root_dir / "cleaned_diagnosis_specialty_detail_6.csv"), "覆盖"),
        ("处方用药覆盖", count_unique_hadm(root_dir / "cleaned_prescriptions.csv"), "覆盖"),
        ("关键检验覆盖", count_hadm_with_any_non_null(root_dir / "cohort_first24h_labs.csv", lab_cols), "覆盖"),
        ("全量检验覆盖", count_unique_hadm(root_dir / "cohort_first24h_labs_all_long.csv"), "覆盖"),
        ("生命体征有记录", count_hadm_with_any_non_null(root_dir / "cohort_first24h_vitals.csv", vital_cols), "有记录"),
        ("既往病史阳性", count_hadm_with_any_positive_flags(root_dir / "past_history_flags.csv", history_cols), "阳性"),
        ("操作治疗有记录", count_hadm_with_positive_numeric(root_dir / "procedure_features.csv", "procedure_count"), "有记录"),
        ("微生物有记录", count_hadm_with_positive_numeric(root_dir / "microbiology_features.csv", "microbiology_record_count"), "有记录"),
        ("ICU暴露", count_hadm_with_positive_numeric(root_dir / "icu_features.csv", "icu_admission_flag"), "阳性"),
    ]
    df = pd.DataFrame(metrics, columns=["metric", "count", "type"])
    df["pct"] = df["count"] * 100.0 / total if total else 0
    df = df.sort_values("pct")
    fig, ax = plt.subplots(figsize=(10, 7.4))
    y = np.arange(len(df))
    ax.hlines(y, 0, df["pct"], color="#CBD5E1", linewidth=3)
    colors = ["#2563EB" if t == "覆盖" else "#EA580C" for t in df["type"]]
    ax.scatter(df["pct"], y, s=120, color=colors, zorder=3)
    for yi, row in zip(y, df.itertuples(index=False)):
        ax.text(row.pct + 1.2, yi, f"{row.pct:.1f}% ({int(row.count):,})", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(df["metric"])
    ax.set_xlim(0, 105)
    ax.set_xlabel("病例比例 (%)")
    ax.set_title("成熟病例关键临床信息有效比例", fontsize=16, fontweight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.text(0.13, 0.035, "说明：蓝色表示覆盖率；橙色表示阳性或有记录比例。", fontsize=9, color="#374151")
    fig.subplots_adjust(bottom=0.14)
    output_path = output_dir / "03_effective_information_lollipop.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_lab_coverage_heatmap(root_dir: Path, output_dir: Path, top_n: int = 24) -> Path:
    coverage = read_csv(root_dir / "cohort_first24h_labs_coverage.csv")
    top_labs = coverage.sort_values(["coverage_pct", "non_null_case_count"], ascending=[False, False]).head(top_n)
    wanted = set(top_labs["lab_label"].astype(str))
    single = read_csv(root_dir / "single_specialty_cases.csv", usecols=["hadm_id", "specialty_group"], dtype=str)
    hadm_to_specialty = single.drop_duplicates("hadm_id").set_index("hadm_id")["specialty_group"]
    denom = single.groupby("specialty_group")["hadm_id"].nunique().to_dict()
    counts: dict[tuple[str, str], set[str]] = {(s, l): set() for s in SPECIALTIES for l in wanted}
    for chunk in pd.read_csv(root_dir / "cohort_first24h_labs_all_long.csv", usecols=["hadm_id", "lab_label"], dtype=str, chunksize=500_000, low_memory=False):
        chunk = chunk[chunk["lab_label"].isin(wanted)]
        if chunk.empty:
            continue
        chunk["specialty_group"] = chunk["hadm_id"].map(hadm_to_specialty)
        chunk = chunk.dropna(subset=["specialty_group"])
        for (specialty, lab), group in chunk.groupby(["specialty_group", "lab_label"]):
            counts.setdefault((specialty, lab), set()).update(group["hadm_id"].astype(str))
    labels = top_labs["lab_label"].astype(str).tolist()
    matrix = [[len(counts.get((s, lab), set())) * 100 / denom.get(s, 1) for s in SPECIALTIES] for lab in labels]
    fig, ax = plt.subplots(figsize=(10.5, 7))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(SPECIALTIES)))
    ax.set_xticklabels(SPECIALTIES, rotation=25)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title("六专科首24小时全量检验覆盖率热力图", fontsize=16, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("覆盖率 (%)")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value >= 60:
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="white")
            elif value >= 15:
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    output_path = output_dir / "04_lab_coverage_heatmap.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成正式论文数据结果图。")
    parser.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    saved = [
        plot_processing_entity_funnels(args.root_dir, args.output_dir),
        plot_specialty_involvement_bubble(args.root_dir, args.output_dir),
        plot_effective_information_lollipop(args.root_dir, args.output_dir),
        plot_lab_coverage_heatmap(args.root_dir, args.output_dir),
    ]
    print("论文数据图生成完成：")
    for path in saved:
        print(path)


if __name__ == "__main__":
    main()
