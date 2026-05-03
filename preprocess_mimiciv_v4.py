from __future__ import annotations

import argparse
import csv
import importlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SQL_FILE = ROOT_DIR / "sql" / "01_extract_mimiciv_v4_cohort.sql"
DEFAULT_MATURE_SQL_FILE = ROOT_DIR / "sql" / "02_mature_clinical_features_navicat.sql"

BASE_EXPORT_TABLES = [
    "cohort_admissions",
    "cohort_diagnoses",
    "diagnosis_specialty_detail_6",
    "cohort_prescriptions",
    "cleaned_diagnosis_specialty_detail_6",
    "cleaned_prescriptions",
    "cohort_first24h_labs",
    "case_summary",
    "single_specialty_cases",
    "multi_specialty_cases_v2",
    "specialty_top_diagnoses_clean",
    "specialty_top_drugs_clean",
]

MATURE_EXPORT_TABLES = [
    "history_diagnoses",
    "past_history_flags",
    "comorbidity_summary",
    "cohort_first24h_vitals",
    "procedure_features",
    "microbiology_features",
    "icu_features",
    "outcome_features",
    "case_summary_mature",
]

REQUIRED_COLUMNS = {
    "single_specialty_cases": {"subject_id", "hadm_id", "specialty_group"},
    "multi_specialty_cases_v2": {"subject_id", "hadm_id", "specialty_cnt", "specialty_list"},
    "cleaned_diagnosis_specialty_detail_6": {
        "subject_id",
        "hadm_id",
        "seq_num",
        "icd_version",
        "icd_code",
        "long_title",
        "specialty_group",
    },
    "cleaned_prescriptions": {"subject_id", "hadm_id", "drug_name"},
    "specialty_top_diagnoses_clean": {"specialty_group", "diagnosis_name", "freq"},
    "cohort_first24h_labs": {
        "subject_id",
        "hadm_id",
        "creatinine_24h",
        "bun_24h",
        "potassium_24h",
        "sodium_24h",
        "glucose_24h",
        "inr_24h",
        "bilirubin_total_24h",
    },
    "past_history_flags": {
        "subject_id",
        "hadm_id",
        "history_hypertension",
        "history_diabetes",
        "history_heart_failure",
        "history_coronary_disease",
        "history_stroke",
        "history_copd",
        "history_chronic_kidney_disease",
        "history_chronic_liver_disease",
        "history_malignancy",
    },
    "comorbidity_summary": {"subject_id", "hadm_id", "comorbidity_count", "comorbidity_list"},
    "cohort_first24h_vitals": {
        "subject_id",
        "hadm_id",
        "heart_rate_mean_24h",
        "respiratory_rate_mean_24h",
        "temperature_f_mean_24h",
        "spo2_min_24h",
        "sbp_mean_24h",
        "dbp_mean_24h",
        "mbp_mean_24h",
    },
    "procedure_features": {
        "subject_id",
        "hadm_id",
        "procedure_count",
        "procedure_mechanical_ventilation",
        "procedure_renal_replacement",
        "procedure_transfusion",
        "procedure_invasive_line",
    },
    "microbiology_features": {
        "subject_id",
        "hadm_id",
        "microbiology_record_count",
        "culture_positive_flag",
        "organism_count",
        "resistant_result_flag",
    },
    "icu_features": {"subject_id", "hadm_id", "icu_admission_flag", "icu_stay_count", "icu_los_hours"},
    "outcome_features": {
        "subject_id",
        "hadm_id",
        "hospital_expire_flag",
        "hospital_los_days",
        "readmission_30d_flag",
    },
    "case_summary_mature": {
        "subject_id",
        "hadm_id",
        "history_hypertension",
        "comorbidity_count",
        "icu_admission_flag",
        "hospital_los_days",
    },
}

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Driver:
    module: Any
    name: str


def quote_ident(identifier: str) -> str:
    if not IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"非法 SQL 标识符: {identifier}")
    return f'"{identifier}"'


def import_postgres_driver() -> Driver:
    for module_name in ("psycopg", "psycopg2"):
        try:
            return Driver(module=importlib.import_module(module_name), name=module_name)
        except ImportError:
            continue
    raise ImportError("未安装 psycopg 或 psycopg2，请先安装 PostgreSQL Python 驱动。")


def connect(driver: Driver, dsn: str) -> Any:
    return driver.module.connect(dsn)


