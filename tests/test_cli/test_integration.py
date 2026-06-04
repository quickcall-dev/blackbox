# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Integration tests for CLI to API flow."""

import pytest
from src.cli.client import BlackboxClient


@pytest.mark.asyncio
async def test_client_health_check_unreachable():
    client = BlackboxClient(base_url="http://127.0.0.1:19999")
    ok = await client.health()
    assert ok is False
