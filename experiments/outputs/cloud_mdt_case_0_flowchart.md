# cloud_mdt_case_0 整体结果流程图

来源 JSON：`experiments/outputs/cloud_mdt_case_0.json`

## Mermaid 流程图

```mermaid
flowchart TD
    A["病例输入<br/>hadm_id: 22927623<br/>subject_id: 10000117<br/>性别: F，年龄: 48<br/>主诊断: Dysphagia, unspecified"] --> B["诊断路由智能体"]

    B --> C["唤起专科<br/>消化、心血管"]
    B --> D["主专科判定<br/>消化<br/>依据: 各专科相关诊断数量"]

    C --> E["消化智能体"]
    C --> F["心血管智能体"]

    E --> E1["相关诊断 5 个<br/>Dysphagia<br/>胃十二指肠血管发育异常<br/>膈疝<br/>二尖瓣脱垂<br/>尼古丁依赖史"]
    E --> E2["Top 药物建议<br/>1. pantoprazole (0.95)<br/>2. omeprazole (0.72)<br/>3. metronidazole (0.67)<br/>4. polyethylene glycol (0.62)<br/>5. ciprofloxacin iv (0.57)"]
    E --> E3["专科风险提示<br/>0 条"]
    E --> E4["低优先级/避免药物<br/>potassium chloride、sw、acetaminophen、calcium gluconate、magnesium sulfate、ondansetron、heparin、hydromorphone"]

    F --> F1["相关诊断 4 个<br/>骨质疏松<br/>焦虑障碍<br/>胃食管反流<br/>循环/呼吸相关症状"]
    F --> F2["Top 药物建议<br/>1. furosemide (0.95)<br/>2. metoprolol tartrate (0.95)<br/>3. heparin (0.95)<br/>4. aspirin (0.95)<br/>5. warfarin (0.95)"]
    F --> F3["专科风险提示<br/>0 条"]

    E2 --> G["协调智能体<br/>整合专科建议并生成候选方案"]
    F2 --> G

    G --> H1["plan_a 主专科优先方案<br/>pantoprazole, omeprazole,<br/>metronidazole, polyethylene glycol,<br/>ciprofloxacin iv<br/>aggregate_score: 10.53"]
    G --> H2["plan_b 多专科平衡方案<br/>pantoprazole, omeprazole,<br/>metronidazole, polyethylene glycol,<br/>ciprofloxacin iv<br/>aggregate_score: 10.53"]
    G --> H3["plan_c 保守低负荷方案<br/>pantoprazole, omeprazole,<br/>metronidazole<br/>aggregate_score: 6.54"]

    H1 --> I["安全智能体筛查"]
    H2 --> I
    H3 --> I

    I --> J["关键检验值<br/>肌酐 0.9、BUN 8.0<br/>钾 3.6、钠 142.0<br/>葡萄糖 85.0、INR 1.1<br/>总胆红素 1.0"]
    I --> K["触发风险数量: 0<br/>risk_penalty: 0"]

    K --> L["最终方案<br/>plan_a 主专科优先方案<br/>pantoprazole, omeprazole,<br/>metronidazole, polyethylene glycol,<br/>ciprofloxacin iv<br/>final_score: 10.53"]

    L --> M["结论<br/>安全智能体选择风险惩罚后得分最高的方案；<br/>本病例无触发风险，最终采用主专科优先方案。"]
```

## 简要解读

- 病例 `22927623` 被路由到 `消化` 和 `心血管` 两个专科，主专科为 `消化`。
- 消化智能体的推荐药物构成了最终方案主体。
- 安全智能体没有发现触发风险，因此候选方案未受到风险惩罚。
- `plan_a` 与 `plan_b` 得分相同，排序后最终选择 `plan_a 主专科优先方案`。
