# 毕业设计总体思路与数据预处理优化方案

## 1. 当前问题判断

`sql/02_mature_clinical_features_navicat.sql` 已经执行很久仍未结束，通常不是 Navicat 的问题，而是 SQL 中存在对 MIMIC-IV 大表的高成本扫描和 join。MIMIC-IV 中最容易拖慢的表是 ICU 模块的 `chartevents`，其次是 `microbiologyevents`、历史住院诊断回溯和出院后再入院查询。

当前脚本中最可能卡住的位置有三处：

1. `history_diagnoses`：把每个当前住院病例与同一患者所有历史住院关联，再关联历史诊断。若患者多次住院，会产生大量重复行。
2. `cohort_first24h_vitals`：从 `mimiciv_icu.chartevents` 读取生命体征。`chartevents` 是 MIMIC-IV 最大的表之一，如果先 join 全表再按 `d_items.label` 判断，会非常慢。
3. `microbiology_features` 和 `outcome_features`：虽然通常比 `chartevents` 小，但如果缺少索引或 cohort 很大，也可能明显拖慢。

所以不要继续等这个已经运行很久的 SQL。应停止当前任务，改为分段执行和先小后大的策略。

根据当前 Navicat 截图，已经确认：

- `history_diagnoses` 已生成，但耗时较长。
- `past_history_flags` 已生成，但耗时较长。
- `comorbidity_summary` 已生成，耗时较短。
- 真正被取消的是 `cohort_first24h_vitals`。

因此当前不需要重跑前面已经成功的表，下一步只需要单独处理生命体征模块，并继续执行后面的轻量模块。

## 2. 立即处理方案

在 Navicat 中打开一个新的查询窗口，先查看当前正在运行的 SQL：

```sql
SELECT
    pid,
    now() - query_start AS running_time,
    state,
    wait_event_type,
    wait_event,
    LEFT(query, 500) AS query_preview
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY running_time DESC;
```

如果确认是 `02_mature_clinical_features_navicat.sql` 中的长查询，可以先尝试取消：

```sql
SELECT pg_cancel_backend(这里填pid);
```

如果取消不掉，再终止连接：

```sql
SELECT pg_terminate_backend(这里填pid);
```

终止后不要直接重新整段执行 `02_mature_clinical_features_navicat.sql`。应按模块分段运行，每跑完一个模块就检查行数。

## 3. 分段执行顺序

推荐在 Navicat 中按下面顺序执行，而不是一次性全选运行：

1. `icu_features`
2. `outcome_features`
3. `procedure_features`
4. `microbiology_features`
5. `cohort_first24h_vitals`
6. `case_summary_mature`

由于截图显示 `past_history_flags` 和 `comorbidity_summary` 已经成功，不建议再重跑这两段。`cohort_first24h_vitals` 最重，建议使用新增的优化脚本 `sql/03_optimized_first24h_vitals_navicat.sql` 单独执行。如果前面的轻量表已经生成，就可以先导出论文所需的大部分表，不必等生命体征模块全部完成。

每个模块执行后用下面语句检查：

```sql
SELECT COUNT(*) FROM thesis.表名;
SELECT * FROM thesis.表名 LIMIT 20;
```

## 4. 性能优化原则

### 4.1 不导出历史诊断明细

`history_diagnoses` 只是为了生成 `past_history_flags`。论文不需要导出这个大表。如果执行太慢，可以直接跳过 `history_diagnoses` 明细表，改用历史诊断直接生成慢性病 flag。

论文中只需要解释：既往病史来自本次入院前同一患者的历史住院 ICD 诊断。

### 4.2 生命体征必须先筛 itemid

`chartevents` 不能直接全表 join 后再按 `d_items.label` 判断。应先建立生命体征 itemid 小表，再用 `itemid` 限制 `chartevents`：

```sql
DROP TABLE IF EXISTS thesis.vital_itemids;
CREATE TABLE thesis.vital_itemids AS
SELECT
    itemid,
    CASE
        WHEN label IN ('Heart Rate') THEN 'heart_rate'
        WHEN label IN ('Respiratory Rate') THEN 'respiratory_rate'
        WHEN label IN ('Temperature Fahrenheit') THEN 'temperature_f'
        WHEN label IN ('Temperature Celsius') THEN 'temperature_c'
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
```

