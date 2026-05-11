# cloud_mdt_case_0 MDT 会诊链路图

来源 JSON：`experiments/outputs/cloud_mdt_case_0.json`

> 说明：本图按 MDT（多学科会诊）链路重画，重点表达“召集 MDT -> 多专科并行意见 -> 协调共识 -> 安全复核 -> 最终方案”，而不是单向流水线。

## Mermaid MDT 链路图

```mermaid
flowchart TD
    A["病例进入 MDT 池<br/>hadm_id: 22927623<br/>48岁女性<br/>主诊断: Dysphagia, unspecified<br/>关键检验: Cr 0.9 / BUN 8.0 / K 3.6 / Na 142 / INR 1.1 / TBil 1.0"]

    A --> B["诊断路由/MDT 召集<br/>识别需要会诊的专科<br/>唤起: 消化 + 心血管<br/>主导专科: 消化"]

    B --> C{"MDT 并行专科讨论<br/>Round 1: 各专科独立形成 proposal"}

    C --> D["消化专科意见<br/>相关诊断: 5个<br/>首选: pantoprazole<br/>备选: omeprazole, metronidazole,<br/>polyethylene glycol, ciprofloxacin iv<br/>风险提示: 0条"]

    C --> E["心血管专科意见<br/>相关诊断: 4个<br/>建议: furosemide, metoprolol tartrate,<br/>heparin, aspirin, warfarin<br/>风险提示: 0条"]

    D --> F["MDT 协调/共识形成<br/>Round 2: 协调智能体汇总各专科 proposal<br/>以主专科消化建议为核心<br/>评估跨专科支持与冲突"]
    E --> F

    D -. "低优先级/需谨慎: heparin 等" .-> F
    E -. "心血管候选含 heparin/抗凝药" .-> F

    F --> G1["候选共识方案 A<br/>主专科优先方案<br/>pantoprazole, omeprazole,<br/>metronidazole, polyethylene glycol,<br/>ciprofloxacin iv<br/>score: 10.53"]
    F --> G2["候选共识方案 B<br/>多专科平衡方案<br/>同方案 A<br/>score: 10.53"]
    F --> G3["候选共识方案 C<br/>保守低负荷方案<br/>pantoprazole, omeprazole,<br/>metronidazole<br/>score: 6.54"]

    G1 --> H["安全复核/二次筛查<br/>Round 3: 安全智能体检查风险规则<br/>触发风险数量: 0<br/>risk_penalty: 0"]
    G2 --> H
    G3 --> H

    H --> I{"MDT 最终裁决"}
    I --> J["最终采用方案 A<br/>主专科优先方案<br/>pantoprazole + omeprazole + metronidazole<br/>+ polyethylene glycol + ciprofloxacin iv<br/>final_score: 10.53"]

    J --> K["MDT 结论<br/>本病例由消化专科主导；<br/>心血管意见参与会诊但未进入最终用药主体；<br/>安全复核未发现需否决或降权的检验风险。"]
```

## 简要解读

- 这不是“诊断 -> 专科 -> 安全”的普通流水线，而是一次简化 MDT 链路：先召集相关专科，再由专科并行给出意见，随后进入协调共识和安全复核。
- case 0 唤起 `消化` 与 `心血管`，主导专科为 `消化`。
- 协调阶段保留了消化专科方案作为最终主体；心血管建议参与讨论，但没有进入最终方案主体。
- 安全复核触发风险数量为 `0`，所以最终采用 `plan_a 主专科优先方案`。
