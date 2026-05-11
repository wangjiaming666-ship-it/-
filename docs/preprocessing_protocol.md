# MIMIC-IV v4 数据预处理与论文方法说明

## 1. 论文设计主线

本课题建议表述为：**基于 MIMIC-IV v4 的多专科临床知识库构建与辅助诊疗智能体研究**。研究不是直接把大模型用于诊疗，而是先从公开重症医学数据库中构建可复现的结构化病例队列，再生成六个专科方向的知识库，最后将知识库作为约束输入到多智能体辅助诊疗原型中。

整体流程如下：

1. 从 MIMIC-IV v4 的 PostgreSQL 数据库中抽取成人住院病例。
2. 基于 ICD 诊断和诊断文本将病例映射到六个专科：心血管、神经、呼吸、肾内/泌尿、内分泌/代谢、消化。
3. 整理诊断、处方、首 24 小时检验、生命体征、既往史、操作、微生物、ICU 暴露和结局指标，形成知识库构建与智能体病例输入所需的中间表。
4. 构建专科疾病目录、药物目录、检验分布、病药共现映射和风险规则。
5. 在多专科病例上进行智能体路由、专科建议、协调和安全审核实验。

## 2. 数据来源与队列单位

数据源为 MIMIC-IV v4 PostgreSQL 数据库。预处理脚本默认使用 `mimiciv_hosp` 作为住院模块 schema，并将结果写入 `thesis` schema。若本机数据库 schema 名称不同，可通过脚本参数调整。

队列单位为一次住院记录，即 `hadm_id`。患者身份使用 `subject_id` 与 `hadm_id` 共同关联诊断、处方和检验事件。

纳入标准：

- 年龄字段 `anchor_age` 大于等于 18 岁。
- 存在有效的 `subject_id`、`hadm_id`、`admittime` 和 `dischtime`。
- `dischtime` 晚于 `admittime`。
- 至少存在一个可映射到六专科之一的诊断。

排除标准：

- 儿科病例。
- 入院或出院时间缺失、住院时间异常的记录。
- 无法映射到六专科研究范围的住院记录。
- 诊断名称为空且无法通过 ICD 代码补充解释的记录。

## 3. 诊断预处理

诊断数据来自 `diagnoses_icd`，并与 `d_icd_diagnoses` 关联，保留以下字段：

- `subject_id`
- `hadm_id`
- `seq_num`
- `icd_version`
- `icd_code`
- `long_title`
- `specialty_group`

六专科映射采用 ICD 前缀与诊断文本关键词结合的可审计规则。ICD 规则用于保证主要映射依据可追溯，关键词规则用于补充部分文本能明确指向专科但 ICD 前缀不够直接的诊断。映射后的原始明细表为 `diagnosis_specialty_detail_6.csv`，清洗去重后的明细表为 `cleaned_diagnosis_specialty_detail_6.csv`。

论文中应说明：该分科规则用于数据治理和知识库原型构建，不等同于临床科室真实收治归属，也不作为疾病因果判断依据。

## 4. 处方预处理

处方数据来自 `prescriptions`。预处理保留住院内全部非空药品记录，并生成两层表：

- `cohort_prescriptions.csv`：保留原始处方字段，用于清洗前后对比。
- `cleaned_prescriptions.csv`：按 `subject_id`、`hadm_id` 和规范化后的 `drug_name` 去重，保留首次开始时间、末次停止时间和原始记录数。

药品名规范化包括去除首尾空格、合并多余空白、统一首字母大小写。后续知识库中的药物目录不是人工录入，而是在单专科病例中统计药品频次，再由 `build_specialty_kb.py` 的药物关键词规则标注为核心治疗药、支持治疗药或通用辅助药。

论文中应避免将“同次住院病药共现”解释为药物疗效证据。它只能作为真实世界用药模式的候选证据。

## 5. 既往病史与合并症预处理