然后先生成研究队列对应的 ICU 住院小表：

```sql
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
    ON thesis.cohort_icu_stays (stay_id, admittime);
```

这样比直接扫所有 `chartevents` 更稳。

项目中已经新增优化版脚本：

`sql/03_optimized_first24h_vitals_navicat.sql`

这个文件放在 `sql/` 目录，因为它是专门给 Navicat 执行的数据库层优化脚本。它只负责生成 `cohort_first24h_vitals`，不重复生成既往史、合并症和其他表。

当前建议操作：

1. 不再运行 `02_mature_clinical_features_navicat.sql` 中的生命体征段。
2. 单独执行 `03_optimized_first24h_vitals_navicat.sql`。
3. 如果该脚本仍然慢，先只执行到 `thesis.cohort_icu_stays`，检查 ICU 队列规模：

```sql
SELECT COUNT(*) FROM thesis.cohort_icu_stays;
```

4. 再执行到 `thesis.vital_events_24h`，检查生命体征中间表规模：

```sql
SELECT COUNT(*) FROM thesis.vital_events_24h;
SELECT vital_name, COUNT(*) FROM thesis.vital_events_24h GROUP BY vital_name ORDER BY COUNT(*) DESC;
```

5. 最后再生成 `thesis.cohort_first24h_vitals`。

### 4.3 先跑小样本验证

正式跑全量前，先抽 1000 个病例验证逻辑：

```sql
DROP TABLE IF EXISTS thesis.cohort_admissions_test;
CREATE TABLE thesis.cohort_admissions_test AS
SELECT *
FROM thesis.cohort_admissions
LIMIT 1000;
```

把成熟特征脚本中的 `thesis.cohort_admissions` 临时替换成 `thesis.cohort_admissions_test`。如果 1000 个病例都跑不完，说明 SQL 逻辑或索引存在问题，不能直接跑全量。

### 4.4 给中间表建索引

在生成基础表后，先执行：

```sql
CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_hadm
    ON thesis.cohort_admissions (subject_id, hadm_id);

CREATE INDEX IF NOT EXISTS idx_thesis_cohort_subject_time
    ON thesis.cohort_admissions (subject_id, admittime, dischtime);

CREATE INDEX IF NOT EXISTS idx_thesis_clean_dx_hadm
    ON thesis.cleaned_diagnosis_specialty_detail_6 (subject_id, hadm_id);

ANALYZE thesis.cohort_admissions;
ANALYZE thesis.cleaned_diagnosis_specialty_detail_6;
```

如果你有数据库权限，也可以检查原始 MIMIC 表索引是否存在。没有权限时不要强行给 `chartevents` 建大索引，因为建索引本身也可能运行很久。

## 5. 论文需要导出的表

从 `02_mature_clinical_features_navicat.sql` 生成的表里，论文最推荐导出：

1. `case_summary_mature.csv`：最终成熟病例总表。
2. `past_history_flags.csv`：既往病史慢性病标志。
3. `comorbidity_summary.csv`：本次住院合并症。
4. `cohort_first24h_vitals.csv`：首 24 小时生命体征。
5. `procedure_features.csv`：操作和治疗因素。
6. `microbiology_features.csv`：微生物因素。
7. `icu_features.csv`：ICU 暴露和 ICU 时长。
8. `outcome_features.csv`：结局指标。

一般不导出：

- `history_diagnoses.csv`：只是中间追溯表，行数大，论文正文不需要。

如果 `cohort_first24h_vitals` 因为 `chartevents` 过大暂时跑不出来，论文仍然可以先使用其他成熟特征表。正文中说明“生命体征仅在 ICU 有结构化记录，覆盖率单独报告”。

## 6. 毕业设计总体思路

建议论文题目方向：

**基于 MIMIC-IV v4 的多专科临床知识库构建与辅助诊疗智能体研究**

本课题不是简单做数据统计，也不是直接把病例丢给大模型，而是构建一条完整的数据治理到智能体应用的流程：

