-- MIMIC-IV v4 preprocessing for the thesis knowledge-base pipeline.
--
-- Usage:
--   psql "host=localhost port=5432 dbname=mimiciv user=wjm password=..." \
--     -v out_schema=thesis \
--     -v patient_schema=mimiciv_hosp \
--     -v hosp_schema=mimiciv_hosp \
--     -f sql/01_extract_mimiciv_v4_cohort.sql
--
-- The output tables intentionally match the CSV names consumed by:
--   build_specialty_kb.py
--   draw_processed_data_figures.py
--   experiments/case_builder.py

\set ON_ERROR_STOP on

\if :{?out_schema}
\else
\set out_schema thesis
\endif

\if :{?hosp_schema}
\else
\set hosp_schema mimiciv_hosp
\endif

\if :{?patient_schema}
\else
\set patient_schema :hosp_schema
\endif

CREATE SCHEMA IF NOT EXISTS :out_schema;

DROP TABLE IF EXISTS :out_schema.cohort_admissions;
CREATE TABLE :out_schema.cohort_admissions AS
WITH admission_base AS (
    SELECT
        p.subject_id,
        a.hadm_id,
        p.gender,
        p.anchor_age,
        a.admittime,
        a.dischtime,
        a.admission_type,
        a.admission_location,
        a.discharge_location,
        a.insurance,
        a.language,
        a.marital_status,
        a.race,
        a.hospital_expire_flag
    FROM :patient_schema.patients p
    JOIN :hosp_schema.admissions a
        ON p.subject_id = a.subject_id
    WHERE p.anchor_age >= 18
      AND a.hadm_id IS NOT NULL
      AND a.admittime IS NOT NULL
      AND a.dischtime IS NOT NULL
      AND a.dischtime > a.admittime
)
SELECT *
FROM admission_base;

CREATE INDEX IF NOT EXISTS idx_cohort_admissions_hadm
    ON :out_schema.cohort_admissions (hadm_id);
CREATE INDEX IF NOT EXISTS idx_cohort_admissions_subject
    ON :out_schema.cohort_admissions (subject_id);

DROP TABLE IF EXISTS :out_schema.cohort_diagnoses;
CREATE TABLE :out_schema.cohort_diagnoses AS
SELECT
    c.subject_id,
    c.hadm_id,
    d.seq_num,
    d.icd_version,
    d.icd_code,
    dd.long_title
FROM :out_schema.cohort_admissions c
JOIN :hosp_schema.diagnoses_icd d
    ON c.subject_id = d.subject_id
   AND c.hadm_id = d.hadm_id
LEFT JOIN :hosp_schema.d_icd_diagnoses dd
    ON d.icd_code = dd.icd_code
   AND d.icd_version = dd.icd_version
WHERE COALESCE(NULLIF(TRIM(dd.long_title), ''), NULLIF(TRIM(d.icd_code), '')) IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cohort_diagnoses_hadm
    ON :out_schema.cohort_diagnoses (hadm_id);
CREATE INDEX IF NOT EXISTS idx_cohort_diagnoses_icd
    ON :out_schema.cohort_diagnoses (icd_version, icd_code);

