-- Optimized outcome feature extraction for Navicat Premium Lite 17.
--
-- Use this script when outcome_features gets stuck at a LEFT JOIN LATERAL query.
-- The original lateral query searches the next admission once for each cohort row.
-- This version computes the next admission once with a window function, then joins
-- the result back to thesis.cohort_admissions.
--
-- Default schema names:
--   output schema: thesis
--   MIMIC-IV hosp schema: mimiciv_hosp
--
-- If your database uses hosp instead, replace mimiciv_hosp with hosp.

CREATE SCHEMA IF NOT EXISTS thesis;

CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_hadm
    ON thesis.cohort_admissions (subject_id, hadm_id);
CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_time
    ON thesis.cohort_admissions (subject_id, admittime, dischtime);

ANALYZE thesis.cohort_admissions;

DROP TABLE IF EXISTS thesis.cohort_subjects_for_readmission;
CREATE TABLE thesis.cohort_subjects_for_readmission AS
SELECT DISTINCT subject_id
FROM thesis.cohort_admissions;

CREATE INDEX IF NOT EXISTS idx_cohort_subjects_for_readmission_subject
    ON thesis.cohort_subjects_for_readmission (subject_id);

ANALYZE thesis.cohort_subjects_for_readmission;

DROP TABLE IF EXISTS thesis.subject_admissions_ordered;
CREATE TABLE thesis.subject_admissions_ordered AS
SELECT
    a.subject_id,
    a.hadm_id,
    a.admittime,
    a.dischtime,
    LEAD(a.admittime) OVER (
        PARTITION BY a.subject_id
        ORDER BY a.admittime, a.hadm_id
    ) AS next_admittime
FROM mimiciv_hosp.admissions a
JOIN thesis.cohort_subjects_for_readmission s
    ON a.subject_id = s.subject_id
WHERE a.admittime IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subject_admissions_ordered_hadm
    ON thesis.subject_admissions_ordered (subject_id, hadm_id);

ANALYZE thesis.subject_admissions_ordered;

DROP TABLE IF EXISTS thesis.outcome_features;
CREATE TABLE thesis.outcome_features AS
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
LEFT JOIN thesis.subject_admissions_ordered o
    ON c.subject_id = o.subject_id
   AND c.hadm_id = o.hadm_id;

CREATE INDEX IF NOT EXISTS idx_outcome_features_hadm
    ON thesis.outcome_features (hadm_id);

ANALYZE thesis.outcome_features;

SELECT
    COUNT(*) AS total_cases,
    SUM(hospital_expire_flag) AS hospital_death_cases,
    SUM(readmission_30d_flag) AS readmission_30d_cases,
    AVG(hospital_los_days) AS mean_hospital_los_days
FROM thesis.outcome_features;
