-- Mature clinical feature preprocessing for Navicat Premium Lite 17.
--
-- Run this script after sql/01_extract_mimiciv_v4_cohort.sql has created
-- the base tables in the thesis schema. It adds clinically important factors:
-- past history, current comorbidities, first-24h vitals, procedures,
-- microbiology, ICU exposure, outcomes, and an enriched case summary.
--
-- Default schema names:
--   output schema: thesis
--   MIMIC-IV hosp schema: mimiciv_hosp
--   MIMIC-IV ICU schema: mimiciv_icu
--
-- If your database uses hosp/icu instead, use Navicat's replace function:
--   mimiciv_hosp -> hosp
--   mimiciv_icu  -> icu

CREATE SCHEMA IF NOT EXISTS thesis;

DROP TABLE IF EXISTS thesis.history_diagnoses;
CREATE TABLE thesis.history_diagnoses AS
SELECT
    idx.subject_id,
    idx.hadm_id AS index_hadm_id,
    prev.hadm_id AS history_hadm_id,
    adm.admittime AS history_admittime,
    adm.dischtime AS history_dischtime,
    d.seq_num,
    d.icd_version,
    d.icd_code,
    dd.long_title
FROM thesis.cohort_admissions idx
JOIN mimiciv_hosp.admissions adm
    ON idx.subject_id = adm.subject_id
   AND adm.admittime < idx.admittime
JOIN mimiciv_hosp.diagnoses_icd d
    ON adm.subject_id = d.subject_id
   AND adm.hadm_id = d.hadm_id
LEFT JOIN mimiciv_hosp.d_icd_diagnoses dd
    ON d.icd_code = dd.icd_code
   AND d.icd_version = dd.icd_version
JOIN mimiciv_hosp.admissions prev
    ON adm.subject_id = prev.subject_id
   AND adm.hadm_id = prev.hadm_id
WHERE COALESCE(NULLIF(TRIM(dd.long_title), ''), NULLIF(TRIM(d.icd_code), '')) IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_history_diagnoses_index_hadm
    ON thesis.history_diagnoses (index_hadm_id);
CREATE INDEX IF NOT EXISTS idx_history_diagnoses_subject
    ON thesis.history_diagnoses (subject_id);

