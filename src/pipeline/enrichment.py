# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Batched enrichment with retry and progress tracking."""

import asyncio
import logging
import time
from typing import Any, Callable

from src.rca.prompts import (
    BEHAVIOR_SCHEMA,
    BEHAVIOR_SYSTEM_PROMPT,
    CLUSTER_SCHEMA,
    CLUSTER_SYSTEM_PROMPT,
    CONVENTION_SCHEMA,
    CONVENTION_SYSTEM_PROMPT,
)

MODEL = "deepseek-v4-pro"
BEHAVIOR_BATCH_SIZE = 5
CLUSTER_BATCH_SIZE = 30
MAX_PATTERN_SIZE = 15
CONVENTION_BATCH_SIZE = 10


class _Progress:
    """Async-safe progress counter."""

    def __init__(self, total: int, label: str, logger: logging.Logger, every: int = 0):
        self.total = total
        self.label = label
        self.logger = logger
        self.done = 0
        self.errors = 0
        self._lock = asyncio.Lock()
        self.every = every or max(1, total // 10)
        self._t0 = time.time()

    async def tick(self, error: bool = False):
        async with self._lock:
            self.done += 1
            if error:
                self.errors += 1
            if self.done == self.total or self.done % self.every == 0:
                elapsed = time.time() - self._t0
                rate = self.done / elapsed if elapsed > 0 else 0
                eta = (self.total - self.done) / rate if rate > 0 else 0
                err_str = f", {self.errors} errors" if self.errors else ""
                self.logger.info(
                    f"  [{self.label}] {self.done}/{self.total} done "
                    f"({self.done * 100 // self.total}%) "
                    f"[{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining{err_str}]"
                )


async def _call_llm(
    client: Any,
    system: str,
    user: str,
    response_format: dict,
    semaphore: asyncio.Semaphore,
    logger: logging.Logger,
    track_tokens: Callable | None = None,
    retries: int = 2,
    default: dict | None = None,
) -> dict:
    """LLM call with json_schema strict mode and retry."""
    if default is None:
        default = {}
    for attempt in range(retries + 1):
        async with semaphore:
            try:
                resp = await client.call(system, user, response_format)
                if track_tokens and hasattr(resp, "usage"):
                    track_tokens(resp.usage.prompt_tokens, resp.usage.completion_tokens)
                return resp
            except Exception as exc:
                if attempt == retries:
                    logger.warning(f"LLM call failed after {retries + 1} attempts: {exc}")
                    return default
                wait = 2 ** attempt
                logger.info(f"LLM call failed (attempt {attempt + 1}), retrying in {wait}s...")
                await asyncio.sleep(wait)
    return default


def _normalize_response(result: Any, key: str) -> dict:
    """Handle both wrapped dicts and raw lists from json_object mode."""
    if isinstance(result, list):
        # Filter out non-dict items (e.g. stray strings from malformed LLM output)
        return {key: [item for item in result if isinstance(item, dict)]}
    if isinstance(result, dict):
        # Ensure list values only contain dicts
        out = dict(result)
        for k, v in out.items():
            if isinstance(v, list):
                out[k] = [item for item in v if isinstance(item, dict)]
        return out
    return {key: []}


async def phase4a_behavior_classify(
    findings: list[dict],
    llm_client: Any,
    semaphore: asyncio.Semaphore,
    logger: logging.Logger,
    track_tokens: Callable | None = None,
) -> list[dict]:
    """Classify findings into agent_behavior / code_correctness / architecture."""
    if not findings:
        return findings

    batches = [
        findings[i : i + BEHAVIOR_BATCH_SIZE]
        for i in range(0, len(findings), BEHAVIOR_BATCH_SIZE)
    ]
    progress = _Progress(len(batches), "P4a behavior", logger)

    async def _classify_batch(batch: list[dict]) -> dict:
        prompt = "\n".join(
            f"[{idx}] {f.get('agents_md_rule', '')}"
            for idx, f in enumerate(batch)
        )
        result = await _call_llm(
            llm_client, BEHAVIOR_SYSTEM_PROMPT, prompt, BEHAVIOR_SCHEMA,
            semaphore, logger, track_tokens,
            default={"classifications": []},
        )
        await progress.tick()
        return _normalize_response(result, "classifications")

    results = await asyncio.gather(*[_classify_batch(b) for b in batches])

    for batch_index, result in enumerate(results):
        by_index = {item.get("index"): item for item in result.get("classifications", [])}
        for offset, finding in enumerate(batches[batch_index]):
            classification = by_index.get(offset, {})
            finding["rule_type"] = classification.get("rule_type", "unknown")
            finding["type_confidence"] = classification.get("confidence", "low")
            finding["requires_code_change"] = classification.get("requires_code_change")

    return findings


async def phase4b_recurrence_cluster(
    findings: list[dict],
    llm_client: Any,
    semaphore: asyncio.Semaphore,
    logger: logging.Logger,
    track_tokens: Callable | None = None,
) -> tuple[list[dict], list[dict]]:
    """Cluster findings into patterns and mark recurrence."""
    if not findings:
        return [], findings

    prompt = "\n".join(
        f"[{idx}] {f.get('agents_md_rule', '')}"
        for idx, f in enumerate(findings)
    )

    result = await _call_llm(
        llm_client, CLUSTER_SYSTEM_PROMPT, prompt, CLUSTER_SCHEMA,
        semaphore, logger, track_tokens,
        default={"patterns": [], "one_off_indices": list(range(len(findings)))},
    )
    result = _normalize_response(result, "patterns")

    patterns = result.get("patterns", [])
    one_off_indices = result.get("one_off_indices", list(range(len(findings))))

    # Split oversized patterns
    split_patterns = []
    for pattern in patterns:
        indices = pattern.get("finding_indices", [])
        if len(indices) <= MAX_PATTERN_SIZE:
            split_patterns.append(pattern)
            continue
        # Split into chunks
        for i in range(0, len(indices), MAX_PATTERN_SIZE):
            chunk = indices[i : i + MAX_PATTERN_SIZE]
            split_patterns.append({
                "label": f"{pattern['label']} (part {i // MAX_PATTERN_SIZE + 1})",
                "description": pattern["description"],
                "finding_indices": chunk,
            })

    # Mark findings
    covered = set()
    for pattern in split_patterns:
        indices = pattern.get("finding_indices", [])
        covered.update(indices)
        is_recurring = len(indices) >= 2
        for index in indices:
            if 0 <= index < len(findings):
                findings[index]["pattern_label"] = pattern.get("label", "")
                findings[index]["pattern_description"] = pattern.get("description", "")
                findings[index]["is_recurring"] = is_recurring

    for index, finding in enumerate(findings):
        if index not in covered:
            finding["pattern_label"] = ""
            finding["pattern_description"] = ""
            finding["is_recurring"] = False

    return split_patterns, findings


async def phase4c_convention_detect(
    findings: list[dict],
    llm_client: Any,
    semaphore: asyncio.Semaphore,
    logger: logging.Logger,
    track_tokens: Callable | None = None,
) -> list[dict]:
    """Detect conventions from wrong_approach findings."""
    wrong_approach = [
        (idx, f) for idx, f in enumerate(findings)
        if f.get("category") == "wrong_approach"
    ]
    if not wrong_approach:
        return []

    batches = [
        wrong_approach[i : i + CONVENTION_BATCH_SIZE]
        for i in range(0, len(wrong_approach), CONVENTION_BATCH_SIZE)
    ]
    progress = _Progress(len(batches), "P4c convention", logger)

    async def _detect_batch(batch: list[tuple]) -> dict:
        prompt = "\n".join(
            f"[{batch_idx}] {f.get('agents_md_rule', '')}"
            for batch_idx, (_, f) in enumerate(batch)
        )
        result = await _call_llm(
            llm_client, CONVENTION_SYSTEM_PROMPT, prompt, CONVENTION_SCHEMA,
            semaphore, logger, track_tokens,
            default={"results": []},
        )
        await progress.tick()
        return _normalize_response(result, "results")

    results = await asyncio.gather(*[_detect_batch(b) for b in batches])

    conventions = []
    for batch_index, result in enumerate(results):
        by_index = {item.get("index"): item for item in result.get("results", [])}
        for batch_offset, (finding_index, finding) in enumerate(batches[batch_index]):
            item = by_index.get(batch_offset, {})
            finding["is_convention"] = item.get("is_convention", False)
            finding["convention_type"] = item.get("convention_type", "none")
            finding["dont_do"] = item.get("dont_do", "")
            finding["do_instead"] = item.get("do_instead", "")
            if finding["is_convention"]:
                conventions.append({
                    "finding_index": finding_index,
                    "convention_type": finding["convention_type"],
                    "dont_do": finding["dont_do"],
                    "do_instead": finding["do_instead"],
                })

    for finding in findings:
        finding.setdefault("is_convention", False)
        finding.setdefault("convention_type", "none")

    return conventions