DROP TABLE IF EXISTS :out_schema.diagnosis_specialty_detail_6;
CREATE TABLE :out_schema.diagnosis_specialty_detail_6 AS
WITH normalized AS (
    SELECT
        subject_id,
        hadm_id,
        seq_num,
        icd_version,
        UPPER(REPLACE(icd_code, '.', '')) AS icd_code_norm,
        icd_code,
        long_title,
        LOWER(COALESCE(long_title, '')) AS title_lower
    FROM :out_schema.cohort_diagnoses
),
mapped AS (
    SELECT
        *,
        CASE
            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'I%' OR icd_code_norm LIKE 'R00%' OR icd_code_norm LIKE 'R01%'
                OR icd_code_norm LIKE 'R03%' OR icd_code_norm LIKE 'R07%'
            ) THEN '心血管'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '39%' OR icd_code_norm LIKE '40%' OR icd_code_norm LIKE '41%'
                OR icd_code_norm LIKE '42%' OR icd_code_norm LIKE '43%' OR icd_code_norm LIKE '44%'
                OR icd_code_norm LIKE '45%' OR icd_code_norm LIKE '785%' OR icd_code_norm LIKE '7865%'
            ) THEN '心血管'
            WHEN title_lower ~ '(heart|card|coronary|myocard|atrial|ventric|hypertension|infarction|ischemi|aortic|thrombosis|embolism)'
                THEN '心血管'

            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'G%' OR icd_code_norm LIKE 'F01%' OR icd_code_norm LIKE 'F02%'
                OR icd_code_norm LIKE 'F03%' OR icd_code_norm LIKE 'I60%' OR icd_code_norm LIKE 'I61%'
                OR icd_code_norm LIKE 'I62%' OR icd_code_norm LIKE 'I63%' OR icd_code_norm LIKE 'I64%'
                OR icd_code_norm LIKE 'R51%' OR icd_code_norm LIKE 'R56%'
            ) THEN '神经'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '32%' OR icd_code_norm LIKE '33%' OR icd_code_norm LIKE '34%'
                OR icd_code_norm LIKE '35%' OR icd_code_norm LIKE '430%' OR icd_code_norm LIKE '431%'
                OR icd_code_norm LIKE '432%' OR icd_code_norm LIKE '433%' OR icd_code_norm LIKE '434%'
                OR icd_code_norm LIKE '435%' OR icd_code_norm LIKE '436%' OR icd_code_norm LIKE '7803%'
            ) THEN '神经'
            WHEN title_lower ~ '(brain|cerebr|intracran|seizure|epilep|stroke|parkinson|dementia|neurop|mening|encephal|migraine)'
                THEN '神经'

            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'J%' OR icd_code_norm LIKE 'R04%' OR icd_code_norm LIKE 'R05%'
                OR icd_code_norm LIKE 'R06%' OR icd_code_norm LIKE 'R09%'
            ) THEN '呼吸'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '46%' OR icd_code_norm LIKE '47%' OR icd_code_norm LIKE '48%'
                OR icd_code_norm LIKE '49%' OR icd_code_norm LIKE '50%' OR icd_code_norm LIKE '51%'
                OR icd_code_norm LIKE '7860%' OR icd_code_norm LIKE '7862%'
            ) THEN '呼吸'
            WHEN title_lower ~ '(respirat|pulmon|pneumon|asthma|copd|bronch|lung|pleur|emphysema|airway)'
                THEN '呼吸'

            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'N%' OR icd_code_norm LIKE 'R30%' OR icd_code_norm LIKE 'R31%'
                OR icd_code_norm LIKE 'R32%' OR icd_code_norm LIKE 'R33%' OR icd_code_norm LIKE 'R34%'
            ) THEN '肾内/泌尿'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '58%' OR icd_code_norm LIKE '59%' OR icd_code_norm LIKE '60%'
                OR icd_code_norm LIKE '788%' OR icd_code_norm LIKE '791%'
            ) THEN '肾内/泌尿'
            WHEN title_lower ~ '(kidney|renal|neph|urinary|ureter|bladder|prostat|pyelo|cystitis|hydroneph|dialysis)'
                THEN '肾内/泌尿'

            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'E%' OR icd_code_norm LIKE 'R73%' OR icd_code_norm LIKE 'R63%'
            ) THEN '内分泌/代谢'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '24%' OR icd_code_norm LIKE '25%' OR icd_code_norm LIKE '26%'
                OR icd_code_norm LIKE '27%' OR icd_code_norm LIKE '278%' OR icd_code_norm LIKE '276%'
            ) THEN '内分泌/代谢'
            WHEN title_lower ~ '(diabetes|thyroid|obesity|lipid|cholesterol|metab|adrenal|pituitar|glucose|ketoacidosis|malnutrition)'
                THEN '内分泌/代谢'

            WHEN icd_version = 10 AND (
                icd_code_norm LIKE 'K%' OR icd_code_norm LIKE 'R10%' OR icd_code_norm LIKE 'R11%'
                OR icd_code_norm LIKE 'R12%' OR icd_code_norm LIKE 'R13%' OR icd_code_norm LIKE 'R14%'
                OR icd_code_norm LIKE 'R17%' OR icd_code_norm LIKE 'R18%' OR icd_code_norm LIKE 'R19%'
            ) THEN '消化'
            WHEN icd_version = 9 AND (
                icd_code_norm LIKE '52%' OR icd_code_norm LIKE '53%' OR icd_code_norm LIKE '54%'
                OR icd_code_norm LIKE '55%' OR icd_code_norm LIKE '56%' OR icd_code_norm LIKE '57%'
                OR icd_code_norm LIKE '787%' OR icd_code_norm LIKE '789%'
            ) THEN '消化'
            WHEN title_lower ~ '(gastro|reflux|liver|hepatic|append|bowel|bile|pancrea|colitis|crohn|ulcer|rect|stomach|cholecyst|intestin|duoden|gastric|esophag)'
                THEN '消化'
            ELSE NULL
        END AS specialty_group
    FROM normalized
)
SELECT
    subject_id,
    hadm_id,
    seq_num,
    icd_version,
    icd_code,
    long_title,
    specialty_group
