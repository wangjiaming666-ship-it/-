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
        "diagnoses": "cleaned_diagnosis_specialty_detail_6.csv",
        "prescriptions": "cleaned_prescriptions.csv",
        "single_cases": "single_specialty_cases.csv",
        "multi_cases": "multi_specialty_cases_v2.csv",
        "case_summary": "case_summary.csv",
        "kb_index": "kb_index.csv",
    }
    discovered: dict[str, Path] = {}
    for key, file_name in required_names.items():
        matches = sorted(root_dir.rglob(file_name))
        if matches:
            discovered[key] = matches[0]
    missing = [name for name in required_names if name not in discovered]
    if missing:
        raise FileNotFoundError(f"缺少以下必需文件: {missing}")
    return discovered


def load_data(root_dir: Path) -> dict[str, pd.DataFrame]:
    files = discover_required_files(root_dir)
    kb_index = read_csv_flexible(files["kb_index"])
    if "\ufeffspecialty_name" in kb_index.columns:
        kb_index = kb_index.rename(columns={"\ufeffspecialty_name": "specialty_name"})

    return {
        "diagnoses": read_csv_flexible(
            files["diagnoses"],
            usecols=["subject_id", "hadm_id", "long_title", "specialty_group"],
        ),
        "prescriptions": read_csv_flexible(
            files["prescriptions"],
            usecols=["subject_id", "hadm_id", "drug_name"],
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
    diagnoses = data["diagnoses"].copy()
    prescriptions = data["prescriptions"].copy()
    single_cases = data["single_cases"].copy().drop_duplicates()
    kb_index = data["kb_index"].copy()

    raw_diag_stats = (
        diagnoses.groupby("specialty_group")["long_title"]
        .nunique()
        .to_dict()
    )

    rx_joined = single_cases.merge(
        prescriptions,
        on=["subject_id", "hadm_id"],
        how="inner",
    )
    raw_drug_stats = (
        rx_joined.groupby("specialty_group")["drug_name"]
        .nunique()
        .to_dict()
    )

    raw_pairs = (
        single_cases.merge(
            diagnoses.rename(columns={"long_title": "diagnosis_name"}),
            on=["subject_id", "hadm_id", "specialty_group"],
            how="inner",
        )
        .merge(
            prescriptions,
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
        drug_catalog = read_csv_flexible(Path(entry["drug_catalog"]))
        disease_drug_map = read_csv_flexible(Path(entry["disease_drug_map"]))

        rows.append(
            {
                "specialty_name": specialty,
                "raw_distinct_diagnoses": int(raw_diag_stats.get(specialty, 0)),
                "retained_diseases": int((disease_catalog["disease_role"] != "应剔除项").sum()),
                "core_diseases": int((disease_catalog["disease_role"] == "核心病种").sum()),
                "raw_distinct_drugs": int(raw_drug_stats.get(specialty, 0)),
                "retained_drugs": int((drug_catalog["drug_role"] != "通用辅助药").sum()),
                "core_drugs": int((drug_catalog["drug_role"] == "核心治疗药").sum()),
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
        plot_grouped_comparison(
            summary_df,
            columns=["raw_distinct_diagnoses", "retained_diseases", "core_diseases"],
            labels=["预处理输入诊断种类数", "处理后保留病种数", "核心病种数"],
            colors=["#94A3B8", "#3B82F6", "#10B981"],
            title="各专科诊断规模：原始输入 vs 处理后结果",
            ylabel="诊断条目数",
            output_path=output_dir / "02_diagnosis_before_after.png",
        )
    )
    saved_files.append(
        plot_grouped_comparison(
            summary_df,
            columns=["raw_distinct_drugs", "retained_drugs", "core_drugs"],
            labels=["预处理输入药物种类数", "处理后保留药物数", "核心治疗药数"],
            colors=["#94A3B8", "#F59E0B", "#EF4444"],
            title="各专科药物规模：原始输入 vs 处理后结果",
            ylabel="药物条目数",
            output_path=output_dir / "03_drug_before_after.png",
        )
    )
    saved_files.append(
        plot_grouped_comparison(
            summary_df,
            columns=["raw_disease_drug_pairs", "structured_map_entries", "usable_map_entries"],
            labels=["原始病药共现对数", "结构化映射条目数", "可直接使用映射数"],
            colors=["#94A3B8", "#8B5CF6", "#14B8A6"],
            title="各专科病药关系：原始共现 vs 处理后映射",
            ylabel="关系条目数",
            output_path=output_dir / "04_mapping_before_after.png",
        )
    )

    print("原始数据与处理后结果对比图绘制完成，输出文件如下：")
    for path in saved_files:
        print(path)


if __name__ == "__main__":
    main()
