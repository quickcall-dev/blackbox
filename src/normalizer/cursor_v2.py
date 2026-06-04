# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Cursor vscdb-related types."""


from typing import TypedDict


class CursorTimingInfo(TypedDict, total=False):
    clientStartTime: int
    clientRpcSendTime: int
    clientSettleTime: int
    clientEndTime: int


class CursorModelConfig(TypedDict, total=False):
    modelName: str
    maxMode: bool


class CursorBubbleTokenCount(TypedDict, total=False):
    inputTokens: int
    outputTokens: int


class CursorVscdbBubble(TypedDict, total=False):
    type: int
    bubbleId: str
    text: str
    timingInfo: CursorTimingInfo
    tokenCountUpUntilHere: int
    isCapabilityIteration: bool
    capabilityType: str
    allThinkingBlocks: list[dict]


class CursorBubbleIdEntry(TypedDict, total=False):
    _v: int
    type: int
    tokenCount: CursorBubbleTokenCount
    createdAt: int


class CursorAgentKvToolResult(TypedDict, total=False):
    role: str
    id: str
    content: list[dict]
