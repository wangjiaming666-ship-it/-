import {
  CURSOR_API_KEY,
  CURSOR_CLOUD_POLL_MS,
  CURSOR_CLOUD_REPO_URL,
  CURSOR_CLOUD_REPO_REF,
  CURSOR_CLOUD_TIMEOUT_MS,
  CURSOR_MODEL,
  requireCursorApiKey,
  requireCursorCloudRepoUrl,
} from "./config.js";

const CURSOR_API_BASE = "https://api.cursor.com";

export interface CloudRepositoryItem {
  owner: string;
  name: string;
  repository: string;
}

interface CloudRepositoriesResponse {
  repositories: CloudRepositoryItem[];
}

export interface CloudAgentMessage {
  id: string;
  type: string;
  text: string;
}

interface CloudConversationResponse {
  id: string;
  messages: CloudAgentMessage[];
}

export interface CloudAgentResponse {
  id: string;
  name?: string;
  status: string;
  summary?: string;
  createdAt?: string;
  source?: {
    repository?: string;
    ref?: string;
  };
  target?: {
    branchName?: string;
    url?: string;
    prUrl?: string;
    autoCreatePr?: boolean;
  };
}

function buildBasicAuthHeader(): string {
  const apiKey = requireCursorApiKey();
  return `Basic ${Buffer.from(`${apiKey}:`, "utf-8").toString("base64")}`;
}

function getCloudModelForRequest(): string | undefined {
  if (!CURSOR_MODEL || CURSOR_MODEL === "default" || CURSOR_MODEL === "auto") {
    return undefined;
  }
  return CURSOR_MODEL;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readErrorBody(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) {
    return `${response.status} ${response.statusText}`;
  }
  try {
    const json = JSON.parse(text) as Record<string, any>;
    if (json.error?.message) {
      return `${response.status} ${json.error.message}`;
    }
    if (json.message) {
      return `${response.status} ${json.message}`;
    }
  } catch {
    return `${response.status} ${text}`;
  }
  return `${response.status} ${text}`;
}

export async function cursorApiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${CURSOR_API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: buildBasicAuthHeader(),
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Cursor Cloud API 请求失败: ${await readErrorBody(response)}`);
  }

  return (await response.json()) as T;
}

export async function listCloudRepositories(): Promise<CloudRepositoryItem[]> {
  const response = await cursorApiRequest<CloudRepositoriesResponse>("/v0/repositories");
  return response.repositories ?? [];
}

export async function createCloudAgent(prompt: string): Promise<CloudAgentResponse> {
  const repository = requireCursorCloudRepoUrl();
  const model = getCloudModelForRequest();
  const payload: Record<string, unknown> = {
    prompt: { text: prompt },
    source: {
      repository,
      ref: CURSOR_CLOUD_REPO_REF,
    },
    target: {
      autoCreatePr: false,
    },
  };

  if (model) {
    payload.model = model;
  }

  return cursorApiRequest<CloudAgentResponse>("/v0/agents", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function getCloudAgent(agentId: string): Promise<CloudAgentResponse> {
  return cursorApiRequest<CloudAgentResponse>(`/v0/agents/${agentId}`);
}

export async function getCloudConversation(agentId: string): Promise<CloudConversationResponse> {
  return cursorApiRequest<CloudConversationResponse>(`/v0/agents/${agentId}/conversation`);
}

export async function waitForCloudAgent(agentId: string): Promise<CloudAgentResponse> {
  const startedAt = Date.now();
  let latest = await getCloudAgent(agentId);

  while (latest.status === "CREATING" || latest.status === "RUNNING") {
    if (Date.now() - startedAt > CURSOR_CLOUD_TIMEOUT_MS) {
      throw new Error(`Cloud Agent 超时未完成: ${agentId}`);
    }
    await sleep(CURSOR_CLOUD_POLL_MS);
    latest = await getCloudAgent(agentId);
  }

  return latest;
}

export async function runCloudPrompt(prompt: string): Promise<string> {
  const created = await createCloudAgent(prompt);
  const finished = await waitForCloudAgent(created.id);

  if (finished.status !== "FINISHED") {
    throw new Error(
      `Cloud Agent 运行失败，状态: ${finished.status}${finished.target?.url ? `，详情: ${finished.target.url}` : ""}`,
    );
  }

  const conversation = await getCloudConversation(created.id);
  const text = conversation.messages
    .filter((message) => message.type === "assistant_message")
    .map((message) => message.text?.trim())
    .filter(Boolean)
    .join("\n\n");

  if (text) {
    return text;
  }

  if (finished.summary?.trim()) {
    return finished.summary.trim();
  }

  throw new Error(`Cloud Agent 已完成，但未返回 assistant_message: ${created.id}`);
}

export function getCloudRuntimeSummary(): Record<string, string> {
  return {
    apiKeyConfigured: CURSOR_API_KEY ? "yes" : "no",
    repository: CURSOR_CLOUD_REPO_URL || "",
    ref: CURSOR_CLOUD_REPO_REF,
    model: CURSOR_MODEL,
  };
}
