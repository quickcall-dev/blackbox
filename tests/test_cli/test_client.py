# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for Blackbox API client."""

import pytest
from src.cli.client import BlackboxClient


def test_client_creates_with_default_url():
    # Pass explicit base_url to avoid env var interference
    client = BlackboxClient(base_url="http://localhost:8000")
    assert client.base_url == "http://localhost:8000"


def test_client_creates_with_custom_url():
    client = BlackboxClient(base_url="http://api.example.com:9000")
    assert client.base_url == "http://api.example.com:9000"


def test_client_builds_analyze_url():
    client = BlackboxClient(base_url="http://localhost:8000")
    url = client._url("/analyze")
    assert url == "http://localhost:8000/analyze"


def test_client_builds_run_url():
    client = BlackboxClient(base_url="http://x:1")
    url = client._url("/runs/abc123")
    assert url == "http://x:1/runs/abc123"
