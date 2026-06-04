# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Pipeline orchestrator for standalone trace analysis."""


import asyncio
import logging
import traceback
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

from src.pipeline.annotator import annotate_unified
from src.utils.logging import get_logger, PhaseTimer, ProgressLogger
from src.classify.prompts import CLASSIFICATION_SCHEMA, CLASSIFICATION_SYSTEM_PROMPT
from src.classify.runner import (
    build_classification_prompt,
    get_rca_triggers,
    get_session_skeleton,
    parse_classifications,
)
from src.pipeline.context_builder import (
    build_context_window,
    extract_user_messages,
    format_context_for_prompt,
)
from src.pipeline.dedup import dedup_annotated_messages
from src.pipeline.enrichment import (
    phase4a_behavior_classify,
    phase4b_recurrence_cluster,
    phase4c_convention_detect,
)
from src.llm.client import MockLLMClient
from src.normalizer.unified import NormalizedMessage
from src.rca.prompts import (
    BEHAVIOR_SCHEMA,
    BEHAVIOR_SYSTEM_PROMPT,
    CLUSTER_SCHEMA,
    CLUSTER_SYSTEM_PROMPT,
    CONVENTION_SCHEMA,
    CONVENTION_SYSTEM_PROMPT,
    RCA_SCHEMA,
    RCA_SYSTEM_PROMPT,
    RCA_USER_TEMPLATE,
)
from src.storage.run_store import RunStore


