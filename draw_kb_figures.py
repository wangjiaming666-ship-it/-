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
    text = path.read_text(encoding="utf-8")
    sanitized = (
        text.replace(": NaN", ": null")
        .replace(": Infinity", ": null")
        .replace(": -Infinity", ": null")
    )
    return json.loads(sanitized)


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
        disease_drug_map = read_csv_flexible(Path(entry["disease_drug_map"]))
        risk_rules = read_json_flexible(Path(entry["risk_rules"]))
        example_cases = read_json_flexible(Path(entry["example_cases"]))

        disease_role_counts = (
            disease_catalog["disease_role"].fillna("未标注").value_counts().to_dict()
        )
        drug_role_counts = (
            drug_catalog["drug_role"].fillna("未标注").value_counts().to_dict()
        )
        mapping_quality_counts = (
            disease_drug_map["mapping_quality"].fillna("未标注").value_counts().to_dict()
        )

        single_examples = example_cases.get("single_specialty_examples", [])
        multi_examples = example_cases.get("multi_specialty_examples", [])

        rows.append(
            {
                "specialty_name": specialty,
                "核心病种": disease_role_counts.get("核心病种", 0),
                "背景共病": disease_role_counts.get("背景共病", 0),
                "应剔除项": disease_role_counts.get("应剔除项", 0),
                "核心治疗药": drug_role_counts.get("核心治疗药", 0),
                "支持治疗药": drug_role_counts.get("支持治疗药", 0),
                "通用辅助药": drug_role_counts.get("通用辅助药", 0),
                "候选证据充分": mapping_quality_counts.get("候选证据充分", 0)
                + mapping_quality_counts.get("可直接使用", 0),
                "仅保留低优先级方案": mapping_quality_counts.get("仅保留低优先级方案", 0),
                "仅用于诊断评估": mapping_quality_counts.get("仅用于诊断评估", 0)
                + mapping_quality_counts.get("背景共病", 0),
                "风险规则数": len(risk_rules) if isinstance(risk_rules, list) else 0,
                "单专科示例数": len(single_examples) if isinstance(single_examples, list) else 0,
                "多专科示例数": len(multi_examples) if isinstance(multi_examples, list) else 0,
            }
        )
    return pd.DataFrame(rows)


def plot_stacked_bar(
    df: pd.DataFrame,
    columns: list[str],
    title: str,
    ylabel: str,
    colors: list[str],
    output_path: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = pd.Series([0] * len(df), index=df.index, dtype=float)
    for column, color in zip(columns, colors):
        ax.bar(df["specialty_name"], df[column], bottom=bottom, label=column, color=color)
        bottom = bottom + df[column]

    ax.set_title(title)
    ax.set_xlabel("专科")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.legend()

    total_heights = df[columns].sum(axis=1)
    for x, height in zip(df["specialty_name"], total_heights):
        ax.annotate(
            f"{int(height)}",
            (x, height),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 4),
            textcoords="offset points",
        )

    save_current_figure(output_path)
    return output_path


def plot_risk_rules_and_examples(df: pd.DataFrame, output_path: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].bar(df["specialty_name"], df["风险规则数"], color="#8B5CF6")
    axes[0].set_title("六专科风险规则数量分布")
    axes[0].set_xlabel("专科")
    axes[0].set_ylabel("规则数量")
    axes[0].tick_params(axis="x", rotation=20)
    add_bar_labels(axes[0])

    x = range(len(df))
    width = 0.35
    axes[1].bar(
        [i - width / 2 for i in x],
        df["单专科示例数"],
        width=width,
        label="单专科示例",
        color="#10B981",
    )
    axes[1].bar(
        [i + width / 2 for i in x],
        df["多专科示例数"],
        width=width,
        label="多专科示例",
        color="#F59E0B",
    )
    axes[1].set_title("六专科示例病例数量分布")
    axes[1].set_xlabel("专科")
    axes[1].set_ylabel("示例数量")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(df["specialty_name"], rotation=20)
    axes[1].legend()
    add_bar_labels(axes[1])

    save_current_figure(output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 knowledge_base 目录绘制知识库生成结果图。"
    )
    parser.add_argument(
        "--kb-dir",
        type=Path,
        default=KB_DIR,
        help="知识库根目录，默认是项目下的 knowledge_base。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="图片输出目录，默认是 figures/knowledge_base。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()

    kb_index = load_kb_index(args.kb_dir)
    summary_df = summarize_kb(kb_index)
    if summary_df.empty:
        raise RuntimeError("未能从知识库索引中读取到任何专科数据。")

    output_dir = args.output_dir
    saved_files: list[Path] = []
    saved_files.append(
        plot_stacked_bar(
            summary_df,
            columns=["核心病种", "背景共病", "应剔除项"],
            title="六专科病种角色分布",
            ylabel="病种条目数",
            colors=["#2563EB", "#10B981", "#EF4444"],
            output_path=output_dir / "01_disease_role_distribution.png",
        )
    )
    saved_files.append(
        plot_stacked_bar(
            summary_df,
            columns=["核心治疗药", "支持治疗药", "通用辅助药"],
            title="六专科药物角色分布",
            ylabel="药物条目数",
            colors=["#F59E0B", "#6366F1", "#9CA3AF"],
            output_path=output_dir / "02_drug_role_distribution.png",
        )
    )
    saved_files.append(
        plot_stacked_bar(
            summary_df,
            columns=["候选证据充分", "仅保留低优先级方案", "仅用于诊断评估"],
            title="六专科病药共现证据分布",
            ylabel="映射条目数",
            colors=["#14B8A6", "#F97316", "#A855F7"],
            output_path=output_dir / "03_mapping_quality_distribution.png",
        )
    )
    saved_files.append(
        plot_risk_rules_and_examples(
            summary_df,
            output_path=output_dir / "04_risk_rules_and_examples.png",
        )
    )

    print("知识库图片绘制完成，输出文件如下：")
    for path in saved_files:
        print(path)


if __name__ == "__main__":
    main()