DROP TABLE IF EXISTS thesis.past_history_flags;
CREATE TABLE thesis.past_history_flags AS
WITH normalized AS (
    SELECT
        subject_id,
        index_hadm_id AS hadm_id,
        UPPER(REPLACE(icd_code, '.', '')) AS icd_code_norm,
        icd_version,
        LOWER(COALESCE(long_title, '')) AS title_lower
    FROM thesis.history_diagnoses
),
flags AS (
    SELECT
        subject_id,
        hadm_id,
        MAX(CASE WHEN (icd_version = 10 AND icd_code_norm LIKE 'I10%')
                   OR (icd_version = 9 AND icd_code_norm LIKE '401%')
                   OR title_lower ~ 'hypertension|hypertensive' THEN 1 ELSE 0 END) AS history_hypertension,
        MAX(CASE WHEN (icd_version = 10 AND icd_code_norm LIKE 'E1%')
                   OR (icd_version = 9 AND icd_code_norm LIKE '250%')
                   OR title_lower ~ 'diabetes|diabetic' THEN 1 ELSE 0 END) AS history_diabetes,
        MAX(CASE WHEN (icd_version = 10 AND icd_code_norm LIKE 'I50%')
                   OR (icd_version = 9 AND icd_code_norm LIKE '428%')
                   OR title_lower ~ 'heart failure|congestive heart' THEN 1 ELSE 0 END) AS history_heart_failure,
        MAX(CASE WHEN (icd_version = 10 AND (icd_code_norm LIKE 'I20%' OR icd_code_norm LIKE 'I21%' OR icd_code_norm LIKE 'I22%' OR icd_code_norm LIKE 'I25%'))
                   OR (icd_version = 9 AND (icd_code_norm LIKE '410%' OR icd_code_norm LIKE '411%' OR icd_code_norm LIKE '412%' OR icd_code_norm LIKE '413%' OR icd_code_norm LIKE '414%'))
                   OR title_lower ~ 'coronary|myocardial infarction|ischemic heart' THEN 1 ELSE 0 END) AS history_coronary_disease,
        MAX(CASE WHEN (icd_version = 10 AND (icd_code_norm LIKE 'I60%' OR icd_code_norm LIKE 'I61%' OR icd_code_norm LIKE 'I62%' OR icd_code_norm LIKE 'I63%' OR icd_code_norm LIKE 'I64%'))
                   OR (icd_version = 9 AND (icd_code_norm LIKE '430%' OR icd_code_norm LIKE '431%' OR icd_code_norm LIKE '432%' OR icd_code_norm LIKE '433%' OR icd_code_norm LIKE '434%' OR icd_code_norm LIKE '435%' OR icd_code_norm LIKE '436%'))
                   OR title_lower ~ 'stroke|cerebral infarction|intracerebral hemorrhage' THEN 1 ELSE 0 END) AS history_stroke,
        MAX(CASE WHEN (icd_version = 10 AND (icd_code_norm LIKE 'J44%' OR icd_code_norm LIKE 'J43%'))
                   OR (icd_version = 9 AND (icd_code_norm LIKE '491%' OR icd_code_norm LIKE '492%' OR icd_code_norm LIKE '496%'))
                   OR title_lower ~ 'copd|chronic obstructive|emphysema' THEN 1 ELSE 0 END) AS history_copd,
        MAX(CASE WHEN (icd_version = 10 AND icd_code_norm LIKE 'N18%')
                   OR (icd_version = 9 AND icd_code_norm LIKE '585%')
                   OR title_lower ~ 'chronic kidney|ckd|end stage renal|dialysis' THEN 1 ELSE 0 END) AS history_chronic_kidney_disease,
        MAX(CASE WHEN (icd_version = 10 AND (icd_code_norm LIKE 'K70%' OR icd_code_norm LIKE 'K71%' OR icd_code_norm LIKE 'K72%' OR icd_code_norm LIKE 'K73%' OR icd_code_norm LIKE 'K74%'))
                   OR (icd_version = 9 AND (icd_code_norm LIKE '571%' OR icd_code_norm LIKE '572%'))
                   OR title_lower ~ 'cirrhosis|chronic liver|hepatic failure' THEN 1 ELSE 0 END) AS history_chronic_liver_disease,
        MAX(CASE WHEN (icd_version = 10 AND (icd_code_norm LIKE 'C%' OR icd_code_norm LIKE 'D0%'))
                   OR (icd_version = 9 AND icd_code_norm ~ '^(14|15|16|17|18|19|20|21|22|23)')
                   OR title_lower ~ 'malignant|cancer|carcinoma|neoplasm' THEN 1 ELSE 0 END) AS history_malignancy
    FROM normalized
    GROUP BY subject_id, hadm_id
)
SELECT
    c.subject_id,
    c.hadm_id,
    COALESCE(f.history_hypertension, 0) AS history_hypertension,
    COALESCE(f.history_diabetes, 0) AS history_diabetes,
    COALESCE(f.history_heart_failure, 0) AS history_heart_failure,
    COALESCE(f.history_coronary_disease, 0) AS history_coronary_disease,
    COALESCE(f.history_stroke, 0) AS history_stroke,
    COALESCE(f.history_copd, 0) AS history_copd,
    COALESCE(f.history_chronic_kidney_disease, 0) AS history_chronic_kidney_disease,
    COALESCE(f.history_chronic_liver_disease, 0) AS history_chronic_liver_disease,
    COALESCE(f.history_malignancy, 0) AS history_malignancy
FROM thesis.cohort_admissions c
LEFT JOIN flags f
    ON c.subject_id = f.subject_id
   AND c.hadm_id = f.hadm_id;

CREATE INDEX IF NOT EXISTS idx_past_history_flags_hadm
    ON thesis.past_history_flags (hadm_id);

