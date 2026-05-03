from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
KB_DIR = ROOT_DIR / "knowledge_base"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "figures" / "raw_vs_processed"

SPECIALTIES = [
    "心血管",
    "神经",
    "呼吸",
    "肾内/泌尿",
    "内分泌/代谢",
    "消化",
]

RAW_DIAGNOSIS_FILE_CANDIDATES = [
    "diagnosis_specialty_detail_6.csv",
    "diagnosis_specialty_detail.csv",
    "cohort_diagnoses.csv",
]
RAW_PRESCRIPTION_FILE_CANDIDATES = [
    "cohort_prescriptions.csv",
    "prescriptions.csv",
]


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
            header = pd.read_csv(path, encoding=encoding, nrows=0)
            available_cols = list(header.columns)
            selected_cols = available_cols if usecols is None else [
                col for col in usecols if col in available_cols
            ]
            return pd.read_csv(
                path,
                encoding=encoding,
                usecols=selected_cols,
                low_memory=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path} -> {last_error}") from last_error


def discover_required_files(root_dir: Path) -> dict[str, Path]:
    required_names = {
        "raw_diagnoses": RAW_DIAGNOSIS_FILE_CANDIDATES,
        "cleaned_diagnoses": ["cleaned_diagnosis_specialty_detail_6.csv"],
        "raw_prescriptions": RAW_PRESCRIPTION_FILE_CANDIDATES,
        "cleaned_prescriptions": ["cleaned_prescriptions.csv"],
        "single_cases": "single_specialty_cases.csv",
        "multi_cases": "multi_specialty_cases_v2.csv",
        "case_summary": "case_summary.csv",
        "kb_index": "kb_index.csv",
    }
    discovered: dict[str, Path] = {}
    for key, file_name in required_names.items():
        candidates = file_name if isinstance(file_name, list) else [file_name]
        for candidate in candidates:
            matches = sorted(root_dir.rglob(candidate))
            if matches:
                discovered[key] = matches[0]
                break
    missing = [name for name in required_names if name not in discovered]
    if missing:
        details = {
            "raw_diagnoses": "原始诊断明细文件，建议导出为 diagnosis_specialty_detail_6.csv",
            "raw_prescriptions": "原始处方明细文件，建议导出为 cohort_prescriptions.csv",
        }
        detail_lines = [details[name] for name in missing if name in details]
        raise FileNotFoundError(
            "缺少以下必需文件: "
            + ", ".join(missing)
            + ("\n" + "\n".join(detail_lines) if detail_lines else "")
        )
    return discovered


def rename_first_available_column(
    df: pd.DataFrame,
    target: str,
    candidates: list[str],
) -> pd.DataFrame:
    for candidate in candidates:
        if candidate in df.columns:
            if candidate != target:
                return df.rename(columns={candidate: target})
            return df
    raise KeyError(f"缺少列 {target}，候选列包括: {candidates}")


def normalize_diagnosis_df(df: pd.DataFrame) -> pd.DataFrame:
    df = rename_first_available_column(df, "diagnosis_name", ["diagnosis_name", "long_title"])
    df = rename_first_available_column(df, "specialty_group", ["specialty_group", "specialty_name"])
    return df


def normalize_prescription_df(df: pd.DataFrame) -> pd.DataFrame:
    return rename_first_available_column(df, "drug_name", ["drug_name", "drug"])