FROM mapped
WHERE specialty_group IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_diagnosis_specialty_detail_6_hadm
    ON :out_schema.diagnosis_specialty_detail_6 (hadm_id);
CREATE INDEX IF NOT EXISTS idx_diagnosis_specialty_detail_6_group
    ON :out_schema.diagnosis_specialty_detail_6 (specialty_group);

DROP TABLE IF EXISTS :out_schema.cleaned_diagnosis_specialty_detail_6;
CREATE TABLE :out_schema.cleaned_diagnosis_specialty_detail_6 AS
SELECT DISTINCT
    subject_id,
    hadm_id,
    seq_num,
    icd_version,
    icd_code,
    long_title,
    specialty_group
FROM :out_schema.diagnosis_specialty_detail_6
WHERE long_title IS NOT NULL
  AND TRIM(long_title) <> ''
  AND specialty_group IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cleaned_diagnosis_specialty_detail_6_hadm
    ON :out_schema.cleaned_diagnosis_specialty_detail_6 (hadm_id);

DROP TABLE IF EXISTS :out_schema.case_summary;
CREATE TABLE :out_schema.case_summary AS
WITH specialty_by_case AS (
    SELECT
        subject_id,
        hadm_id,
        COUNT(DISTINCT specialty_group) AS specialty_cnt,
        STRING_AGG(DISTINCT specialty_group, ' | ' ORDER BY specialty_group) AS specialty_list
    FROM :out_schema.cleaned_diagnosis_specialty_detail_6
    GROUP BY subject_id, hadm_id
),
diagnosis_by_case AS (
    SELECT
        subject_id,
        hadm_id,
        STRING_AGG(long_title, ' | ' ORDER BY seq_num NULLS LAST, long_title) AS diagnosis_list
    FROM (
        SELECT DISTINCT subject_id, hadm_id, seq_num, long_title
        FROM :out_schema.cleaned_diagnosis_specialty_detail_6
    ) d
    GROUP BY subject_id, hadm_id
)
SELECT
    c.subject_id,
    c.hadm_id,
    c.gender,
    c.anchor_age,
    c.admittime,
    c.dischtime,
    c.admission_type,
    c.admission_location,
    c.discharge_location,
    c.insurance,
    c.language,
    c.marital_status,
    c.race,
    c.hospital_expire_flag,
    s.specialty_cnt,
    s.specialty_list,
    d.diagnosis_list
