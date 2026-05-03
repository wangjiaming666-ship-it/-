# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is a multi-specialty medical AI agent system (多专科对话式多智能体系统) for clinical drug recommendation. It uses the MIMIC clinical database. There are two runtime implementations:

- **Python pipeline** (`experiments/`): the primary local pipeline, run via `python -m experiments.run_multi_agent_dialogue`
- **TypeScript/Cursor SDK** (`experiments/cursor_sdk/`): alternative implementation using Cursor Cloud Agents REST API

### Important caveats

1. **`kb_index.csv` paths**: The `knowledge_base/kb_index.csv` file was originally committed with Windows absolute paths (`C:\Users\...`). These have been converted to relative paths (`knowledge_base/<specialty>/<file>`) for cross-platform compatibility. The pipeline must be run from the repo root (`/workspace`) so that relative paths resolve correctly.

2. **MIMIC data files are gitignored**: The raw clinical CSV files (`multi_specialty_cases_v2.csv`, `cohort_admissions.csv`, `cleaned_diagnosis_specialty_detail_6.csv`, `cohort_first24h_labs.csv`, `case_summary.csv`) are listed in `.gitignore` and must be provided externally or generated as synthetic test data before running the pipeline. Without these files, `CaseBuilder` will fail.

3. **LLM is optional**: The system falls back to rule-based logic when `OPENAI_API_KEY` is not set. All agents (SpecialtyAgent, CoordinationAgent) have both LLM and rule-based code paths. The rule-based fallback produces valid results using the knowledge base.

4. **No formal linter or test suite**: The repo does not include a linter config, test framework, or test files. Type-checking the TypeScript code can be done with `cd experiments/cursor_sdk && npx tsc --noEmit`.

### Running the Python pipeline

```bash
# From repo root (/workspace)
python -m experiments.run_multi_agent_dialogue --case-index 0
python -m experiments.run_multi_agent_dialogue --hadm-id <hadm_id>
```

Output is saved to `experiments/outputs/<hadm_id>.json`.

### Running TypeScript type-check

```bash
cd experiments/cursor_sdk && npx tsc --noEmit
```

### Python dependencies

`pandas` and `matplotlib` (installed via pip). No `requirements.txt` exists in the repo; dependencies are inferred from imports.

### Node.js dependencies

`experiments/cursor_sdk/package.json` with `package-lock.json`; install via `npm install` in that directory.
