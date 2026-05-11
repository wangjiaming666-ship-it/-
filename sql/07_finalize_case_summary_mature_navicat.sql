-- Finalize case_summary_mature after feature tables have been generated.
--
-- Run this script after these tables already exist:
--   thesis.case_summary
--   thesis.past_history_flags
--   thesis.comorbidity_summary
--   thesis.cohort_first24h_vitals
--   thesis.procedure_features
--   thesis.microbiology_features
--   thesis.icu_features
--   thesis.outcome_features
--
-- This script only rebuilds:
--   thesis.case_summary_mature

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

SELECT 'case_summary' AS table_name, COUNT(*) AS row_count FROM thesis.case_summary
UNION ALL
SELECT 'past_history_flags', COUNT(*) FROM thesis.past_history_flags
UNION ALL
SELECT 'comorbidity_summary', COUNT(*) FROM thesis.comorbidity_summary
UNION ALL
SELECT 'cohort_first24h_vitals', COUNT(*) FROM thesis.cohort_first24h_vitals
UNION ALL
SELECT 'procedure_features', COUNT(*) FROM thesis.procedure_features
UNION ALL
SELECT 'microbiology_features', COUNT(*) FROM thesis.microbiology_features
UNION ALL
SELECT 'icu_features', COUNT(*) FROM thesis.icu_features
UNION ALL
SELECT 'outcome_features', COUNT(*) FROM thesis.outcome_features
UNION ALL
SELECT 'case_summary_mature', COUNT(*) FROM thesis.case_summary_mature;

SELECT *
FROM thesis.case_summary_mature
LIMIT 20;
