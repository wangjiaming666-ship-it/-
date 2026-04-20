import { execFileSync } from "node:child_process";
import path from "node:path";

import { EXPERIMENTS_DIR, OUTPUTS_DIR, PYTHON_EXE } from "./config.js";
import type { CaseRecord } from "./types.js";
import { readJsonFile } from "./utils.js";

export function exportCaseBundle(caseIndex: number, hadmId = ""): CaseRecord {
  const outputPath = path.join(
    OUTPUTS_DIR,
    hadmId ? `${hadmId}_case_bundle.json` : `case_index_${caseIndex}_case_bundle.json`,
  );
  const scriptPath = path.join(EXPERIMENTS_DIR, "export_case_bundle.py");

  const args = [scriptPath, "--output", outputPath];
  if (hadmId) {
    args.push("--hadm-id", hadmId);
  } else {
    args.push("--case-index", String(caseIndex));
  }

  execFileSync(PYTHON_EXE, args, {
    cwd: path.join(EXPERIMENTS_DIR, ".."),
    stdio: "inherit",
  });
  return readJsonFile<CaseRecord>(outputPath);
}
