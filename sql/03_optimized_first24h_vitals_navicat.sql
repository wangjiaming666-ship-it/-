-- Optimized first-24h vital signs extraction for Navicat Premium Lite 17.
--
-- Use this script when sql/02_mature_clinical_features_navicat.sql gets stuck
-- at thesis.cohort_first24h_vitals. The slow point is mimiciv_icu.chartevents.
-- This version reduces the scan by:
--   1. creating a small itemid table first;
--   2. creating a cohort ICU stay table first;
--   3. joining chartevents only by stay_id and selected itemid;
--   4. materializing an intermediate vital_events_24h table before aggregation.
--
-- Default schema names:
--   output schema: thesis
--   MIMIC-IV ICU schema: mimiciv_icu
--
-- If your ICU schema is named icu, replace mimiciv_icu with icu.

CREATE SCHEMA IF NOT EXISTS thesis;

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

SELECT
    COUNT(*) AS total_cases,
    COUNT(heart_rate_mean_24h) AS heart_rate_non_null,
    COUNT(respiratory_rate_mean_24h) AS respiratory_rate_non_null,
    COUNT(temperature_f_mean_24h) AS temperature_non_null,
    COUNT(spo2_mean_24h) AS spo2_non_null,
    COUNT(sbp_mean_24h) AS sbp_non_null,
    COUNT(mbp_mean_24h) AS mbp_non_null
FROM thesis.cohort_first24h_vitals;
