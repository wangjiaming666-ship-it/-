from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "figures" / "processed_data"
DEFAULT_SCHEMA = "thesis"

SPECIALTIES = [
    "心血管",
    "神经",
    "呼吸",
    "肾内/泌尿",
    "内分泌/代谢",
    "消化",
]

SPECIALTY_SLUGS = {
    "心血管": "cardiology",
    "神经": "neurology",
    "呼吸": "respiratory",
    "肾内/泌尿": "nephrology",
    "内分泌/代谢": "endocrinology",
    "消化": "gastroenterology",
}

REQUIRED_CSVS = {
    "single_specialty_cases": "single_specialty_cases.csv",
    "multi_specialty_cases_v2": "multi_specialty_cases_v2.csv",
    "specialty_top_diagnoses_clean": "specialty_top_diagnoses_clean.csv",
    "specialty_top_drugs_clean": "specialty_top_drugs_clean.csv",
    "cohort_first24h_labs": "cohort_first24h_labs.csv",
}

LAB_COLUMNS = [
    "creatinine_24h",
    "bun_24h",
    "potassium_24h",
    "sodium_24h",
    "glucose_24h",
    "inr_24h",
    "bilirubin_total_24h",
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


def discover_csv_files(root_dir: Path) -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    for key, file_name in REQUIRED_CSVS.items():
        matches = sorted(root_dir.rglob(file_name))
        if matches:
            discovered[key] = matches[0]
    return discovered


def load_csv_mode(root_dir: Path) -> dict[str, pd.DataFrame]:
    discovered = discover_csv_files(root_dir)
    missing = [name for name in REQUIRED_CSVS if name not in discovered]
    if missing:
        missing_files = [REQUIRED_CSVS[name] for name in missing]
        raise FileNotFoundError(
            "未找到以下处理后 CSV 文件: " + ", ".join(missing_files)
        )

    return {
        "single_specialty_cases": read_csv_flexible(
            discovered["single_specialty_cases"],
            usecols=["subject_id", "hadm_id", "specialty_group"],
        ),
        "multi_specialty_cases_v2": read_csv_flexible(
            discovered["multi_specialty_cases_v2"],
            usecols=["subject_id", "hadm_id", "specialty_cnt", "specialty_list"],
        ),
        "specialty_top_diagnoses_clean": read_csv_flexible(
            discovered["specialty_top_diagnoses_clean"],
            usecols=["specialty_group", "diagnosis_name", "freq"],
        ),
        "specialty_top_drugs_clean": read_csv_flexible(
            discovered["specialty_top_drugs_clean"],
            usecols=["specialty_group", "drug_name", "freq"],
        ),
        "cohort_first24h_labs": read_csv_flexible(
            discovered["cohort_first24h_labs"],
            usecols=["subject_id", "hadm_id", *LAB_COLUMNS],
        ),
    }


def import_postgres_driver() -> tuple[Any, str]:
    for module_name in ("psycopg", "psycopg2"):
        try:
            return importlib.import_module(module_name), module_name
        except ImportError:
            continue
    raise ImportError("未安装 psycopg 或 psycopg2，无法直接连接 PostgreSQL。")


def run_postgres_query(dsn: str, sql: str) -> pd.DataFrame:
    driver, driver_name = import_postgres_driver()
    if driver_name == "psycopg":
        with driver.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
    else:
        with driver.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
    return pd.DataFrame(rows, columns=columns)


def load_postgres_mode(dsn: str, schema: str) -> dict[str, pd.DataFrame]:
    return {
        "single_specialty_counts": run_postgres_query(
            dsn,
            f"""
            SELECT specialty_group, COUNT(*) AS case_cnt
            FROM {schema}.single_specialty_cases
            GROUP BY specialty_group
            ORDER BY case_cnt DESC
            """,
        ),
        "multi_specialty_counts": run_postgres_query(
            dsn,
            f"""
            SELECT specialty_cnt, COUNT(*) AS case_cnt
            FROM {schema}.multi_specialty_cases_v2
            GROUP BY specialty_cnt
            ORDER BY specialty_cnt
            """,
        ),
        "specialty_top_diagnoses_clean": run_postgres_query(
            dsn,
            f"""
            SELECT specialty_group, diagnosis_name, freq
            FROM {schema}.specialty_top_diagnoses_clean
            """,
        ),
        "specialty_top_drugs_clean": run_postgres_query(
            dsn,
            f"""
            SELECT specialty_group, drug_name, freq
            FROM {schema}.specialty_top_drugs_clean
            """,
        ),
        "lab_coverage": run_postgres_query(
            dsn,
            f"""
            SELECT lab_name,
                   non_null_cnt,
                   ROUND(non_null_cnt * 100.0 / NULLIF(total_cnt, 0), 2) AS coverage_pct
            FROM (
                SELECT 'creatinine_24h' AS lab_name, COUNT(creatinine_24h) AS non_null_cnt, COUNT(*) AS total_cnt FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'bun_24h', COUNT(bun_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'potassium_24h', COUNT(potassium_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'sodium_24h', COUNT(sodium_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'glucose_24h', COUNT(glucose_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'inr_24h', COUNT(inr_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
                UNION ALL
                SELECT 'bilirubin_total_24h', COUNT(bilirubin_total_24h), COUNT(*) FROM {schema}.cohort_first24h_labs
            ) t
            ORDER BY coverage_pct DESC, lab_name
            """,
        ),
    }


def prepare_csv_aggregates(raw_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    single_cases = raw_data["single_specialty_cases"].copy()
    multi_cases = raw_data["multi_specialty_cases_v2"].copy()
    top_diagnoses = raw_data["specialty_top_diagnoses_clean"].copy()
    top_drugs = raw_data["specialty_top_drugs_clean"].copy()
    labs = raw_data["cohort_first24h_labs"].copy()

    single_specialty_counts = (
        single_cases.groupby("specialty_group", dropna=False)
        .size()
        .reset_index(name="case_cnt")
        .sort_values("case_cnt", ascending=False)
    )

    multi_cases["specialty_cnt"] = pd.to_numeric(
        multi_cases["specialty_cnt"], errors="coerce"
    )
    multi_specialty_counts = (
        multi_cases.groupby("specialty_cnt", dropna=False)
        .size()
        .reset_index(name="case_cnt")
        .dropna(subset=["specialty_cnt"])
        .sort_values("specialty_cnt")
    )

    top_diagnoses["freq"] = pd.to_numeric(top_diagnoses["freq"], errors="coerce")
    top_drugs["freq"] = pd.to_numeric(top_drugs["freq"], errors="coerce")

    lab_rows: list[dict[str, Any]] = []
    total_cnt = len(labs.index)
    for lab_name in LAB_COLUMNS:
        if lab_name not in labs.columns:
            continue
        non_null_cnt = int(labs[lab_name].notna().sum())
        coverage_pct = round(non_null_cnt * 100.0 / total_cnt, 2) if total_cnt else 0.0
        lab_rows.append(
            {
                "lab_name": lab_name,
                "non_null_cnt": non_null_cnt,
                "coverage_pct": coverage_pct,
            }
        )
    lab_coverage = pd.DataFrame(lab_rows).sort_values(
        ["coverage_pct", "lab_name"], ascending=[False, True]
    )

    return {
        "single_specialty_counts": single_specialty_counts,
        "multi_specialty_counts": multi_specialty_counts,
        "specialty_top_diagnoses_clean": top_diagnoses,
        "specialty_top_drugs_clean": top_drugs,
        "lab_coverage": lab_coverage,
    }


def add_bar_labels(ax: Any, fmt: str = "{:.0f}") -> None:
    for patch in ax.patches:
        height = patch.get_height()
        if pd.isna(height):
            continue
        ax.annotate(
            fmt.format(height),
            (patch.get_x() + patch.get_width() / 2, height),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 4),
            textcoords="offset points",
        )


def save_current_figure(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_single_specialty_distribution(df: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(df["specialty_group"], df["case_cnt"], color="#3B82F6")
    ax.set_title("六专科单专科病例数量分布")
    ax.set_xlabel("专科")
    ax.set_ylabel("病例数")
    ax.tick_params(axis="x", rotation=20)
    add_bar_labels(ax)
    output_path = output_dir / "01_single_specialty_case_distribution.png"
    save_current_figure(output_path)
    return output_path


def plot_multi_specialty_complexity(df: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(df["specialty_cnt"].astype(int).astype(str), df["case_cnt"], color="#10B981")
    ax.set_title("多专科病例复杂度分布")
    ax.set_xlabel("涉及专科数量")
    ax.set_ylabel("病例数")
    add_bar_labels(ax)
    output_path = output_dir / "02_multi_specialty_complexity_distribution.png"
    save_current_figure(output_path)
    return output_path


def plot_top_items_by_specialty(
    df: pd.DataFrame,
    specialty_col: str,
    item_col: str,
    value_col: str,
    title_prefix: str,
    filename_prefix: str,
    output_dir: Path,
    top_n: int = 10,
) -> list[Path]:
    output_paths: list[Path] = []
    for specialty in SPECIALTIES:
        sub = df[df[specialty_col] == specialty].copy()
        if sub.empty:
            continue
        sub = sub.sort_values(value_col, ascending=False).head(top_n)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(sub[item_col], sub[value_col], color="#F59E0B")
        ax.set_title(f"{specialty}{title_prefix}")
        ax.set_xlabel("频次")
        ax.set_ylabel("")
        ax.invert_yaxis()
        for patch in ax.patches:
            width = patch.get_width()
            ax.annotate(
                f"{int(width)}",
                (width, patch.get_y() + patch.get_height() / 2),
                ha="left",
                va="center",
                fontsize=9,
                xytext=(4, 0),
                textcoords="offset points",
            )
        slug = SPECIALTY_SLUGS.get(specialty, specialty)
        output_path = output_dir / f"{filename_prefix}_{slug}.png"
        save_current_figure(output_path)
        output_paths.append(output_path)
    return output_paths


def plot_lab_coverage(df: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["lab_name"], df["coverage_pct"], color="#8B5CF6")
    ax.set_title("关键检验指标覆盖率")
    ax.set_xlabel("检验指标")
    ax.set_ylabel("覆盖率 (%)")
    ax.set_ylim(0, max(100, float(df["coverage_pct"].max()) + 5))
    ax.tick_params(axis="x", rotation=25)
    add_bar_labels(ax, fmt="{:.2f}")
    output_path = output_dir / "05_key_lab_coverage.png"
    save_current_figure(output_path)
    return output_path


def resolve_data_source(
    input_mode: str, root_dir: Path, pg_dsn: str | None, schema: str
) -> dict[str, pd.DataFrame]:
    if input_mode == "csv":
        return prepare_csv_aggregates(load_csv_mode(root_dir))

    if input_mode == "postgres":
        if not pg_dsn:
            raise ValueError("PostgreSQL 模式需要提供 --pg-dsn。")
        return load_postgres_mode(pg_dsn, schema)

    discovered = discover_csv_files(root_dir)
    if len(discovered) == len(REQUIRED_CSVS):
        return prepare_csv_aggregates(load_csv_mode(root_dir))

    if pg_dsn:
        return load_postgres_mode(pg_dsn, schema)

    missing_files = [REQUIRED_CSVS[name] for name in REQUIRED_CSVS if name not in discovered]
    raise FileNotFoundError(
        "自动模式下未找到完整 CSV，也未提供 PostgreSQL 连接。"
        f"\n缺少文件: {', '.join(missing_files)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按序绘制处理后论文数据图表，输出为 PNG 图片。"
    )
    parser.add_argument(
        "--input-mode",
        choices=["auto", "csv", "postgres"],
        default="auto",
        help="数据来源模式：自动检测、本地 CSV 或 PostgreSQL。",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=ROOT_DIR,
        help="CSV 搜索根目录，默认是脚本所在目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="图片输出目录，默认是 figures/processed_data。",
    )
    parser.add_argument(
        "--pg-dsn",
        type=str,
        default=None,
        help='PostgreSQL 连接串，例如：host=localhost port=5432 dbname=mimiciv user=wjm password=123456',
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=DEFAULT_SCHEMA,
        help="PostgreSQL 中存放处理后表的 schema，默认 thesis。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()

    data = resolve_data_source(
        input_mode=args.input_mode,
        root_dir=args.root_dir,
        pg_dsn=args.pg_dsn,
        schema=args.schema,
    )

    output_dir = args.output_dir
    saved_files: list[Path] = []
    saved_files.append(plot_single_specialty_distribution(data["single_specialty_counts"], output_dir))
    saved_files.append(plot_multi_specialty_complexity(data["multi_specialty_counts"], output_dir))
    saved_files.extend(
        plot_top_items_by_specialty(
            df=data["specialty_top_diagnoses_clean"],
            specialty_col="specialty_group",
            item_col="diagnosis_name",
            value_col="freq",
            title_prefix=" Top10 诊断分布",
            filename_prefix="03_top_diagnoses",
            output_dir=output_dir,
        )
    )
    saved_files.extend(
        plot_top_items_by_specialty(
            df=data["specialty_top_drugs_clean"],
            specialty_col="specialty_group",
            item_col="drug_name",
            value_col="freq",
            title_prefix=" Top10 药物分布",
            filename_prefix="04_top_drugs",
            output_dir=output_dir,
        )
    )
    saved_files.append(plot_lab_coverage(data["lab_coverage"], output_dir))

    print("图片绘制完成，输出文件如下：")
    for path in saved_files:
        print(path)


if __name__ == "__main__":
    main()