def load_data(root_dir: Path) -> dict[str, pd.DataFrame]:
    files = discover_required_files(root_dir)
    kb_index = read_csv_flexible(files["kb_index"])
    if "\ufeffspecialty_name" in kb_index.columns:
        kb_index = kb_index.rename(columns={"\ufeffspecialty_name": "specialty_name"})

    return {
        "raw_diagnoses": normalize_diagnosis_df(
            read_csv_flexible(
                files["raw_diagnoses"],
                usecols=["subject_id", "hadm_id", "long_title", "diagnosis_name", "specialty_group", "specialty_name"],
            )
        ),
        "cleaned_diagnoses": normalize_diagnosis_df(
            read_csv_flexible(
                files["cleaned_diagnoses"],
                usecols=["subject_id", "hadm_id", "long_title", "diagnosis_name", "specialty_group", "specialty_name"],
            )
        ),
        "raw_prescriptions": normalize_prescription_df(
            read_csv_flexible(
                files["raw_prescriptions"],
                usecols=["subject_id", "hadm_id", "drug_name", "drug"],
            )
        ),
        "cleaned_prescriptions": normalize_prescription_df(
            read_csv_flexible(
                files["cleaned_prescriptions"],
                usecols=["subject_id", "hadm_id", "drug_name", "drug"],
            )
        ),
        "single_cases": read_csv_flexible(
            files["single_cases"],
            usecols=["subject_id", "hadm_id", "specialty_group"],
        ),
        "multi_cases": read_csv_flexible(
            files["multi_cases"],
            usecols=["subject_id", "hadm_id"],
        ),
        "case_summary": read_csv_flexible(
            files["case_summary"],
            usecols=["subject_id", "hadm_id"],
        ),
        "kb_index": kb_index,
    }


def add_bar_labels(ax: Any, fmt: str = "{:.0f}") -> None:
    for patch in ax.patches:
        height = patch.get_height()
        if pd.isna(height) or height <= 0:
            continue
        ax.annotate(
            fmt.format(height),
            (patch.get_x() + patch.get_width() / 2, height),
            ha="center",
            va="bottom",
            fontsize=8,
            xytext=(0, 3),
            textcoords="offset points",
        )


def save_current_figure(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def summarize_comparison(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    raw_diagnoses = data["raw_diagnoses"].copy()
    cleaned_diagnoses = data["cleaned_diagnoses"].copy()
    raw_prescriptions = data["raw_prescriptions"].copy()
    cleaned_prescriptions = data["cleaned_prescriptions"].copy()
    single_cases = data["single_cases"].copy().drop_duplicates()
    kb_index = data["kb_index"].copy()

    raw_diag_record_stats = raw_diagnoses.groupby("specialty_group").size().to_dict()

    raw_rx_joined = single_cases.merge(
        raw_prescriptions,
        on=["subject_id", "hadm_id"],
        how="inner",
    )
    raw_prescription_record_stats = raw_rx_joined.groupby("specialty_group").size().to_dict()
    cleaned_rx_joined = single_cases.merge(
        cleaned_prescriptions,
        on=["subject_id", "hadm_id"],
        how="inner",
    )
    cleaned_prescription_record_stats = cleaned_rx_joined.groupby("specialty_group").size().to_dict()

    raw_pairs = (
        single_cases.merge(
            cleaned_diagnoses,
            on=["subject_id", "hadm_id", "specialty_group"],
            how="inner",
        )
        .merge(
            cleaned_prescriptions,
            on=["subject_id", "hadm_id"],
            how="inner",
        )
        .dropna(subset=["diagnosis_name", "drug_name"])
        .groupby(["specialty_group", "diagnosis_name", "drug_name"])
        .size()
        .reset_index(name="cooccurrence")
    )
    raw_pair_stats = raw_pairs.groupby("specialty_group").size().to_dict()

    rows: list[dict[str, Any]] = []
    for specialty in SPECIALTIES:
        matched = kb_index[kb_index["specialty_name"] == specialty]
        if matched.empty:
            continue
        entry = matched.iloc[0]
        disease_catalog = read_csv_flexible(Path(entry["disease_catalog"]))
        disease_drug_map = read_csv_flexible(Path(entry["disease_drug_map"]))
        core_diagnosis_names = set(
            disease_catalog.loc[
                disease_catalog["disease_role"] == "核心病种",
                "diagnosis_name",
            ].dropna().astype(str)
        )
        core_coverage_records = int(
            raw_diagnoses[
                (raw_diagnoses["specialty_group"] == specialty)
                & (raw_diagnoses["diagnosis_name"].astype(str).isin(core_diagnosis_names))
            ].shape[0]
        )

        rows.append(
            {
                "specialty_name": specialty,
                "raw_diagnosis_records": int(raw_diag_record_stats.get(specialty, 0)),
                "core_diagnosis_coverage_records": core_coverage_records,
                "raw_prescription_records": int(raw_prescription_record_stats.get(specialty, 0)),
                "cleaned_prescription_records": int(cleaned_prescription_record_stats.get(specialty, 0)),
                "raw_disease_drug_pairs": int(raw_pair_stats.get(specialty, 0)),
                "structured_map_entries": int(len(disease_drug_map.index)),
                "usable_map_entries": int((disease_drug_map["mapping_quality"] == "可直接使用").sum()),
            }
        )

    return pd.DataFrame(rows)


def plot_grouped_comparison(
    df: pd.DataFrame,
    columns: list[str],
    labels: list[str],
    colors: list[str],
    title: str,
    ylabel: str,
    output_path: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6))
    x = range(len(df))
    width = 0.22 if len(columns) == 3 else 0.35

    offsets = []
    if len(columns) == 3:
        offsets = [-width, 0, width]
    elif len(columns) == 2:
        offsets = [-width / 2, width / 2]
    else:
        offsets = [0] * len(columns)

    for offset, column, label, color in zip(offsets, columns, labels, colors):
        ax.bar(
            [i + offset for i in x],
            df[column],
            width=width,
            label=label,
            color=color,
        )

    ax.set_title(title)
    ax.set_xlabel("专科")
    ax.set_ylabel(ylabel)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["specialty_name"], rotation=20)
    ax.legend()
    add_bar_labels(ax)
    save_current_figure(output_path)
    return output_path


