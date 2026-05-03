-- Continue after cancelling sql/02_mature_clinical_features_navicat.sql.
--
-- Use this script after these tables already exist:
--   thesis.history_diagnoses
--   thesis.past_history_flags
--   thesis.comorbidity_summary
--
-- This script generates the remaining tables:
--   thesis.procedure_features
--   thesis.microbiology_features
--   thesis.icu_features
--   thesis.outcome_features
--   thesis.cohort_first24h_vitals
--   thesis.case_summary_mature
--
-- Default schema names:
--   output schema: thesis
--   MIMIC-IV hosp schema: mimiciv_hosp
--   MIMIC-IV ICU schema: mimiciv_icu
--
-- If your database uses hosp/icu instead, replace:
--   mimiciv_hosp -> hosp
--   mimiciv_icu  -> icu

CREATE SCHEMA IF NOT EXISTS thesis;

CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_hadm
    ON thesis.cohort_admissions (subject_id, hadm_id);
CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_time
    ON thesis.cohort_admissions (subject_id, admittime, dischtime);
CREATE INDEX IF NOT EXISTS idx_thesis_clean_dx_hadm
    ON thesis.cleaned_diagnosis_specialty_detail_6 (subject_id, hadm_id);

ANALYZE thesis.cohort_admissions;
ANALYZE thesis.cleaned_diagnosis_specialty_detail_6;

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
ANALYZE thesis.procedure_features;

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
    WHERE m.charttime IS NOT NULL
      AND m.charttime >= c.admittime
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
ANALYZE thesis.microbiology_features;

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
ANALYZE thesis.icu_features;

DROP TABLE IF EXISTS thesis.outcome_features;
CREATE TABLE thesis.outcome_features AS
WITH cohort_subjects AS (
    SELECT DISTINCT subject_id
    FROM thesis.cohort_admissions
),
subject_admissions_ordered AS (
    SELECT
        a.subject_id,
        a.hadm_id,
        a.admittime,
        LEAD(a.admittime) OVER (
            PARTITION BY a.subject_id
            ORDER BY a.admittime, a.hadm_id
        ) AS next_admittime
    FROM mimiciv_hosp.admissions a
    JOIN cohort_subjects s
        ON a.subject_id = s.subject_id
    WHERE a.admittime IS NOT NULL
)
SELECT
    c.subject_id,
    c.hadm_id,
    c.hospital_expire_flag,
    EXTRACT(EPOCH FROM (c.dischtime - c.admittime)) / 86400.0 AS hospital_los_days,
    CASE
        WHEN o.next_admittime IS NOT NULL
         AND o.next_admittime > c.dischtime
         AND o.next_admittime <= c.dischtime + INTERVAL '30 days'
        THEN 1 ELSE 0
    END AS readmission_30d_flag,
    o.next_admittime
FROM thesis.cohort_admissions c
LEFT JOIN subject_admissions_ordered o
    ON c.subject_id = o.subject_id
   AND c.hadm_id = o.hadm_id;

CREATE INDEX IF NOT EXISTS idx_outcome_features_hadm
    ON thesis.outcome_features (hadm_id);
ANALYZE thesis.outcome_features;

DROP TABLE IF EXISTS thesis.vital_itemids;
CREATE TABLE thesis.vital_itemids AS
SELECT
    itemid,
    CASE
        WHEN label = 'Heart Rate' THEN 'heart_rate'
        WHEN label = 'Respiratory Rate' THEN 'respiratory_rate'
        WHEN label = 'Temperature Fahrenheit' THEN 'temperature_f'
        WHEN label = 'Temperature Celsius' THEN 'temperature_c'
        WHEN label IN ('O2 saturation pulseoxymetry', 'SpO2') THEN 'spo2'
        WHEN label IN ('Non Invasive Blood Pressure systolic', 'Arterial Blood Pressure systolic') THEN 'sbp'
        WHEN label IN ('Non Invasive Blood Pressure diastolic', 'Arterial Blood Pressure diastolic') THEN 'dbp'
        WHEN label IN ('Non Invasive Blood Pressure mean', 'Arterial Blood Pressure mean') THEN 'mbp'
        ELSE NULL
    END AS vital_name,
    label
FROM mimiciv_icu.d_items
WHERE label IN (
    'Heart Rate',
    'Respiratory Rate',
    'Temperature Fahrenheit',
    'Temperature Celsius',
    'O2 saturation pulseoxymetry',
    'SpO2',
    'Non Invasive Blood Pressure systolic',
    'Arterial Blood Pressure systolic',
    'Non Invasive Blood Pressure diastolic',
    'Arterial Blood Pressure diastolic',
    'Non Invasive Blood Pressure mean',
    'Arterial Blood Pressure mean'
);

CREATE INDEX IF NOT EXISTS idx_vital_itemids_itemid
    ON thesis.vital_itemids (itemid);