1. 从 MIMIC-IV v4 构建成人住院患者队列。
2. 基于 ICD 诊断和诊断文本，将病例映射到六个专科。
3. 提取人口学、诊断、既往史、合并症、检验、生命体征、用药、操作、微生物、ICU 暴露和结局等临床因素。
4. 使用单专科病例构建疾病目录、药品目录、检验分布、病药共现映射和风险规则。
5. 使用多专科病例测试多智能体辅助诊疗流程，包括病例路由、专科建议、协调决策和安全审核。

## 7. 研究对象与数据来源

数据来源为 MIMIC-IV v4。研究单位为一次住院，即 `hadm_id`。通过 `subject_id` 关联同一患者的历史住院、诊断、处方、检验、ICU 和微生物记录。

纳入标准：

- 成人患者，`anchor_age >= 18`。
- 有有效 `subject_id` 和 `hadm_id`。
- 入院时间和出院时间完整。
- 至少有一个诊断可映射到六个目标专科。

排除标准：

- 儿科病例。
- 入院或出院时间缺失。
- 出院时间早于或等于入院时间。
- 无目标专科诊断的住院记录。

## 8. 六专科设计

本研究关注六个临床常见且药物治疗和风险控制差异较大的专科：

- 心血管
- 神经
- 呼吸
- 肾内/泌尿
- 内分泌/代谢
- 消化

分科依据为 ICD 前缀和诊断英文标题关键词。每个诊断可映射到一个专科。对每个 `hadm_id` 统计命中的专科数量：

- 只涉及一个专科：单专科病例，用于构建专科知识库。
- 涉及两个及以上专科：多专科病例，用于智能体协同实验。

## 9. 临床因素处理

### 9.1 人口学和入院信息

来自 `patients` 和 `admissions`，包括性别、年龄、入院类型、入院来源、保险、语言、婚姻、种族和院内死亡标志。

### 9.2 当前诊断

来自 `diagnoses_icd` 和 `d_icd_diagnoses`。保留 ICD 版本、ICD 编码、诊断顺序和诊断名称。`seq_num` 最小的诊断作为主诊断，其他诊断作为合并症。

### 9.3 既往病史

既往病史不直接使用本次住院非主诊断，而是回溯同一患者本次入院前的历史住院诊断。提取慢性病 flag：

- 高血压
- 糖尿病
- 心力衰竭
- 冠心病
- 卒中
- COPD
- 慢性肾病
- 慢性肝病
- 恶性肿瘤

这种定义更符合医学论文中“既往病史”的含义。

### 9.4 检验

检验来自 `labevents` 和 `d_labitems`，限定入院后首 24 小时。当前核心指标包括肌酐、尿素氮、钾、钠、血糖、INR 和总胆红素。缺失值不插补，覆盖率单独统计。

### 9.5 生命体征

生命体征来自 ICU `chartevents`，包括心率、呼吸频率、体温、SpO2、收缩压、舒张压和平均动脉压。每项保留首 24 小时最小值、平均值和最大值。

注意：非 ICU 病例可能缺少结构化生命体征，因此论文需要报告覆盖率。

### 9.6 用药

处方来自 `prescriptions`。先保留原始处方，再对药名做标准化，生成清洗后药品表。知识库中药品目录来自单专科病例的药品频次统计，并用规则标注核心治疗药、支持治疗药和通用辅助药。

### 9.7 操作和治疗

操作来自 `procedures_icd`。重点标记机械通气、肾脏替代治疗、输血和侵入性置管等严重程度相关治疗因素。

### 9.8 微生物

微生物来自 `microbiologyevents`。提取培养记录数、是否培养阳性、病原体数量、是否存在耐药结果、标本类型和病原体列表。

### 9.9 ICU 和结局

ICU 信息来自 `icustays`，包括是否 ICU、ICU 次数和 ICU 时长。结局包括院内死亡、住院时长和 30 天再入院。结局只能用于评价，不能作为智能体早期推荐输入，以避免数据泄露。

## 10. 知识库构建

知识库以六个专科为单位构建，每个专科包括：

- 疾病目录：高频诊断、是否核心病种、疾病角色。
- 药物目录：高频药品、是否核心治疗药、药物角色。
- 检验画像：关键检验的非空数量、均值、中位数和四分位数。
- 病药映射：基于单专科病例同次住院诊断和药物共现。
- 风险规则：根据关键检验异常触发安全提醒。
- 示例病例：单专科和多专科病例样例。