FROM :out_schema.cohort_admissions c
JOIN specialty_by_case s
    ON c.subject_id = s.subject_id
   AND c.hadm_id = s.hadm_id
LEFT JOIN diagnosis_by_case d
    ON c.subject_id = d.subject_id
   AND c.hadm_id = d.hadm_id;

CREATE INDEX IF NOT EXISTS idx_case_summary_hadm
    ON :out_schema.case_summary (hadm_id);

DROP TABLE IF EXISTS :out_schema.single_specialty_cases;
CREATE TABLE :out_schema.single_specialty_cases AS
SELECT
    subject_id,
    hadm_id,
    specialty_list AS specialty_group
FROM :out_schema.case_summary
WHERE specialty_cnt = 1;

CREATE INDEX IF NOT EXISTS idx_single_specialty_cases_hadm
    ON :out_schema.single_specialty_cases (hadm_id);

DROP TABLE IF EXISTS :out_schema.multi_specialty_cases_v2;
CREATE TABLE :out_schema.multi_specialty_cases_v2 AS
SELECT
    subject_id,
    hadm_id,
    specialty_cnt,
    specialty_list
FROM :out_schema.case_summary
WHERE specialty_cnt >= 2;

CREATE INDEX IF NOT EXISTS idx_multi_specialty_cases_v2_hadm
    ON :out_schema.multi_specialty_cases_v2 (hadm_id);

DROP TABLE IF EXISTS :out_schema.cohort_prescriptions;
CREATE TABLE :out_schema.cohort_prescriptions AS
SELECT
    c.subject_id,
    c.hadm_id,
    p.pharmacy_id,
    p.poe_id,
    p.poe_seq,
    p.order_provider_id,
    p.starttime,
    p.stoptime,
    p.drug_type,
    p.drug,
    p.formulary_drug_cd,
    p.gsn,
    p.ndc,
    p.prod_strength,
    p.form_rx,
    p.dose_val_rx,
    p.dose_unit_rx,
    p.form_val_disp,
    p.form_unit_disp,
    p.doses_per_24_hrs,
    p.route
FROM :out_schema.cohort_admissions c
JOIN :hosp_schema.prescriptions p
    ON c.subject_id = p.subject_id
   AND c.hadm_id = p.hadm_id
WHERE p.drug IS NOT NULL
  AND TRIM(p.drug) <> '';

CREATE INDEX IF NOT EXISTS idx_cohort_prescriptions_hadm
    ON :out_schema.cohort_prescriptions (hadm_id);

DROP TABLE IF EXISTS :out_schema.cleaned_prescriptions;
CREATE TABLE :out_schema.cleaned_prescriptions AS
SELECT DISTINCT
    subject_id,
    hadm_id,
    INITCAP(TRIM(REGEXP_REPLACE(drug, '\s+', ' ', 'g'))) AS drug_name,
    MIN(starttime) AS first_starttime,
    MAX(stoptime) AS last_stoptime,
    COUNT(*) AS prescription_record_cnt
FROM :out_schema.cohort_prescriptions
WHERE drug IS NOT NULL
  AND TRIM(drug) <> ''
GROUP BY subject_id, hadm_id, INITCAP(TRIM(REGEXP_REPLACE(drug, '\s+', ' ', 'g')));

CREATE INDEX IF NOT EXISTS idx_cleaned_prescriptions_hadm
    ON :out_schema.cleaned_prescriptions (hadm_id);

