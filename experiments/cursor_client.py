from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from experiments.config import CursorSettings


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Cursor Agent 未返回可解析 JSON。")
    return json.loads(text[start : end + 1])


@dataclass
class CursorCloudAgentClient:
    settings: CursorSettings
    api_version: str = field(default="", init=False)

    def run_json(self, role_name: str, task_description: str, payload: dict[str, Any], output_shape: str) -> dict[str, Any]:
        text = self.run_prompt(self._build_json_prompt(role_name, task_description, payload, output_shape))
        return extract_json_object(text)

    def run_json_prompt(self, prompt: str) -> dict[str, Any]:
        return extract_json_object(self.run_prompt(prompt))

    def run_prompt(self, prompt: str) -> str:
        self._ensure_api_version()
        agent_id = self._create_agent(prompt)
        self._wait_for_agent(agent_id)
        return self._read_assistant_text(agent_id)

    def _build_json_prompt(
        self,
        role_name: str,
        task_description: str,
        payload: dict[str, Any],
        output_shape: str,
    ) -> str:
        return "\n\n".join(
            [
                f"你现在扮演 {role_name}。",
                task_description,
                "你必须严格输出 JSON，不允许输出 Markdown，不允许输出额外解释。",
                f"输出结构要求: {output_shape}",
                "输入数据如下：",
                json.dumps(payload, ensure_ascii=False, indent=2),
            ]
        )

    def _create_agent(self, prompt: str) -> str:
        if self.api_version == "v1":
            payload: dict[str, Any] = {
                "prompt": {"text": prompt},
                "repos": [{"url": self.settings.repo_url, "startingRef": self.settings.repo_ref}],
                "autoCreatePR": False,
            }
        else:
            payload = {
                "prompt": {"text": prompt},
                "source": {
                    "repository": self.settings.repo_url,
                    "ref": self.settings.repo_ref,
                },
                "target": {"autoCreatePr": False},
            }
        if self.settings.model and self.settings.model not in {"default", "auto"}:
            payload["model"] = {"id": self.settings.model} if self.api_version == "v1" else self.settings.model

        response = self._request_json(
            f"/{self.api_version}/agents",
            method="POST",
            body=payload,
        )
        agent_payload = response.get("agent", response)
        agent_id = str(agent_payload.get("id", ""))
        if not agent_id:
            raise RuntimeError(f"Cursor Cloud Agent 创建成功但未返回 id: {response}")
        return agent_id

    def _wait_for_agent(self, agent_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.settings.timeout_seconds
        while True:
            latest = self._request_json(f"/{self.api_version}/agents/{urllib.parse.quote(agent_id)}")
            status = str(latest.get("status", ""))
            if self.api_version == "v1":
                run_id = str(latest.get("latestRunId", ""))
                if not run_id:
                    raise RuntimeError(f"Cursor Cloud Agent 未返回 latestRunId: {latest}")
                run = self._request_json(
                    f"/v1/agents/{urllib.parse.quote(agent_id)}/runs/{urllib.parse.quote(run_id)}"
                )
                status = str(run.get("status", ""))
                if status not in {"CREATING", "RUNNING"}:
                    if status != "FINISHED":
                        raise RuntimeError(f"Cursor Cloud Agent 运行失败，状态: {status}，响应: {run}")
                    return run
            else:
                if status not in {"CREATING", "RUNNING"}:
                    if status != "FINISHED":
                        raise RuntimeError(f"Cursor Cloud Agent 运行失败，状态: {status}，响应: {latest}")
                    return latest
            if time.monotonic() > deadline:
                raise TimeoutError(f"Cursor Cloud Agent 超时未完成: {agent_id}")
            time.sleep(self.settings.poll_seconds)

    def _read_assistant_text(self, agent_id: str) -> str:
        if self.api_version == "v1":
            return self._read_assistant_text_v1(agent_id)
        conversation = self._request_json(f"/v0/agents/{urllib.parse.quote(agent_id)}/conversation")
        messages = conversation.get("messages", [])
        texts = [
            str(message.get("text", "")).strip()
            for message in messages
            if message.get("type") == "assistant_message" and str(message.get("text", "")).strip()
        ]
        if texts:
            return "\n\n".join(texts)
        raise RuntimeError(f"Cursor Cloud Agent 已完成，但未返回 assistant_message: {agent_id}")

    def _read_assistant_text_v1(self, agent_id: str) -> str:
        latest = self._request_json(f"/v1/agents/{urllib.parse.quote(agent_id)}")
        run_id = str(latest.get("latestRunId", ""))
        if not run_id:
            raise RuntimeError(f"Cursor Cloud Agent 未返回 latestRunId: {latest}")
        request = urllib.request.Request(
            f"{self.settings.api_base}/v1/agents/{urllib.parse.quote(agent_id)}/runs/{urllib.parse.quote(run_id)}/stream",
            headers={
                "Accept": "text/event-stream",
                "Authorization": self._auth_header(),
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(10, self.settings.timeout_seconds)) as response:
                text = response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Cursor Cloud API 请求失败: {exc.code} {detail}") from exc

        chunks = []
        for block in text.split("\n\n"):
            event = ""
            data = ""
            for line in block.splitlines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = line.split(":", 1)[1].strip()
            if event != "assistant" or not data:
                continue
            try:
                chunks.append(str(json.loads(data).get("text", "")))
            except json.JSONDecodeError:
                continue
        assistant_text = "".join(chunks).strip()
        if assistant_text:
            return assistant_text
        raise RuntimeError(f"Cursor Cloud Agent 已完成，但 v1 stream 未返回 assistant 文本: {agent_id}")

    def _ensure_api_version(self) -> None:
        if self.api_version:
            return
        try:
            self._request_json("/v1/me")
            self.api_version = "v1"
            return
        except RuntimeError as exc:
            v1_error = str(exc)
        try:
            self._request_json("/v0/repositories")
            self.api_version = "v0"
            return
        except RuntimeError as exc:
            raise RuntimeError(f"Cursor Cloud API 鉴权失败；v1={v1_error}; v0={exc}") from exc

    def _request_json(self, path: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": self._auth_header(),
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.api_base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=max(10, self.settings.timeout_seconds)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Cursor Cloud API 请求失败: {exc.code} {detail}") from exc

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self.settings.api_key}:".encode("utf-8")).decode("ascii")
        return f"Basic {token}"
