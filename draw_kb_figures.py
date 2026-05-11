from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
KB_DIR = ROOT_DIR / "knowledge_base"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "figures" / "knowledge_base"

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


def read_csv_flexible(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path} -> {last_error}") from last_error


def read_json_flexible(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
            fontsize=9,
            xytext=(0, 3),
            textcoords="offset points",
        )


def save_current_figure(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def load_kb_index(kb_dir: Path) -> pd.DataFrame:
    kb_index_path = kb_dir / "kb_index.csv"
    if not kb_index_path.exists():
        raise FileNotFoundError(f"未找到知识库索引文件: {kb_index_path}")
    kb_index = read_csv_flexible(kb_index_path)
    if "specialty_name" not in kb_index.columns and "\ufeffspecialty_name" in kb_index.columns:
        kb_index = kb_index.rename(columns={"\ufeffspecialty_name": "specialty_name"})
    return kb_index


def summarize_kb(kb_index: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for specialty in SPECIALTIES:
        matched = kb_index[kb_index["specialty_name"] == specialty]
        if matched.empty:
            continue
        entry = matched.iloc[0]
        disease_catalog = read_csv_flexible(Path(entry["disease_catalog"]))
        drug_catalog = read_csv_flexible(Path(entry["drug_catalog"]))
        risk_rules = read_json_flexible(Path(entry["risk_rules"]))
        role_counts = drug_catalog["treatment_role"].fillna("未标注").value_counts().to_dict()
        rows.append(
            {
                "specialty_name": specialty,
                "疾病诊断知识条目": int(len(disease_catalog.index)),
                "疾病直接治疗": int(role_counts.get("disease_directed_therapy", 0)),
                "风险控制治疗": int(role_counts.get("risk_modifying_therapy", 0)),
                "支持/对症治疗": int(role_counts.get("supportive_or_symptomatic_therapy", 0)),
                "住院通用药物": int(role_counts.get("general_inpatient_medication", 0)),
                "治疗风险规则": len(risk_rules) if isinstance(risk_rules, list) else 0,
            }
        )
    return pd.DataFrame(rows)


def plot_single_bar(df: pd.DataFrame, column: str, title: str, ylabel: str, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["specialty_name"], df[column], color="#2563EB")
    ax.set_title(title)
    ax.set_xlabel("专科")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    add_bar_labels(ax)
    save_current_figure(output_path)
    return output_path


def plot_stacked_bar(
    df: pd.DataFrame,
    columns: list[str],
    title: str,
    ylabel: str,
    output_path: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#F59E0B", "#6366F1", "#10B981", "#9CA3AF"]
    bottom = pd.Series([0] * len(df), index=df.index, dtype=float)
    for column, color in zip(columns, colors):
        ax.bar(df["specialty_name"], df[column], bottom=bottom, label=column, color=color)
        bottom = bottom + df[column]

    ax.set_title(title)
    ax.set_xlabel("专科")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    add_bar_labels(ax)
    save_current_figure(output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据 knowledge_base 目录绘制三类核心知识库图。")
    parser.add_argument("--kb-dir", type=Path, default=KB_DIR, help="知识库根目录。")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="图片输出目录。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()
    kb_index = load_kb_index(args.kb_dir)
    summary_df = summarize_kb(kb_index)
    if summary_df.empty:
        raise RuntimeError("未能从知识库索引中读取到任何专科数据。")

    output_dir = args.output_dir
    saved_files = [
        plot_single_bar(
            summary_df,
            "疾病诊断知识条目",
            "六专科疾病诊断知识条目数",
            "疾病知识条目数",
            output_dir / "01_disease_diagnosis_knowledge.png",
        ),
        plot_stacked_bar(
            summary_df,
            ["疾病直接治疗", "风险控制治疗", "支持/对症治疗", "住院通用药物"],
            "六专科公开药物功能知识分布",
            "药物功能条目数",
            output_dir / "02_drug_function_knowledge.png",
        ),
        plot_single_bar(
            summary_df,
            "治疗风险规则",
            "六专科外部治疗风险规则数量",
            "风险规则数",
            output_dir / "03_treatment_risk_rules.png",
        ),
    ]

    print("知识库图片绘制完成，输出文件如下：")
    for path in saved_files:
        print(path)


if __name__ == "__main__":
    main()
