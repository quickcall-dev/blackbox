# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Async LLM client wrappers used by the pipeline."""


import asyncio
import json
from typing import Any


class AsyncLLMClient:
    """Real async OpenAI client wrapper."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        concurrency: int = 30,
        model: str = "kimi-k2.6",
    ) -> None:
        import openai

        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=180)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.model = model

    async def call(self, system: str, user: str, response_format: dict) -> dict:
        async with self.semaphore:
            resp = await self.client.chat.completions.create(
                model=self.model,
                temperature=1,
                response_format=response_format,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        return json.loads(resp.choices[0].message.content)


class MockLLMClient:
    """Mock client for tests keyed by pipeline phase."""

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}

    def set_response(self, phase: str, response: Any) -> None:
        self._responses[phase] = response

    async def call(self, system: str, user: str, response_format: dict) -> dict:
        del user, response_format
        phase = self._detect_phase(system)
        resp = self._responses.get(phase, {})
        if isinstance(resp, Exception):
            raise resp
        return resp

    def _detect_phase(self, system: str) -> str:
        system_lower = system.lower()
        if "root cause analyst" in system_lower:
            return "rca"
        if "convention" in system_lower:
            return "convention"
        if "identify specific, actionable patterns" in system_lower:
            return "cluster"
        if "classify ai coding assistant mistake findings" in system_lower:
            return "behavior"
        if "classifying" in system_lower or "classify" in system_lower:
            return "classify"
        return "default"