DROP TABLE IF EXISTS thesis.comorbidity_summary;
CREATE TABLE thesis.comorbidity_summary AS
WITH ranked AS (
    SELECT
        subject_id,
        hadm_id,
        seq_num,
        long_title,
        specialty_group,
        MIN(seq_num) OVER (PARTITION BY subject_id, hadm_id) AS primary_seq_num
    FROM thesis.cleaned_diagnosis_specialty_detail_6
),
comorbidity AS (
    SELECT DISTINCT
        subject_id,
        hadm_id,
        long_title,
        specialty_group
    FROM ranked
    WHERE seq_num IS DISTINCT FROM primary_seq_num
)
SELECT
    c.subject_id,
    c.hadm_id,
    COUNT(*) AS comorbidity_count,
    STRING_AGG(long_title, ' | ' ORDER BY long_title) AS comorbidity_list,
    STRING_AGG(DISTINCT specialty_group, ' | ' ORDER BY specialty_group) AS comorbidity_specialty_list
FROM thesis.cohort_admissions c
LEFT JOIN comorbidity cb
    ON c.subject_id = cb.subject_id
   AND c.hadm_id = cb.hadm_id
GROUP BY c.subject_id, c.hadm_id;

CREATE INDEX IF NOT EXISTS idx_comorbidity_summary_hadm
    ON thesis.comorbidity_summary (hadm_id);

DROP TABLE IF EXISTS thesis.cohort_first24h_vitals;
CREATE TABLE thesis.cohort_first24h_vitals AS
WITH chartevents_24h AS (
    SELECT
        c.subject_id,
        c.hadm_id,
        ce.charttime,
        CASE
            WHEN di.label IN ('Heart Rate') THEN 'heart_rate'
            WHEN di.label IN ('Respiratory Rate') THEN 'respiratory_rate'
            WHEN di.label IN ('Temperature Fahrenheit') THEN 'temperature_f'
            WHEN di.label IN ('Temperature Celsius') THEN 'temperature_c'
            WHEN di.label IN ('O2 saturation pulseoxymetry', 'SpO2') THEN 'spo2'
            WHEN di.label IN ('Non Invasive Blood Pressure systolic', 'Arterial Blood Pressure systolic') THEN 'sbp'
            WHEN di.label IN ('Non Invasive Blood Pressure diastolic', 'Arterial Blood Pressure diastolic') THEN 'dbp'
            WHEN di.label IN ('Non Invasive Blood Pressure mean', 'Arterial Blood Pressure mean') THEN 'mbp'
            ELSE NULL
        END AS vital_name,
        CASE
            WHEN di.label IN ('Temperature Celsius') THEN ce.valuenum * 9.0 / 5.0 + 32.0
            ELSE ce.valuenum
        END AS valuenum
    FROM thesis.cohort_admissions c
    JOIN mimiciv_icu.icustays icu
        ON c.subject_id = icu.subject_id
       AND c.hadm_id = icu.hadm_id
    JOIN mimiciv_icu.chartevents ce
        ON icu.subject_id = ce.subject_id
       AND icu.hadm_id = ce.hadm_id
       AND icu.stay_id = ce.stay_id
       AND ce.charttime >= c.admittime
       AND ce.charttime < c.admittime + INTERVAL '24 hours'
    JOIN mimiciv_icu.d_items di
        ON ce.itemid = di.itemid
    WHERE ce.valuenum IS NOT NULL
),
filtered AS (
    SELECT *
    FROM chartevents_24h
    WHERE vital_name IS NOT NULL
      AND (
        (vital_name = 'heart_rate' AND valuenum BETWEEN 20 AND 250)
        OR (vital_name = 'respiratory_rate' AND valuenum BETWEEN 3 AND 80)
        OR (vital_name = 'temperature_f' AND valuenum BETWEEN 80 AND 115)
        OR (vital_name = 'spo2' AND valuenum BETWEEN 30 AND 100)
        OR (vital_name IN ('sbp', 'dbp', 'mbp') AND valuenum BETWEEN 20 AND 300)
      )
)
SELECT
    c.subject_id,
    c.hadm_id,
    MIN(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'temperature_f') AS temperature_f_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'temperature_f') AS temperature_f_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'temperature_f') AS temperature_f_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'spo2') AS spo2_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'spo2') AS spo2_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'spo2') AS spo2_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'sbp') AS sbp_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'sbp') AS sbp_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'sbp') AS sbp_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'dbp') AS dbp_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'dbp') AS dbp_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'dbp') AS dbp_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'mbp') AS mbp_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'mbp') AS mbp_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'mbp') AS mbp_max_24h