def fetch_all(conn: Any, sql: str) -> list[tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def fetch_one(conn: Any, sql: str) -> tuple[Any, ...] | None:
    rows = fetch_all(conn, sql)
    return rows[0] if rows else None


def run_psql_script(
    dsn: str,
    sql_file: Path,
    out_schema: str,
    hosp_schema: str,
    patient_schema: str,
    psql_path: str,
) -> None:
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {sql_file}")

    command = [
        psql_path,
        dsn,
        "-v",
        f"out_schema={out_schema}",
        "-v",
        f"hosp_schema={hosp_schema}",
        "-v",
        f"patient_schema={patient_schema}",
        "-f",
        str(sql_file),
    ]
    subprocess.run(command, cwd=ROOT_DIR, check=True)  # noqa: S603


def run_plain_sql_script(dsn: str, sql_file: Path, psql_path: str) -> None:
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {sql_file}")
    command = [psql_path, dsn, "-f", str(sql_file)]
    subprocess.run(command, cwd=ROOT_DIR, check=True)  # noqa: S603


def table_exists(conn: Any, schema: str, table: str) -> bool:
    row = fetch_one(
        conn,
        f"""
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = '{schema}'
          AND table_name = '{table}'
        LIMIT 1
        """,
    )
    return row is not None


def table_columns(conn: Any, schema: str, table: str) -> set[str]:
    rows = fetch_all(
        conn,
        f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = '{schema}'
          AND table_name = '{table}'
        """,
    )
    return {str(row[0]) for row in rows}


def row_count(conn: Any, schema: str, table: str) -> int:
    row = fetch_one(conn, f"SELECT COUNT(*) FROM {quote_ident(schema)}.{quote_ident(table)}")
    return int(row[0]) if row else 0


def export_with_psycopg3(conn: Any, schema: str, table: str, output_path: Path) -> None:
    copy_sql = f"COPY (SELECT * FROM {quote_ident(schema)}.{quote_ident(table)}) TO STDOUT WITH CSV HEADER"
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        with conn.cursor() as cur:
            with cur.copy(copy_sql) as copy:
                for data in copy:
                    if isinstance(data, bytes):
                        file.write(data.decode("utf-8"))
                    else:
                        file.write(str(data))


def export_with_psycopg2(conn: Any, schema: str, table: str, output_path: Path) -> None:
    copy_sql = f"COPY (SELECT * FROM {quote_ident(schema)}.{quote_ident(table)}) TO STDOUT WITH CSV HEADER"
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, file)


def export_table(driver: Driver, conn: Any, schema: str, table: str, output_dir: Path) -> Path:
    output_path = output_dir / f"{table}.csv"
    if driver.name == "psycopg":
        export_with_psycopg3(conn, schema, table, output_path)
    else:
        export_with_psycopg2(conn, schema, table, output_path)
    return output_path


def read_csv_header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        return set(next(reader, []))


def validate_exported_csv(table: str, path: Path) -> None:
    expected = REQUIRED_COLUMNS.get(table)
    if not expected:
        return
    actual = read_csv_header(path)
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(f"{path.name} 缺少必要列: {', '.join(missing)}")


def validate_schema(conn: Any, schema: str, export_tables: list[str]) -> None:
    missing_tables = [table for table in export_tables if not table_exists(conn, schema, table)]
    if missing_tables:
        raise RuntimeError(
            f"schema {schema} 缺少预处理输出表: {', '.join(missing_tables)}。"
            "请先使用 --run-sql 执行抽取脚本。"
        )

    for table, expected_cols in REQUIRED_COLUMNS.items():
        if table not in export_tables:
            continue
        actual_cols = table_columns(conn, schema, table)
        missing_cols = sorted(expected_cols - actual_cols)
        if missing_cols:
            raise RuntimeError(f"{schema}.{table} 缺少必要列: {', '.join(missing_cols)}")


def print_quality_report(conn: Any, schema: str, export_tables: list[str]) -> None:
    print("\n预处理质量概览")
    print("-" * 40)
    for table in export_tables:
        if table_exists(conn, schema, table):
            print(f"{table}: {row_count(conn, schema, table):,} 行")

    specialty_rows = fetch_all(
        conn,
        f"""
        SELECT specialty_group, COUNT(*) AS case_cnt
        FROM {quote_ident(schema)}.single_specialty_cases
        GROUP BY specialty_group
        ORDER BY case_cnt DESC
        """,
    )
    if specialty_rows:
        print("\n单专科病例分布")
        for specialty, count in specialty_rows:
            print(f"{specialty}: {int(count):,}")

    lab_rows = fetch_all(
        conn,
        f"""
        SELECT lab_name,
               non_null_cnt,
               ROUND(non_null_cnt * 100.0 / NULLIF(total_cnt, 0), 2) AS coverage_pct
        FROM (
            SELECT 'creatinine_24h' AS lab_name, COUNT(creatinine_24h) AS non_null_cnt, COUNT(*) AS total_cnt
            FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'bun_24h', COUNT(bun_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'potassium_24h', COUNT(potassium_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'sodium_24h', COUNT(sodium_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'glucose_24h', COUNT(glucose_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'inr_24h', COUNT(inr_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
            UNION ALL
            SELECT 'bilirubin_total_24h', COUNT(bilirubin_total_24h), COUNT(*) FROM {quote_ident(schema)}.cohort_first24h_labs
        ) t
        ORDER BY coverage_pct DESC, lab_name
        """,
    )
    if lab_rows:
        print("\n首 24h 检验覆盖率")
        for lab_name, non_null_cnt, coverage_pct in lab_rows:
            print(f"{lab_name}: {int(non_null_cnt):,} 非空, {coverage_pct}%")

    if "past_history_flags" in export_tables and table_exists(conn, schema, "past_history_flags"):
        history_rows = fetch_all(
            conn,
            f"""
            SELECT 'history_hypertension' AS factor, SUM(history_hypertension) FROM {quote_ident(schema)}.past_history_flags
            UNION ALL
            SELECT 'history_diabetes', SUM(history_diabetes) FROM {quote_ident(schema)}.past_history_flags
            UNION ALL
            SELECT 'history_heart_failure', SUM(history_heart_failure) FROM {quote_ident(schema)}.past_history_flags
            UNION ALL
            SELECT 'history_copd', SUM(history_copd) FROM {quote_ident(schema)}.past_history_flags
            UNION ALL
            SELECT 'history_chronic_kidney_disease', SUM(history_chronic_kidney_disease) FROM {quote_ident(schema)}.past_history_flags
            ORDER BY factor
            """,
        )
        if history_rows:
            print("\n主要既往病史阳性病例数")
            for factor, count in history_rows:
                print(f"{factor}: {int(count or 0):,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 PostgreSQL 中的 MIMIC-IV v4 表生成论文知识库管线需要的 CSV。"
    )
    parser.add_argument(
        "--pg-dsn",
        default=os.getenv("MIMICIV_PG_DSN"),
        help="PostgreSQL 连接串；也可通过环境变量 MIMICIV_PG_DSN 提供。",
    )
    parser.add_argument("--out-schema", default="thesis", help="预处理输出 schema，默认 thesis。")
    parser.add_argument("--hosp-schema", default="mimiciv_hosp", help="MIMIC-IV hosp schema，默认 mimiciv_hosp。")
    parser.add_argument(
        "--patient-schema",
        default=None,
        help="patients 表所在 schema；默认与 --hosp-schema 相同。",
    )
    parser.add_argument(
        "--sql-file",
        type=Path,
        default=DEFAULT_SQL_FILE,
        help="预处理 SQL 文件路径。",
    )
    parser.add_argument(
        "--mature-sql-file",
        type=Path,
        default=DEFAULT_MATURE_SQL_FILE,
        help="成熟临床特征 SQL 文件路径，默认 sql/02_mature_clinical_features_navicat.sql。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR,
        help="CSV 导出目录，默认项目根目录。",
    )
    parser.add_argument(
        "--run-sql",
        action="store_true",
        help="先调用 psql 执行 SQL 抽取脚本，再导出 CSV。",
    )
    parser.add_argument(
        "--run-mature-sql",
        action="store_true",
        help="调用 psql 执行成熟临床特征 SQL。该脚本也可以直接复制到 Navicat 执行。",
    )
    parser.add_argument(
        "--include-mature",
        action="store_true",
        help="导出并校验成熟临床特征表。使用 --run-mature-sql 时会自动启用。",
    )
    parser.add_argument("--psql-path", default="psql", help="psql 可执行文件路径，默认 psql。")
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="只执行 SQL 和质量检查，不导出 CSV。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.pg_dsn:
        raise ValueError("请提供 --pg-dsn，或设置环境变量 MIMICIV_PG_DSN。")

    out_schema = args.out_schema
    hosp_schema = args.hosp_schema
    patient_schema = args.patient_schema or hosp_schema
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for identifier in (out_schema, hosp_schema, patient_schema):
        quote_ident(identifier)

    if args.run_sql:
        print("开始执行 MIMIC-IV v4 预处理 SQL...")
        run_psql_script(
            dsn=args.pg_dsn,
            sql_file=args.sql_file.resolve(),
            out_schema=out_schema,
            hosp_schema=hosp_schema,
            patient_schema=patient_schema,
            psql_path=args.psql_path,
        )

    include_mature = bool(args.include_mature or args.run_mature_sql)
    if args.run_mature_sql:
        print("开始执行成熟临床特征 SQL...")
        run_plain_sql_script(
            dsn=args.pg_dsn,
            sql_file=args.mature_sql_file.resolve(),
            psql_path=args.psql_path,
        )

    export_tables = [*BASE_EXPORT_TABLES, *(MATURE_EXPORT_TABLES if include_mature else [])]

    driver = import_postgres_driver()
    with connect(driver, args.pg_dsn) as conn:
        validate_schema(conn, out_schema, export_tables)
        print_quality_report(conn, out_schema, export_tables)

        if args.skip_export:
            return

        print("\n开始导出 CSV")
        print("-" * 40)
        for table in export_tables:
            output_path = export_table(driver, conn, out_schema, table, output_dir)
            validate_exported_csv(table, output_path)
            print(f"已导出 {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"预处理失败: {exc}", file=sys.stderr)
        raise
