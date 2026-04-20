from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from experiments.config import LLMSettings


class OpenAICompatibleClient:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.settings.enabled:
            raise RuntimeError("未配置 OPENAI_API_KEY，无法调用 LLM。")

        payload = {
            "model": self.settings.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        req = urllib.request.Request(
            self.settings.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM 接口调用失败: {detail}") from exc

        content = body["choices"][0]["message"]["content"]
        return json.loads(content)