FROM thesis.cohort_admissions c
LEFT JOIN filtered f
    ON c.subject_id = f.subject_id
   AND c.hadm_id = f.hadm_id
GROUP BY c.subject_id, c.hadm_id;

CREATE INDEX IF NOT EXISTS idx_cohort_first24h_vitals_hadm
    ON thesis.cohort_first24h_vitals (hadm_id);

DROP TABLE IF EXISTS thesis.procedure_features;
CREATE TABLE thesis.procedure_features AS
WITH procedures AS (
    SELECT
        c.subject_id,
        c.hadm_id,
        p.icd_version,
        UPPER(REPLACE(p.icd_code, '.', '')) AS icd_code_norm,
        COALESCE(dp.long_title, p.icd_code) AS procedure_name
    FROM thesis.cohort_admissions c
    JOIN mimiciv_hosp.procedures_icd p
        ON c.subject_id = p.subject_id
       AND c.hadm_id = p.hadm_id
    LEFT JOIN mimiciv_hosp.d_icd_procedures dp
        ON p.icd_code = dp.icd_code
       AND p.icd_version = dp.icd_version
),
aggregated AS (
    SELECT
        subject_id,
        hadm_id,
        COUNT(*) AS procedure_count,
        MAX(CASE WHEN LOWER(procedure_name) ~ 'ventilation|respiratory ventilation|mechanical ventilation' THEN 1 ELSE 0 END) AS procedure_mechanical_ventilation,
        MAX(CASE WHEN LOWER(procedure_name) ~ 'dialysis|hemodialysis|hemofiltration|renal replacement' THEN 1 ELSE 0 END) AS procedure_renal_replacement,
        MAX(CASE WHEN LOWER(procedure_name) ~ 'transfusion|packed cells|plasma|platelets' THEN 1 ELSE 0 END) AS procedure_transfusion,
        MAX(CASE WHEN LOWER(procedure_name) ~ 'catheter|central venous|arterial line' THEN 1 ELSE 0 END) AS procedure_invasive_line,
        STRING_AGG(DISTINCT procedure_name, ' | ' ORDER BY procedure_name) AS procedure_list
    FROM procedures
    GROUP BY subject_id, hadm_id
)
SELECT
    c.subject_id,
    c.hadm_id,
    COALESCE(a.procedure_count, 0) AS procedure_count,
    COALESCE(a.procedure_mechanical_ventilation, 0) AS procedure_mechanical_ventilation,
    COALESCE(a.procedure_renal_replacement, 0) AS procedure_renal_replacement,
    COALESCE(a.procedure_transfusion, 0) AS procedure_transfusion,
    COALESCE(a.procedure_invasive_line, 0) AS procedure_invasive_line,
    COALESCE(a.procedure_list, '') AS procedure_list
FROM thesis.cohort_admissions c
LEFT JOIN aggregated a
    ON c.subject_id = a.subject_id
   AND c.hadm_id = a.hadm_id;

CREATE INDEX IF NOT EXISTS idx_procedure_features_hadm
    ON thesis.procedure_features (hadm_id);