论文中要强调：病药映射来自真实世界共现，不代表治疗因果关系。

## 11. 多智能体实验设计

多智能体系统建议分为四类角色：

1. 诊断路由智能体：根据病例诊断和专科列表判断涉及哪些专科。
2. 专科智能体：读取对应专科知识库，给出候选药物或处理建议。
3. 协调智能体：整合多专科意见，解决冲突。
4. 安全审核智能体：根据检验异常、既往病史、肾功能、凝血风险等对方案降权或提醒。

实验重点不是证明大模型能替代医生，而是验证“知识库约束 + 多智能体协作”能否提高建议的结构化、可解释性和安全性。

## 12. 论文评价指标

建议从三类指标评价：

### 12.1 数据质量指标

- 成人住院队列规模。
- 六专科诊断覆盖率。
- 单专科和多专科病例比例。
- 检验和生命体征覆盖率。
- 既往病史、操作、微生物、ICU 因素阳性比例。

### 12.2 知识库质量指标

- 各专科疾病目录数量。
- 各专科药物目录数量。
- 核心病种比例。
- 核心治疗药比例。
- 病药映射中可直接使用条目比例。

### 12.3 智能体实验指标

- 专科路由是否覆盖病例涉及专科。
- 推荐是否能引用知识库证据。
- 是否识别肾功能、凝血、电解质等风险。
- 多专科冲突是否能被协调。
- 输出格式是否稳定、可解释。

## 13. 推荐论文结构

第一章：绪论。说明临床多专科病例复杂、MIMIC-IV 数据价值、知识库和大模型结合的意义。

第二章：相关技术与数据基础。介绍 MIMIC-IV、ICD 编码、临床知识库、智能体和数据预处理方法。

第三章：数据预处理与队列构建。重点写成人住院队列、六专科映射、既往史、合并症、检验、生命体征、用药、操作、微生物、ICU 和结局处理。

第四章：多专科知识库构建。写疾病目录、药物目录、实验室画像、病药共现映射和风险规则。

第五章：多智能体辅助诊疗系统设计。写诊断路由、专科智能体、协调智能体和安全审核智能体。

第六章：实验结果与分析。写数据分布、知识库统计、病例实验和局限性。

第七章：总结与展望。

## 14. 当前最推荐的执行路线

考虑到你的 SQL 已经长时间未完成，建议按这个路线推进：

1. 终止当前长查询。
2. 确认基础表已经生成：`cohort_admissions`、`cleaned_diagnosis_specialty_detail_6`、`case_summary`。
3. 先执行轻量模块：`comorbidity_summary`、`icu_features`、`outcome_features`、`procedure_features`。
4. 再执行中等模块：`past_history_flags`、`microbiology_features`。
5. 最后单独优化执行 `cohort_first24h_vitals`。
6. 成功后再生成 `case_summary_mature`。
7. 导出论文需要的 8 个 CSV。

如果时间紧，允许先不跑生命体征模块。因为生命体征来自 ICU 超大表，跑不出来不会影响知识库主线。论文中可以把它作为可选补充特征，并报告当前版本未纳入或仅纳入 ICU 子队列。

## 15. 可写进论文的方法表述

本研究基于 MIMIC-IV v4 数据库构建成人住院病例队列，以一次住院记录作为分析单位。研究首先根据 ICD 诊断编码和诊断文本将病例映射至六个目标专科，并依据专科数量区分单专科和多专科病例。随后，从人口学信息、诊断、历史诊断、处方、实验室检查、生命体征、操作、微生物、ICU 暴露和临床结局等多个维度提取结构化特征。既往病史由患者本次入院前历史住院诊断识别，本次住院非主诊断作为合并症描述。实验室检查和生命体征均限定在入院后首 24 小时窗口内，以减少结局信息泄露。单专科病例用于构建专科知识库，多专科病例用于多智能体辅助诊疗实验。

本研究不将病药共现解释为治疗因果关系，而是作为真实世界用药模式下的候选证据。结局变量仅用于结果评价，不作为智能体早期决策输入。