def _annotate_bars_conditionally(
    ax: Any,
    container: Any,
    values: pd.Series,
    threshold: float,
    place_above_threshold: bool,
) -> None:
    for patch, value in zip(container.patches, values):
        if pd.isna(value) or value <= 0:
            continue
        should_draw = value > threshold if place_above_threshold else value <= threshold
        if not should_draw:
            continue
        ax.annotate(
            f"{int(value)}",
            (patch.get_x() + patch.get_width() / 2, min(value, ax.get_ylim()[1])),
            ha="center",
            va="bottom",
            fontsize=8,
            xytext=(0, 3),
            textcoords="offset points",
        )


def plot_grouped_comparison_broken_axis(
    df: pd.DataFrame,
    columns: list[str],
    labels: list[str],
    colors: list[str],
    title: str,
    ylabel: str,
    output_path: Path,
) -> Path:
    raw_max = float(df[columns[0]].max())
    small_max = float(df[columns[1:]].max().max())
    if raw_max <= 0 or small_max >= raw_max * 0.6:
        return plot_grouped_comparison(df, columns, labels, colors, title.replace("（断轴）", ""), ylabel, output_path)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(11, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.4], "hspace": 0.06},
    )

    x = list(range(len(df)))
    width = 0.22 if len(columns) == 3 else 0.35
    offsets = [-width, 0, width] if len(columns) == 3 else [-width / 2, width / 2]

    bottom_max = max(small_max * 1.8, 25.0)
    top_min = max(bottom_max * 1.2, float(df[columns[0]].min()) * 0.85)
    top_max = raw_max * 1.1

    top_handles = []
    for offset, column, label, color in zip(offsets, columns, labels, colors):
        bars_top = ax_top.bar(
            [i + offset for i in x],
            df[column],
            width=width,
            label=label,
            color=color,
        )
        ax_bottom.bar(
            [i + offset for i in x],
            df[column],
            width=width,
            label=label,
            color=color,
        )
        top_handles.append((bars_top, df[column]))

    ax_top.set_ylim(top_min, top_max)
    ax_bottom.set_ylim(0, bottom_max)

    ax_top.spines["bottom"].set_visible(False)
    ax_bottom.spines["top"].set_visible(False)
    ax_top.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    ax_bottom.set_xticks(x)
    ax_bottom.set_xticklabels(df["specialty_name"], rotation=20)

    ax_top.set_title(title)
    ax_bottom.set_xlabel("专科")
    ax_bottom.set_ylabel(ylabel)
    ax_top.legend()

    d = 0.008
    kwargs = dict(transform=ax_top.transAxes, color="k", clip_on=False, linewidth=1)
    ax_top.plot((-d, +d), (-d, +d), **kwargs)
    ax_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)
    kwargs.update(transform=ax_bottom.transAxes)
    ax_bottom.plot((-d, +d), (1 - d, 1 + d), **kwargs)
    ax_bottom.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

    for bars, values in top_handles:
        _annotate_bars_conditionally(ax_top, bars, values, bottom_max, True)
    for container, column in zip(ax_bottom.containers, columns):
        _annotate_bars_conditionally(ax_bottom, container, df[column], bottom_max, False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    return output_path


def plot_case_flow(case_summary: pd.DataFrame, single_cases: pd.DataFrame, multi_cases: pd.DataFrame, output_path: Path) -> Path:
    labels = ["病例总表", "单专科病例", "多专科病例"]
    values = [len(case_summary.index), len(single_cases.index), len(multi_cases.index)]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, values, color=["#2563EB", "#10B981", "#F59E0B"])
    ax.set_title("预处理后病例分层结果")
    ax.set_ylabel("病例数")
    add_bar_labels(ax)
    save_current_figure(output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="绘制原始输入与处理后结果的对比图。"
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=ROOT_DIR,
        help="项目根目录，默认是脚本所在目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="图片输出目录，默认是 figures/raw_vs_processed。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()

    data = load_data(args.root_dir)
    summary_df = summarize_comparison(data)
    output_dir = args.output_dir

    saved_files: list[Path] = []
    saved_files.append(
        plot_case_flow(
            data["case_summary"],
            data["single_cases"],
            data["multi_cases"],
            output_dir / "01_case_flow_after_preprocessing.png",
        )
    )
    saved_files.append(
        plot_grouped_comparison_broken_axis(
            summary_df,
            columns=["raw_diagnosis_records", "core_diagnosis_coverage_records"],
            labels=["原始诊断记录数", "核心候选覆盖记录数"],
            colors=["#94A3B8", "#3B82F6"],
            title="各专科诊断规模：原始记录 vs 核心候选覆盖记录（断轴）",
            ylabel="数量",
            output_path=output_dir / "02_diagnosis_before_after.png",
        )
    )
    saved_files.append(
        plot_grouped_comparison_broken_axis(
            summary_df,
            columns=["raw_prescription_records", "cleaned_prescription_records"],
            labels=["原始处方记录数", "清洗后处方记录数"],
            colors=["#94A3B8", "#F59E0B"],
            title="各专科药物规模：原始处方记录 vs 清洗后记录（断轴）",
            ylabel="处方记录数",
            output_path=output_dir / "03_drug_before_after.png",
        )
    )
    saved_files.append(
        plot_grouped_comparison(
            summary_df,
            columns=["raw_disease_drug_pairs", "structured_map_entries", "usable_map_entries"],
            labels=["清洗后病药共现对数", "结构化映射条目数", "可直接使用映射数"],
            colors=["#94A3B8", "#8B5CF6", "#14B8A6"],
            title="各专科病药关系：清洗后共现 vs 结构化映射",
            ylabel="关系条目数",
            output_path=output_dir / "04_mapping_before_after.png",
        )
    )

    print("原始数据与处理后结果对比图绘制完成，输出文件如下：")
    for path in saved_files:
        print(path)


if __name__ == "__main__":
    main()