DROP TABLE IF EXISTS thesis.microbiology_features;
CREATE TABLE thesis.microbiology_features AS
WITH micro AS (
    SELECT
        c.subject_id,
        c.hadm_id,
        m.charttime,
        COALESCE(NULLIF(TRIM(m.spec_type_desc), ''), 'Unknown specimen') AS specimen,
        NULLIF(TRIM(m.org_name), '') AS organism,
        NULLIF(TRIM(m.ab_name), '') AS antibiotic_name,
        NULLIF(TRIM(m.interpretation), '') AS interpretation
    FROM thesis.cohort_admissions c
    JOIN mimiciv_hosp.microbiologyevents m
        ON c.subject_id = m.subject_id
       AND c.hadm_id = m.hadm_id
    WHERE m.charttime >= c.admittime
      AND m.charttime < c.dischtime + INTERVAL '1 day'
),
aggregated AS (
    SELECT
        subject_id,
        hadm_id,
        COUNT(*) AS microbiology_record_count,
        MAX(CASE WHEN organism IS NOT NULL THEN 1 ELSE 0 END) AS culture_positive_flag,
        COUNT(DISTINCT organism) FILTER (WHERE organism IS NOT NULL) AS organism_count,
        MAX(CASE WHEN interpretation = 'R' THEN 1 ELSE 0 END) AS resistant_result_flag,
        STRING_AGG(DISTINCT specimen, ' | ' ORDER BY specimen) AS specimen_list,
        STRING_AGG(DISTINCT organism, ' | ' ORDER BY organism) FILTER (WHERE organism IS NOT NULL) AS organism_list
    FROM micro
    GROUP BY subject_id, hadm_id
)
SELECT
    c.subject_id,
    c.hadm_id,
    COALESCE(a.microbiology_record_count, 0) AS microbiology_record_count,
    COALESCE(a.culture_positive_flag, 0) AS culture_positive_flag,
    COALESCE(a.organism_count, 0) AS organism_count,
    COALESCE(a.resistant_result_flag, 0) AS resistant_result_flag,
    COALESCE(a.specimen_list, '') AS specimen_list,
    COALESCE(a.organism_list, '') AS organism_list
FROM thesis.cohort_admissions c
LEFT JOIN aggregated a
    ON c.subject_id = a.subject_id
   AND c.hadm_id = a.hadm_id;

CREATE INDEX IF NOT EXISTS idx_microbiology_features_hadm
    ON thesis.microbiology_features (hadm_id);

DROP TABLE IF EXISTS thesis.icu_features;
CREATE TABLE thesis.icu_features AS
SELECT
    c.subject_id,
    c.hadm_id,
    CASE WHEN COUNT(i.stay_id) > 0 THEN 1 ELSE 0 END AS icu_admission_flag,
    COUNT(DISTINCT i.stay_id) AS icu_stay_count,
    MIN(i.intime) AS first_icu_intime,
    MAX(i.outtime) AS last_icu_outtime,
    COALESCE(SUM(EXTRACT(EPOCH FROM (i.outtime - i.intime)) / 3600.0), 0) AS icu_los_hours
FROM thesis.cohort_admissions c
LEFT JOIN mimiciv_icu.icustays i
    ON c.subject_id = i.subject_id
   AND c.hadm_id = i.hadm_id
GROUP BY c.subject_id, c.hadm_id;

CREATE INDEX IF NOT EXISTS idx_icu_features_hadm
    ON thesis.icu_features (hadm_id);

DROP TABLE IF EXISTS thesis.outcome_features;
CREATE TABLE thesis.outcome_features AS
SELECT
    c.subject_id,
    c.hadm_id,
    c.hospital_expire_flag,
    EXTRACT(EPOCH FROM (c.dischtime - c.admittime)) / 86400.0 AS hospital_los_days,
    CASE
        WHEN next_adm.next_admittime IS NOT NULL
         AND next_adm.next_admittime <= c.dischtime + INTERVAL '30 days'
        THEN 1 ELSE 0
    END AS readmission_30d_flag,
    next_adm.next_admittime
FROM thesis.cohort_admissions c
LEFT JOIN LATERAL (
    SELECT MIN(a.admittime) AS next_admittime
    FROM mimiciv_hosp.admissions a
    WHERE a.subject_id = c.subject_id
      AND a.hadm_id <> c.hadm_id
      AND a.admittime > c.dischtime
) next_adm ON TRUE;

