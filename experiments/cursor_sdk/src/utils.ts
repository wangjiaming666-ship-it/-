import fs from "node:fs";
import path from "node:path";

export function readJsonFile<T>(filePath: string): T {
  const content = fs.readFileSync(filePath, "utf-8");
  const normalized = content
    .replace(/\bNaN\b/g, "null")
    .replace(/\bInfinity\b/g, "null")
    .replace(/\b-Infinity\b/g, "null");
  return JSON.parse(normalized) as T;
}

export function writeJsonFile(filePath: string, data: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
}

export function parsePipeList(value: string | undefined | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function clamp(num: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, num));
}
