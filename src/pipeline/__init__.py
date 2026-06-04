# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Pipeline package — orchestrator, annotator, context builder, dedup."""

from src.pipeline.orchestrator import MockLLMClient, Pipeline
from src.pipeline.annotator import annotate_unified
from src.pipeline.context_builder import (
    build_context_window,
    context_stats,
    extract_user_messages,
    format_context_for_prompt,
)
from src.pipeline.dedup import dedup_annotated_messages

# Re-export shared schemas for convenience
from src.classify.prompts import CLASSIFICATION_SCHEMA, CLASSIFICATION_SYSTEM_PROMPT
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

__all__ = [
    "MockLLMClient",
    "Pipeline",
    "annotate_unified",
    "build_context_window",
    "context_stats",
    "dedup_annotated_messages",
    "extract_user_messages",
    "format_context_for_prompt",
    "CLASSIFICATION_SCHEMA",
    "CLASSIFICATION_SYSTEM_PROMPT",
    "BEHAVIOR_SCHEMA",
    "BEHAVIOR_SYSTEM_PROMPT",
    "CLUSTER_SCHEMA",
    "CLUSTER_SYSTEM_PROMPT",
    "CONVENTION_SCHEMA",
    "CONVENTION_SYSTEM_PROMPT",
    "RCA_SCHEMA",
    "RCA_SYSTEM_PROMPT",
    "RCA_USER_TEMPLATE",
]