CREATE INDEX IF NOT EXISTS idx_outcome_features_hadm
    ON thesis.outcome_features (hadm_id);

DROP TABLE IF EXISTS thesis.case_summary_mature;
CREATE TABLE thesis.case_summary_mature AS
SELECT
    cs.*,
    ph.history_hypertension,
    ph.history_diabetes,
    ph.history_heart_failure,
    ph.history_coronary_disease,
    ph.history_stroke,
    ph.history_copd,
    ph.history_chronic_kidney_disease,
    ph.history_chronic_liver_disease,
    ph.history_malignancy,
    cb.comorbidity_count AS current_comorbidity_count,
    cb.comorbidity_list AS current_comorbidity_list,
    cb.comorbidity_specialty_list AS current_comorbidity_specialty_list,
    vf.heart_rate_min_24h,
    vf.heart_rate_mean_24h,
    vf.heart_rate_max_24h,
    vf.respiratory_rate_min_24h,
    vf.respiratory_rate_mean_24h,
    vf.respiratory_rate_max_24h,
    vf.temperature_f_min_24h,
    vf.temperature_f_mean_24h,
    vf.temperature_f_max_24h,
    vf.spo2_min_24h,
    vf.spo2_mean_24h,
    vf.spo2_max_24h,
    vf.sbp_min_24h,
    vf.sbp_mean_24h,
    vf.sbp_max_24h,
    vf.dbp_min_24h,
    vf.dbp_mean_24h,
    vf.dbp_max_24h,
    vf.mbp_min_24h,
    vf.mbp_mean_24h,
    vf.mbp_max_24h,
    pf.procedure_count,
    pf.procedure_mechanical_ventilation,
    pf.procedure_renal_replacement,
    pf.procedure_transfusion,
    pf.procedure_invasive_line,
    pf.procedure_list,
    mf.microbiology_record_count,
    mf.culture_positive_flag,
    mf.organism_count,
    mf.resistant_result_flag,
    mf.specimen_list,
    mf.organism_list,
    icu.icu_admission_flag,
    icu.icu_stay_count,
    icu.first_icu_intime,
    icu.last_icu_outtime,
    icu.icu_los_hours,
    ofe.hospital_los_days,
    ofe.readmission_30d_flag
FROM thesis.case_summary cs
LEFT JOIN thesis.past_history_flags ph
    ON cs.subject_id = ph.subject_id
   AND cs.hadm_id = ph.hadm_id
LEFT JOIN thesis.comorbidity_summary cb
    ON cs.subject_id = cb.subject_id
   AND cs.hadm_id = cb.hadm_id
LEFT JOIN thesis.cohort_first24h_vitals vf
    ON cs.subject_id = vf.subject_id
   AND cs.hadm_id = vf.hadm_id
LEFT JOIN thesis.procedure_features pf
    ON cs.subject_id = pf.subject_id
   AND cs.hadm_id = pf.hadm_id
LEFT JOIN thesis.microbiology_features mf
    ON cs.subject_id = mf.subject_id
   AND cs.hadm_id = mf.hadm_id
LEFT JOIN thesis.icu_features icu
    ON cs.subject_id = icu.subject_id
   AND cs.hadm_id = icu.hadm_id
LEFT JOIN thesis.outcome_features ofe
    ON cs.subject_id = ofe.subject_id
   AND cs.hadm_id = ofe.hadm_id;

CREATE INDEX IF NOT EXISTS idx_case_summary_mature_hadm
    ON thesis.case_summary_mature (hadm_id);

ANALYZE thesis.history_diagnoses;
ANALYZE thesis.past_history_flags;
ANALYZE thesis.comorbidity_summary;
ANALYZE thesis.cohort_first24h_vitals;
ANALYZE thesis.procedure_features;
ANALYZE thesis.microbiology_features;
ANALYZE thesis.icu_features;
ANALYZE thesis.outcome_features;
ANALYZE thesis.case_summary_mature;
