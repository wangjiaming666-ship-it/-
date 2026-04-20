import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const ROOT_DIR = path.resolve(__dirname, "..", "..", "..");
export const EXPERIMENTS_DIR = path.join(ROOT_DIR, "experiments");
export const OUTPUTS_DIR = path.join(EXPERIMENTS_DIR, "outputs");
export const KNOWLEDGE_BASE_DIR = path.join(ROOT_DIR, "knowledge_base");
export const AGENT_SPECS_DIR = path.join(ROOT_DIR, "agent_specs");

export const PYTHON_EXE = process.env.PYTHON_EXE ?? "C:\\anaconda\\python.exe";
export const CURSOR_API_KEY = process.env.CURSOR_API_KEY ?? "";
export const CURSOR_MODEL = process.env.CURSOR_MODEL ?? "default";
export const CURSOR_CLOUD_REPO_URL = process.env.CURSOR_CLOUD_REPO_URL ?? "";
export const CURSOR_CLOUD_REPO_REF = process.env.CURSOR_CLOUD_REPO_REF ?? "main";
export const CURSOR_CLOUD_POLL_MS = Number(process.env.CURSOR_CLOUD_POLL_MS ?? "5000");
export const CURSOR_CLOUD_TIMEOUT_MS = Number(process.env.CURSOR_CLOUD_TIMEOUT_MS ?? "600000");

export const ACTIVE_SPECIALTIES = [
  "心血管",
  "神经",
  "呼吸",
  "肾内/泌尿",
  "内分泌/代谢",
  "消化",
];

export function requireCursorApiKey(): string {
  if (!CURSOR_API_KEY) {
    throw new Error("未配置 CURSOR_API_KEY，无法调用 Cursor Cloud Agents REST。");
  }
  return CURSOR_API_KEY;
}

export function requireCursorCloudRepoUrl(): string {
  if (!CURSOR_CLOUD_REPO_URL) {
    throw new Error(
      "未配置 CURSOR_CLOUD_REPO_URL。Cloud Agents REST 必须绑定 GitHub 仓库；请先在 Cursor Dashboard 的 Integrations 中连接 GitHub，并在环境变量里提供仓库 URL。",
    );
  }
  return CURSOR_CLOUD_REPO_URL;
}