DROP TABLE IF EXISTS :out_schema.cohort_first24h_labs;
CREATE TABLE :out_schema.cohort_first24h_labs AS
WITH lab_events AS (
    SELECT
        c.subject_id,
        c.hadm_id,
        l.charttime,
        l.itemid,
        l.valuenum
    FROM :out_schema.cohort_admissions c
    JOIN :hosp_schema.labevents l
        ON c.subject_id = l.subject_id
       AND c.hadm_id = l.hadm_id
       AND l.charttime >= c.admittime
       AND l.charttime < c.admittime + INTERVAL '24 hours'
    WHERE l.valuenum IS NOT NULL
),
named_labs AS (
    SELECT
        e.subject_id,
        e.hadm_id,
        CASE
            WHEN di.label ILIKE 'Creatinine%' THEN 'creatinine_24h'
            WHEN di.label ILIKE 'Urea Nitrogen%' OR di.label ILIKE 'Blood Urea Nitrogen%' THEN 'bun_24h'
            WHEN di.label ILIKE 'Potassium%' THEN 'potassium_24h'
            WHEN di.label ILIKE 'Sodium%' THEN 'sodium_24h'
            WHEN di.label ILIKE 'Glucose%' THEN 'glucose_24h'
            WHEN di.label ILIKE 'INR%' OR di.label ILIKE '%International Normalized Ratio%' THEN 'inr_24h'
            WHEN di.label ILIKE 'Bilirubin, Total%' OR di.label ILIKE 'Total Bilirubin%' THEN 'bilirubin_total_24h'
            ELSE NULL
        END AS lab_name,
        e.valuenum
    FROM lab_events e
    JOIN :hosp_schema.d_labitems di
        ON e.itemid = di.itemid
    WHERE di.fluid = 'Blood'
)
SELECT
    c.subject_id,
    c.hadm_id,
    MAX(valuenum) FILTER (WHERE lab_name = 'creatinine_24h') AS creatinine_24h,
    MAX(valuenum) FILTER (WHERE lab_name = 'bun_24h') AS bun_24h,
    MAX(valuenum) FILTER (WHERE lab_name = 'potassium_24h') AS potassium_24h,
    MIN(valuenum) FILTER (WHERE lab_name = 'sodium_24h') AS sodium_24h,
    MAX(valuenum) FILTER (WHERE lab_name = 'glucose_24h') AS glucose_24h,
    MAX(valuenum) FILTER (WHERE lab_name = 'inr_24h') AS inr_24h,
    MAX(valuenum) FILTER (WHERE lab_name = 'bilirubin_total_24h') AS bilirubin_total_24h
FROM :out_schema.cohort_admissions c
LEFT JOIN named_labs n
    ON c.subject_id = n.subject_id
   AND c.hadm_id = n.hadm_id
GROUP BY c.subject_id, c.hadm_id;

CREATE INDEX IF NOT EXISTS idx_cohort_first24h_labs_hadm
    ON :out_schema.cohort_first24h_labs (hadm_id);

DROP TABLE IF EXISTS :out_schema.specialty_top_diagnoses_clean;
CREATE TABLE :out_schema.specialty_top_diagnoses_clean AS
SELECT
    specialty_group,
    long_title AS diagnosis_name,
    COUNT(DISTINCT hadm_id) AS freq
FROM :out_schema.cleaned_diagnosis_specialty_detail_6
GROUP BY specialty_group, long_title
ORDER BY specialty_group, freq DESC, diagnosis_name;

DROP TABLE IF EXISTS :out_schema.specialty_top_drugs_clean;
CREATE TABLE :out_schema.specialty_top_drugs_clean AS
SELECT
    s.specialty_group,
    p.drug_name,
    COUNT(DISTINCT s.hadm_id) AS freq
FROM :out_schema.single_specialty_cases s
JOIN :out_schema.cleaned_prescriptions p
    ON s.subject_id = p.subject_id
   AND s.hadm_id = p.hadm_id
GROUP BY s.specialty_group, p.drug_name
ORDER BY s.specialty_group, freq DESC, p.drug_name;

ANALYZE :out_schema.cohort_admissions;
ANALYZE :out_schema.cleaned_diagnosis_specialty_detail_6;
ANALYZE :out_schema.cleaned_prescriptions;
ANALYZE :out_schema.cohort_first24h_labs;
ANALYZE :out_schema.single_specialty_cases;
ANALYZE :out_schema.multi_specialty_cases_v2;