医疗论文中不建议把“本次住院所有非主诊断”直接称为既往史。本项目将疾病背景拆成两层：

- `past_history_flags.csv`：严格的既往病史代理变量。定义为同一 `subject_id` 在本次 `admittime` 之前的历史住院诊断中已经出现过的慢性病，包括高血压、糖尿病、心衰、冠心病、卒中、COPD、慢性肾病、慢性肝病和恶性肿瘤。
- `comorbidity_summary.csv`：本次住院合并症。定义为本次 `hadm_id` 中除主诊断以外的其他诊断，用于描述本次病例复杂度。

这样处理可以避免将本次急性并发症误写成“既往病史”，也能保留临床背景复杂度。

## 6. 首 24 小时检验预处理

检验数据来自 `labevents`，并与 `d_labitems` 关联。时间窗限定为入院后 24 小时：

`admittime <= charttime < admittime + 24 hours`

输出表为 `cohort_first24h_labs.csv`，包含七项关键指标：

- `creatinine_24h`
- `bun_24h`
- `potassium_24h`
- `sodium_24h`
- `glucose_24h`
- `inr_24h`
- `bilirubin_total_24h`

当前 SQL 采用面向风险筛查的代表值口径：肌酐、尿素氮、钾、血糖、INR、总胆红素取首 24 小时最大值，钠取首 24 小时最小值。该口径适合描述早期异常风险，但论文中必须明确它不是均值或最后一次检验值。

缺失值不进行随意插补。知识库描述统计使用非空样本，病例展示和智能体风险规则中缺失值保留为空，图表单独报告覆盖率。

## 7. 首 24 小时生命体征预处理

生命体征来自 ICU `chartevents` 和 `d_items`，输出为 `cohort_first24h_vitals.csv`。时间窗同样限定为入院后首 24 小时，提取心率、呼吸频率、体温、血氧饱和度、收缩压、舒张压和平均动脉压。

每个生命体征保留最小值、平均值和最大值，并加入基础异常值过滤。例如心率限定在 20 到 250 次/分，SpO2 限定在 30% 到 100%。体温统一换算为华氏度，便于与 MIMIC-IV ICU 常见记录口径一致。

## 8. 操作、微生物、ICU 和结局因素

成熟版预处理新增 `sql/02_mature_clinical_features_navicat.sql`，可在 Navicat Premium Lite 17 中直接执行。该脚本生成以下表：

- `procedure_features.csv`：来自 `procedures_icd`，统计操作数量，并标记机械通气、肾脏替代治疗、输血、侵入性置管等治疗因素。
- `microbiology_features.csv`：来自 `microbiologyevents`，统计培养记录、培养阳性、病原体数量、耐药结果、标本类型和病原体列表。
- `icu_features.csv`：来自 `icustays`，记录是否 ICU、ICU 次数、首次 ICU 时间、末次 ICU 出科时间和 ICU 总时长。
- `outcome_features.csv`：包含院内死亡、住院时长和 30 天再入院标志。
- `case_summary_mature.csv`：把人口学、诊断、既往史、合并症、生命体征、操作、微生物、ICU 和结局整合为完整病例总表。

结局指标只用于描述和评价，不应作为智能体推荐药物时的输入，以避免数据泄露。

## 9. 单专科与多专科病例定义

对每个 `hadm_id` 统计其诊断映射到的不同专科数量：

- `specialty_cnt = 1`：写入 `single_specialty_cases.csv`。
- `specialty_cnt >= 2`：写入 `multi_specialty_cases_v2.csv`。

单专科病例用于构建相对纯净的专科疾病、用药和检验分布；多专科病例用于后续智能体路由、协调和安全审核实验。

## 10. 输出文件与项目衔接

预处理输出的 CSV 文件放在项目根目录，因为现有脚本默认从根目录读取数据：