class Pipeline:
    """Run phases P0-P6 over in-memory session payloads."""

    def __init__(self, llm_client: Any, store: RunStore) -> None:
        self.llm = llm_client
        self.store = store
        self.logger = get_logger("pipeline")

    async def run(self, run_id: str, sessions: dict[str, dict]) -> None:
        if self.store.get_run(run_id) is None:
            self.store.create_run(run_id)
        self.store.update_run_status(run_id, "running")
        self.logger.info("[%s] pipeline started sessions=%d", run_id, len(sessions))

        try:
            with PhaseTimer("p0_normalize", run_id, self.logger):
                self._p0_normalize(run_id, sessions)

            disk = self.store._disk
            if disk:
                cached_p1 = disk.load_stage(run_id, "p1_classify")
                if cached_p1:
                    self.logger.info("[%s] p1_classify loaded from disk", run_id)
                    self.store.update_stage(run_id, "p1_classify", status="done", data=cached_p1.get("data"))
                else:
                    with PhaseTimer("p1_classify", run_id, self.logger):
                        await self._p1_classify(run_id, sessions)
            else:
                with PhaseTimer("p1_classify", run_id, self.logger):
                    await self._p1_classify(run_id, sessions)

            with PhaseTimer("p2_context", run_id, self.logger):
                self._p2_context(run_id, sessions)

            if not self._has_triggers(run_id):
                self.logger.info("[%s] no triggers found — skipping rca+enrichment", run_id)
                self._complete_no_trigger_run(run_id, sessions)
                self.store.update_run_status(run_id, "done")
                return

            if disk:
                cached_p3 = disk.load_stage(run_id, "p3_rca")
                if cached_p3:
                    self.logger.info("[%s] p3_rca loaded from disk", run_id)
                    self.store.update_stage(run_id, "p3_rca", status="done", data=cached_p3.get("data"))
                else:
                    with PhaseTimer("p3_rca", run_id, self.logger):
                        await self._p3_rca(run_id)
            else:
                with PhaseTimer("p3_rca", run_id, self.logger):
                    await self._p3_rca(run_id)

            with PhaseTimer("p4_enrich", run_id, self.logger):
                await self._p4_enrich(run_id)

            with PhaseTimer("p5_aggregate", run_id, self.logger):
                self._p5_aggregate(run_id, sessions)

            with PhaseTimer("p6_scope", run_id, self.logger):
                self._p6_scope(run_id)

            self.store.update_run_status(run_id, "done")
            self.logger.info("[%s] pipeline done", run_id)
        except Exception:
            self.store.update_run_status(run_id, "error")
            run = self.store.get_run(run_id)
            if run is not None:
                run.error = traceback.format_exc()
            raise_stage = self._current_running_stage(run_id)
            if raise_stage is not None:
                self.store.update_stage(run_id, raise_stage, status="error", error=run.error if run else "unknown")
            self.logger.exception("[%s] pipeline failed at stage=%s", run_id, raise_stage)

    def _current_running_stage(self, run_id: str) -> str | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        for name, stage in run.stages.items():
            if stage.status == "running":
                return name
        return None

    def _has_triggers(self, run_id: str) -> bool:
        classification_data = self.store.get_stage_output(run_id, "p1_classify") or {}
        return classification_data.get("trigger_count", 0) > 0

    def _complete_no_trigger_run(self, run_id: str, sessions: dict[str, dict]) -> None:
        self.store.update_stage(run_id, "p3_rca", status="done", data={"findings": []})
        self.store.update_stage(
            run_id,
            "p4a_behavior",
            status="done",
            data={"findings": [], "count": 0},
        )
        self.store.update_stage(
            run_id,
            "p4b_cluster",
            status="done",
            data={"patterns": [], "one_off_indices": []},
        )
        self.store.update_stage(
            run_id,
            "p4c_convention",
            status="done",
            data={"conventions": [], "count": 0},
        )
        self._p5_aggregate(run_id, sessions)
        self._p6_scope(run_id)

    def _normalize_messages(self, session_id: str, raw: dict) -> list[NormalizedMessage]:
        messages = []
        for msg_id, payload in raw.get("messages", {}).items():
            messages.append(
                NormalizedMessage(
                    id=msg_id,
                    session_id=session_id,
                    source=raw.get("source", "claude_code"),
                    source_schema_version=1,
                    msg_type=payload.get("msg_type", "user"),
                    timestamp=payload.get("timestamp", ""),
                    content=payload.get("content"),
                    raw_data=payload,
                )
            )
        messages.sort(key=lambda msg: (msg.timestamp, msg.id))
        return messages

    def _load_annotated_session(self, session_id: str, raw: dict) -> dict:
        annotated = annotate_unified(self._normalize_messages(session_id, raw))
        return dedup_annotated_messages(annotated)

    def _p0_normalize(self, run_id: str, sessions: dict[str, dict]) -> None:
        self.store.update_stage(run_id, "p0_normalize", status="running")
        normalized = {
            session_id: {
                "session_id": session_id,
                "message_count": len(self._normalize_messages(session_id, raw)),
            }
            for session_id, raw in sessions.items()
        }
        self.store.update_stage(
            run_id,
            "p0_normalize",
            status="done",
            data={"sessions": normalized, "count": len(normalized)},
        )

    async def _p1_classify(self, run_id: str, sessions: dict[str, dict]) -> None:
        self.store.update_stage(run_id, "p1_classify", status="running")
        results = []

        MAX_BATCH = 20
        tasks = []
        for session_id, raw in sessions.items():
            annotated = self._load_annotated_session(session_id, raw)
            user_messages = extract_user_messages(annotated)
            if not user_messages:
                results.append({
                    "session_id": session_id,
                    "classifications": [],
                    "triggers": [],
                    "skeleton": get_session_skeleton([]),
                })
                continue

            for i in range(0, len(user_messages), MAX_BATCH):
                batch = user_messages[i : i + MAX_BATCH]
                prompt = build_classification_prompt(batch)
                tasks.append({
                    "session_id": session_id,
                    "user_messages": batch,
                    "prompt": prompt,
                })

        self.logger.info("[%s] p1_classify batches=%d sessions=%d", run_id, len(tasks), len(sessions))
        progress = ProgressLogger(len(tasks), "p1_classify", run_id, self.logger)

        async def _classify_one(task: dict) -> dict:
            try:
                response = await self.llm.call(
                    CLASSIFICATION_SYSTEM_PROMPT,
                    task["prompt"],
                    CLASSIFICATION_SCHEMA,
                )
                classified = parse_classifications(
                    response.get("classifications", []),
                    task["user_messages"],
                )
                progress.tick()
                return {
                    "session_id": task["session_id"],
                    "classified": classified,
                }
            except Exception as exc:
                progress.tick(error=True)
                self.logger.warning("[%s] p1_classify batch failed for %s: %s", run_id, task["session_id"], exc)
                raise

        batch_results = await asyncio.gather(*[_classify_one(t) for t in tasks], return_exceptions=True)

        if tasks and all(isinstance(br, Exception) for br in batch_results):
            first_err = batch_results[0]
            raise RuntimeError(f"All classification tasks failed: {first_err}") from first_err

        by_session: dict[str, list] = {}
        for br in batch_results:
            if isinstance(br, Exception):
                continue
            by_session[br["session_id"]] = br["classified"]

        total_triggers = 0
        for session_id, raw in sessions.items():
            classifications = by_session.get(session_id, [])
            triggers = get_rca_triggers(classifications)
            total_triggers += len(triggers)
            results.append({
                "session_id": session_id,
                "classifications": classifications,
                "triggers": triggers,
                "skeleton": get_session_skeleton(classifications),
            })

        self.logger.info("[%s] p1_classify done triggers=%d", run_id, total_triggers)
        self.store.update_stage(
            run_id,
            "p1_classify",
            status="done",
            data={"sessions": results, "trigger_count": total_triggers},
        )

    def _p2_context(self, run_id: str, sessions: dict[str, dict]) -> None:
        self.store.update_stage(run_id, "p2_context", status="running")
        classification_data = self.store.get_stage_output(run_id, "p1_classify") or {}
        context_items = []

        for session_result in classification_data.get("sessions", []):
            session_id = session_result["session_id"]
            raw = sessions[session_id]
            annotated = self._load_annotated_session(session_id, raw)
            for trigger in session_result.get("triggers", []):
                context = build_context_window(annotated, trigger["turn_index"])
                formatted_context = format_context_for_prompt(context)
                context_items.append(
                    {
                        "session_id": session_id,
                        "trigger": trigger,
                        "context": context,
                        "formatted_context": formatted_context,
                    }
                )

        self.store.update_stage(
            run_id,
            "p2_context",
            status="done",
            data={"windows": context_items, "window_count": len(context_items)},
        )

    async def _p3_rca(self, run_id: str) -> None:
        self.store.update_stage(run_id, "p3_rca", status="running")
        context_data = self.store.get_stage_output(run_id, "p2_context") or {}
        windows = context_data.get("windows", [])
        findings = []
        false_positive_count = 0

        if not windows:
            self.logger.info("[%s] p3_rca no windows to process", run_id)
            self.store.update_stage(run_id, "p3_rca", status="done", data={"findings": []})
            return

        tasks = []
        for item in windows:
            trigger = item["trigger"]
            prompt = RCA_USER_TEMPLATE.format(
                correction_turn=trigger["turn_index"],
                correction_text=trigger["text"],
                repo_name="unknown",
                start=item["context"][0]["original_turn"] if item["context"] else trigger["turn_index"],
                end=item["context"][-1]["original_turn"] if item["context"] else trigger["turn_index"],
                formatted_context=item["formatted_context"],
            )
            tasks.append({"item": item, "prompt": prompt})

        self.logger.info("[%s] p3_rca windows=%d", run_id, len(tasks))
        progress = ProgressLogger(len(tasks), "p3_rca", run_id, self.logger)

        async def _rca_one(task):
            try:
                result = await self.llm.call(RCA_SYSTEM_PROMPT, task["prompt"], RCA_SCHEMA)
                progress.tick()
                return {"item": task["item"], "result": result}
            except Exception as exc:
                progress.tick(error=True)
                self.logger.warning("[%s] p3_rca window failed: %s", run_id, exc)
                raise

        results = await asyncio.gather(*[_rca_one(t) for t in tasks], return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                continue
            result = r["result"]
            # DeepSeek json_object may return a list instead of dict
            if isinstance(result, list):
                if not result:
                    continue
                result = result[0] if isinstance(result[0], dict) else {}
            if not isinstance(result, dict):
                continue
            item = r["item"]
            if result.get("is_correction", True):
                findings.append({
                    **result,
                    "session_id": item["session_id"],
                    "trigger_label": item["trigger"].get("label", "unknown"),
                })
            else:
                false_positive_count += 1

        self.logger.info("[%s] p3_rca done findings=%d false_positives=%d", run_id, len(findings), false_positive_count)
        data = {"findings": findings}
        if findings or false_positive_count:
            data["false_positive_count"] = false_positive_count
        self.store.update_stage(run_id, "p3_rca", status="done", data=data)

    async def _p4_enrich(self, run_id: str) -> None:
        findings = list((self.store.get_stage_output(run_id, "p3_rca") or {}).get("findings", []))

        # Build semaphore from llm client if available
        semaphore = getattr(self.llm, "semaphore", asyncio.Semaphore(30))
        logger = logging.getLogger("blackbox.pipeline")

        await self._p4a_behavior(run_id, findings, semaphore, logger)
        await self._p4b_cluster(run_id, findings, semaphore, logger)
        await self._p4c_convention(run_id, findings, semaphore, logger)

    async def _p4a_behavior(self, run_id: str, findings: list[dict], semaphore, logger) -> None:
        self.store.update_stage(run_id, "p4a_behavior", status="running")
        findings = await phase4a_behavior_classify(
            findings, self.llm, semaphore, logger,
        )
        self.store.update_stage(
            run_id, "p4a_behavior", status="done",
            data={"findings": findings, "count": len(findings)},
        )

    async def _p4b_cluster(self, run_id: str, findings: list[dict], semaphore, logger) -> None:
        self.store.update_stage(run_id, "p4b_cluster", status="running")
        patterns, findings = await phase4b_recurrence_cluster(
            findings, self.llm, semaphore, logger,
        )
        one_off_indices = [
            i for i, f in enumerate(findings) if not f.get("is_recurring", False)
        ]
        self.store.update_stage(
            run_id, "p4b_cluster", status="done",
            data={"patterns": patterns, "one_off_indices": one_off_indices},
        )

    async def _p4c_convention(self, run_id: str, findings: list[dict], semaphore, logger) -> None:
        self.store.update_stage(run_id, "p4c_convention", status="running")
        conventions = await phase4c_convention_detect(
            findings, self.llm, semaphore, logger,
        )
        self.store.update_stage(
            run_id, "p4c_convention", status="done",
            data={"conventions": conventions, "count": len(conventions)},
        )

    def _p5_aggregate(self, run_id: str, sessions: dict[str, dict]) -> None:
        self.store.update_stage(run_id, "p5_aggregate", status="running")
        findings = list((self.store.get_stage_output(run_id, "p4a_behavior") or {}).get("findings", []))
        conventions = (self.store.get_stage_output(run_id, "p4c_convention") or {}).get(
            "conventions",
            [],
        )
        deduped = self._dedupe_findings(findings)
        recurring = [finding for finding in deduped if finding.get("is_recurring", False)]
        one_off = [finding for finding in deduped if not finding.get("is_recurring", False)]
        severity_counts = Counter(finding.get("severity", 0) for finding in deduped)
        category_counts = Counter(finding.get("category", "unknown") for finding in deduped)
        summary = {
            "total_sessions": len(sessions),
            "total_findings": len(deduped),
            "recurring_findings": len(recurring),
            "one_off_findings": len(one_off),
            "severity_distribution": dict(sorted(severity_counts.items())),
            "category_distribution": dict(category_counts),
            "convention_count": len(conventions),
            "findings": deduped,
            "filtered_findings": recurring,
        }
        self.store.update_stage(run_id, "p5_aggregate", status="done", data=summary)

    def _dedupe_findings(self, findings: list[dict]) -> list[dict]:
        by_session: dict[str, list[dict]] = defaultdict(list)
        for finding in findings:
            by_session[finding.get("session_id", "")].append(finding)

        kept: list[dict] = []
        for group in by_session.values():
            for finding in group:
                duplicate = False
                for existing in kept:
                    if existing.get("session_id") != finding.get("session_id"):
                        continue
                    ratio = SequenceMatcher(
                        None,
                        existing.get("agents_md_rule", ""),
                        finding.get("agents_md_rule", ""),
                    ).ratio()
                    if ratio > 0.6:
                        duplicate = True
                        break
                if not duplicate:
                    kept.append(finding)
        return kept

    def _p6_scope(self, run_id: str) -> None:
        self.store.update_stage(run_id, "p6_scope", status="running")
        findings = (self.store.get_stage_output(run_id, "p5_aggregate") or {}).get(
            "filtered_findings",
            [],
        )
        by_repo: dict[str, list[dict]] = defaultdict(list)
        by_dev_repo: dict[str, list[dict]] = defaultdict(list)

        for finding in findings:
            repo = finding.get("repo", "unknown")
            developer = finding.get("developer", "unknown")
            by_repo[repo].append(finding)
            by_dev_repo[f"{developer}::{repo}"].append(finding)

        self.store.update_stage(
            run_id,
            "p6_scope",
            status="done",
            data={"repos": dict(by_repo), "dev_repo": dict(by_dev_repo)},
        )


__all__ = ["MockLLMClient", "Pipeline"]