ANALYZE thesis.vital_itemids;

DROP TABLE IF EXISTS thesis.cohort_icu_stays;
CREATE TABLE thesis.cohort_icu_stays AS
SELECT
    c.subject_id,
    c.hadm_id,
    c.admittime,
    i.stay_id,
    i.intime,
    i.outtime
FROM thesis.cohort_admissions c
JOIN mimiciv_icu.icustays i
    ON c.subject_id = i.subject_id
   AND c.hadm_id = i.hadm_id;

CREATE INDEX IF NOT EXISTS idx_cohort_icu_stays_stay
    ON thesis.cohort_icu_stays (stay_id);
CREATE INDEX IF NOT EXISTS idx_cohort_icu_stays_hadm
    ON thesis.cohort_icu_stays (subject_id, hadm_id);
ANALYZE thesis.cohort_icu_stays;

DROP TABLE IF EXISTS thesis.vital_events_24h;
CREATE TABLE thesis.vital_events_24h AS
SELECT
    s.subject_id,
    s.hadm_id,
    ce.charttime,
    vi.vital_name,
    CASE
        WHEN vi.vital_name = 'temperature_c' THEN ce.valuenum * 9.0 / 5.0 + 32.0
        ELSE ce.valuenum
    END AS valuenum
FROM thesis.cohort_icu_stays s
JOIN mimiciv_icu.chartevents ce
    ON s.stay_id = ce.stay_id
   AND ce.charttime >= s.admittime
   AND ce.charttime < s.admittime + INTERVAL '24 hours'
JOIN thesis.vital_itemids vi
    ON ce.itemid = vi.itemid
WHERE ce.valuenum IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vital_events_24h_hadm
    ON thesis.vital_events_24h (subject_id, hadm_id);
CREATE INDEX IF NOT EXISTS idx_vital_events_24h_name
    ON thesis.vital_events_24h (vital_name);
ANALYZE thesis.vital_events_24h;

DROP TABLE IF EXISTS thesis.vital_events_24h_clean;
CREATE TABLE thesis.vital_events_24h_clean AS
SELECT *
FROM thesis.vital_events_24h
WHERE
    (vital_name = 'heart_rate' AND valuenum BETWEEN 20 AND 250)
    OR (vital_name = 'respiratory_rate' AND valuenum BETWEEN 3 AND 80)
    OR (vital_name IN ('temperature_f', 'temperature_c') AND valuenum BETWEEN 80 AND 115)
    OR (vital_name = 'spo2' AND valuenum BETWEEN 30 AND 100)
    OR (vital_name IN ('sbp', 'dbp', 'mbp') AND valuenum BETWEEN 20 AND 300);

CREATE INDEX IF NOT EXISTS idx_vital_events_24h_clean_hadm
    ON thesis.vital_events_24h_clean (subject_id, hadm_id);
ANALYZE thesis.vital_events_24h_clean;

DROP TABLE IF EXISTS thesis.cohort_first24h_vitals;
CREATE TABLE thesis.cohort_first24h_vitals AS
SELECT
    c.subject_id,
    c.hadm_id,
    MIN(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'heart_rate') AS heart_rate_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name = 'respiratory_rate') AS respiratory_rate_max_24h,
    MIN(valuenum) FILTER (WHERE vital_name IN ('temperature_f', 'temperature_c')) AS temperature_f_min_24h,
    AVG(valuenum) FILTER (WHERE vital_name IN ('temperature_f', 'temperature_c')) AS temperature_f_mean_24h,
    MAX(valuenum) FILTER (WHERE vital_name IN ('temperature_f', 'temperature_c')) AS temperature_f_max_24h,
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
LEFT JOIN thesis.vital_events_24h_clean v
    ON c.subject_id = v.subject_id
   AND c.hadm_id = v.hadm_id
GROUP BY c.subject_id, c.hadm_id;

CREATE INDEX IF NOT EXISTS idx_cohort_first24h_vitals_hadm
    ON thesis.cohort_first24h_vitals (hadm_id);
ANALYZE thesis.cohort_first24h_vitals;

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
ANALYZE thesis.case_summary_mature;

SELECT 'procedure_features' AS table_name, COUNT(*) AS row_count FROM thesis.procedure_features
UNION ALL
SELECT 'microbiology_features', COUNT(*) FROM thesis.microbiology_features
UNION ALL
SELECT 'icu_features', COUNT(*) FROM thesis.icu_features
UNION ALL
SELECT 'outcome_features', COUNT(*) FROM thesis.outcome_features
UNION ALL
SELECT 'cohort_first24h_vitals', COUNT(*) FROM thesis.cohort_first24h_vitals
UNION ALL
SELECT 'case_summary_mature', COUNT(*) FROM thesis.case_summary_mature;
