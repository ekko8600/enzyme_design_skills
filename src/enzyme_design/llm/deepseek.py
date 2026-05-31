"""DeepSeek V4 Pro provider using the OpenAI-compatible API."""

from __future__ import annotations

import json
from typing import Any
from urllib import request

from enzyme_design.config import Settings
from enzyme_design.llm.base import LLMProvider


class DeepSeekProvider(LLMProvider):
    """Small dependency-light DeepSeek client.

    The implementation uses urllib to avoid forcing SDK dependencies in agent
    sandboxes. Users can still install the OpenAI SDK if they prefer a custom
    provider later.
    """

    def __init__(self, settings: Settings):
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek analysis.")
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=120) as response:  # noqa: S310 - user-configured LLM endpoint.
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def structured_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        content = self.chat(messages, temperature=temperature)
        return _extract_json(content)


def _extract_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model response did not contain a JSON object.")
    return json.loads(stripped[start : end + 1])
