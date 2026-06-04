# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Tests for CLI app entry point."""


def test_app_module_imports():
    from src.cli.app import BlackboxApp
    assert BlackboxApp is not None
