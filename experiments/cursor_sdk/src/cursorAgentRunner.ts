import { runCloudPrompt } from "./cloudApiClient.js";

export async function runCursorAgent(prompt: string): Promise<string> {
  return runCloudPrompt(prompt);
}

export function buildJsonPrompt(
  roleName: string,
  taskDescription: string,
  payload: unknown,
  outputShapeDescription: string,
): string {
  return [
    `你现在扮演 ${roleName}。`,
    taskDescription,
    "你必须严格输出 JSON，不允许输出 Markdown，不允许输出额外解释。",
    `输出结构要求: ${outputShapeDescription}`,
    "输入数据如下：",
    JSON.stringify(payload, null, 2),
  ].join("\n\n");
}