- `build_specialty_kb.py` 读取 CSV 后生成 `knowledge_base/`。
- `draw_processed_data_figures.py` 读取 CSV 或 PostgreSQL 表后生成 `figures/processed_data/`。
- `draw_raw_vs_processed_comparison.py` 读取清洗前后 CSV 后生成 `figures/raw_vs_processed/`。
- `experiments/case_builder.py` 读取多专科病例、诊断和检验表，组装智能体实验病例。

新增的 `sql/01_extract_mimiciv_v4_cohort.sql` 放在 `sql/`，因为它是数据库层基础抽取逻辑。新增的 `sql/02_mature_clinical_features_navicat.sql` 也放在 `sql/`，因为它是 Navicat 可直接执行的成熟临床特征脚本。新增的 `preprocess_mimiciv_v4.py` 放在项目根目录，因为它负责执行预处理、导出 CSV，并与现有根目录脚本保持一致。

## 11. 推荐运行方式

如果需要从 PostgreSQL 重新生成全部中间表和 CSV，可运行：

```powershell
& "C:\anaconda\python.exe" "preprocess_mimiciv_v4.py" `
  --pg-dsn "host=localhost port=5432 dbname=mimiciv user=wjm password=你的密码" `
  --run-sql `
  --out-schema thesis `
  --hosp-schema mimiciv_hosp
```

若数据库中的 MIMIC-IV schema 名为 `hosp`，则将参数改为：

```powershell
& "C:\anaconda\python.exe" "preprocess_mimiciv_v4.py" `
  --pg-dsn "host=localhost port=5432 dbname=mimiciv user=wjm password=你的密码" `
  --run-sql `
  --out-schema thesis `
  --hosp-schema hosp `
  --patient-schema hosp
```

生成 CSV 后，重新构建知识库和图表：

```powershell
& "C:\anaconda\python.exe" "build_specialty_kb.py"
& "C:\anaconda\python.exe" "draw_kb_figures.py"
& "C:\anaconda\python.exe" "draw_processed_data_figures.py" --input-mode csv
& "C:\anaconda\python.exe" "draw_raw_vs_processed_comparison.py"
```

如果要生成成熟版临床特征，可以先用基础脚本生成 `thesis.cohort_admissions`、`thesis.cleaned_diagnosis_specialty_detail_6`、`thesis.case_summary` 等基础表，再在 Navicat Premium Lite 17 中执行成熟特征脚本：

1. 基础表：运行 `preprocess_mimiciv_v4.py --run-sql`，或在 Navicat 中执行基础 SQL 时将 `:out_schema`、`:hosp_schema`、`:patient_schema` 分别替换为实际 schema 名称。
2. 成熟特征：执行 `sql/02_mature_clinical_features_navicat.sql`。该脚本默认使用 `thesis`、`mimiciv_hosp` 和 `mimiciv_icu`，如果数据库中叫 `hosp` / `icu`，用 Navicat 的替换功能统一替换即可。

也可以用命令行执行成熟特征并导出：

```powershell
& "C:\anaconda\python.exe" "preprocess_mimiciv_v4.py" `
  --pg-dsn "host=localhost port=5432 dbname=mimiciv user=wjm password=你的密码" `
  --run-mature-sql `
  --include-mature
```

## 12. 论文中需要主动说明的局限

1. 专科映射依赖 ICD 前缀和关键词规则，存在误分或漏分可能。
2. 药品推荐候选来自同次住院共现，不代表因果疗效。
3. 首 24 小时检验取异常风险方向的代表值，适合风险筛查，不等同于完整病程刻画。
4. 缺失检验值不触发风险规则，可能低估部分病例风险。
5. 既往病史来自本次入院前历史住院 ICD 诊断，不能覆盖未在 MIMIC-IV 中记录的院外病史。
6. ICU 生命体征来自 ICU `chartevents`，非 ICU 住院病例可能缺失该部分数据。
7. MIMIC-IV 是单中心回顾性数据库，外部泛化能力需要进一步验证。
