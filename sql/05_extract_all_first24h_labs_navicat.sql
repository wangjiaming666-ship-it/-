-- Extract all numeric first-24h laboratory tests for Navicat Premium Lite 17.
--
-- Purpose:
--   Keep all available numeric lab tests in the first 24 hours after admission,
--   instead of only keeping a small hand-picked set of risk labs.
--
-- Output tables:
--   thesis.cohort_first24h_labs_all_long
--   thesis.cohort_first24h_labs_coverage
--
-- Default schema names:
--   output schema: thesis
--   MIMIC-IV hosp schema: mimiciv_hosp
--
-- If your database uses hosp instead, replace mimiciv_hosp with hosp.

CREATE SCHEMA IF NOT EXISTS thesis;

CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_hadm_time
    ON thesis.cohort_admissions (subject_id, hadm_id, admittime, dischtime);

ANALYZE thesis.cohort_admissions;

DROP TABLE IF EXISTS thesis.cohort_first24h_labs_all_events;
CREATE TABLE thesis.cohort_first24h_labs_all_events AS
SELECT
    c.subject_id,
    c.hadm_id,
    l.charttime,
    l.itemid,
    di.label AS lab_label,
    di.fluid,
    di.category,
    l.value,
    l.valuenum,
    l.valueuom
FROM thesis.cohort_admissions c
JOIN mimiciv_hosp.labevents l
    ON c.subject_id = l.subject_id
   AND c.hadm_id = l.hadm_id
   AND l.charttime >= c.admittime
   AND l.charttime < c.admittime + INTERVAL '24 hours'
JOIN mimiciv_hosp.d_labitems di
    ON l.itemid = di.itemid
WHERE l.valuenum IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_first24h_labs_all_events_hadm
    ON thesis.cohort_first24h_labs_all_events (subject_id, hadm_id);
CREATE INDEX IF NOT EXISTS idx_first24h_labs_all_events_item
    ON thesis.cohort_first24h_labs_all_events (itemid);

ANALYZE thesis.cohort_first24h_labs_all_events;

DROP TABLE IF EXISTS thesis.cohort_first24h_labs_first_value;
CREATE TABLE thesis.cohort_first24h_labs_first_value AS
SELECT DISTINCT ON (subject_id, hadm_id, itemid)
    subject_id,
    hadm_id,
    itemid,
    charttime AS first_charttime,
    valuenum AS first_valuenum,
    valueuom AS first_valueuom
FROM thesis.cohort_first24h_labs_all_events
ORDER BY subject_id, hadm_id, itemid, charttime ASC;

CREATE INDEX IF NOT EXISTS idx_first24h_labs_first_value_hadm_item
    ON thesis.cohort_first24h_labs_first_value (subject_id, hadm_id, itemid);

ANALYZE thesis.cohort_first24h_labs_first_value;

DROP TABLE IF EXISTS thesis.cohort_first24h_labs_last_value;
CREATE TABLE thesis.cohort_first24h_labs_last_value AS
SELECT DISTINCT ON (subject_id, hadm_id, itemid)
    subject_id,
    hadm_id,
    itemid,
    charttime AS last_charttime,
    valuenum AS last_valuenum,
    valueuom AS last_valueuom
FROM thesis.cohort_first24h_labs_all_events
ORDER BY subject_id, hadm_id, itemid, charttime DESC;

CREATE INDEX IF NOT EXISTS idx_first24h_labs_last_value_hadm_item
    ON thesis.cohort_first24h_labs_last_value (subject_id, hadm_id, itemid);

ANALYZE thesis.cohort_first24h_labs_last_value;

DROP TABLE IF EXISTS thesis.cohort_first24h_labs_all_long;
CREATE TABLE thesis.cohort_first24h_labs_all_long AS
WITH aggregated AS (
    SELECT
        subject_id,
        hadm_id,
        itemid,
        MAX(lab_label) AS lab_label,
        MAX(fluid) AS fluid,
        MAX(category) AS category,
        MAX(valueuom) AS unit,
        COUNT(*) AS lab_record_count,
        MIN(charttime) AS first_observed_time,
        MAX(charttime) AS last_observed_time,
        MIN(valuenum) AS min_valuenum,
        AVG(valuenum) AS mean_valuenum,
        MAX(valuenum) AS max_valuenum
    FROM thesis.cohort_first24h_labs_all_events
    GROUP BY subject_id, hadm_id, itemid
)
SELECT
    a.subject_id,
    a.hadm_id,
    a.itemid,
    a.lab_label,
    a.fluid,
    a.category,
    a.unit,
    a.lab_record_count,
    a.first_observed_time,
    fv.first_valuenum,
    a.last_observed_time,
    lv.last_valuenum,
    a.min_valuenum,
    a.mean_valuenum,
    a.max_valuenum
FROM aggregated a
LEFT JOIN thesis.cohort_first24h_labs_first_value fv
    ON a.subject_id = fv.subject_id
   AND a.hadm_id = fv.hadm_id
   AND a.itemid = fv.itemid
LEFT JOIN thesis.cohort_first24h_labs_last_value lv
    ON a.subject_id = lv.subject_id
   AND a.hadm_id = lv.hadm_id
   AND a.itemid = lv.itemid;

CREATE INDEX IF NOT EXISTS idx_first24h_labs_all_long_hadm
    ON thesis.cohort_first24h_labs_all_long (subject_id, hadm_id);
CREATE INDEX IF NOT EXISTS idx_first24h_labs_all_long_item
    ON thesis.cohort_first24h_labs_all_long (itemid);

ANALYZE thesis.cohort_first24h_labs_all_long;

DROP TABLE IF EXISTS thesis.cohort_first24h_labs_coverage;
CREATE TABLE thesis.cohort_first24h_labs_coverage AS
WITH total_cases AS (
    SELECT COUNT(*) AS total_case_count
    FROM thesis.cohort_admissions
),
lab_cases AS (
    SELECT
        itemid,
        lab_label,
        fluid,
        category,
        unit,
        COUNT(DISTINCT hadm_id) AS non_null_case_count,
        COUNT(*) AS case_item_rows,
        SUM(lab_record_count) AS raw_lab_record_count,
        AVG(mean_valuenum) AS cohort_mean_value,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mean_valuenum) AS cohort_median_value
    FROM thesis.cohort_first24h_labs_all_long
    GROUP BY itemid, lab_label, fluid, category, unit
)
SELECT
    lc.itemid,
    lc.lab_label,
    lc.fluid,
    lc.category,
    lc.unit,
    lc.non_null_case_count,
    tc.total_case_count,
    ROUND(lc.non_null_case_count * 100.0 / NULLIF(tc.total_case_count, 0), 2) AS coverage_pct,
    lc.case_item_rows,
    lc.raw_lab_record_count,
    lc.cohort_mean_value,
    lc.cohort_median_value
FROM lab_cases lc
CROSS JOIN total_cases tc
ORDER BY coverage_pct DESC, non_null_case_count DESC, lab_label;

CREATE INDEX IF NOT EXISTS idx_first24h_labs_coverage_item
    ON thesis.cohort_first24h_labs_coverage (itemid);

ANALYZE thesis.cohort_first24h_labs_coverage;

SELECT *
FROM thesis.cohort_first24h_labs_coverage
ORDER BY coverage_pct DESC, non_null_case_count DESC, lab_label
LIMIT 50;
