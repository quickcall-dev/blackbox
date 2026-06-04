# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Structured logging helpers for the Blackbox pipeline."""

import logging
import time
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the blackbox namespace."""
    return logging.getLogger(f"blackbox.{name}")


class PhaseTimer:
    """Context manager that logs phase start/end with duration."""

    def __init__(self, phase: str, run_id: str, logger: logging.Logger | None = None):
        self.phase = phase
        self.run_id = run_id
        self.logger = logger or get_logger("pipeline")
        self._t0: float = 0.0

    def __enter__(self) -> "PhaseTimer":
        self._t0 = time.time()
        self.logger.info("[%s] phase=%s status=started", self.run_id, self.phase)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed = time.time() - self._t0
        if exc_val:
            self.logger.error(
                "[%s] phase=%s status=error duration=%.1fs error=%s",
                self.run_id, self.phase, elapsed, exc_val,
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.info(
                "[%s] phase=%s status=done duration=%.1fs",
                self.run_id, self.phase, elapsed,
            )


class ProgressLogger:
    """Log progress every N items with ETA."""

    def __init__(
        self,
        total: int,
        phase: str,
        run_id: str,
        logger: logging.Logger | None = None,
        every_n: int | None = None,
    ):
        self.total = total
        self.phase = phase
        self.run_id = run_id
        self.logger = logger or get_logger("pipeline")
        self.every_n = every_n or max(1, total // 10)
        self.done = 0
        self.errors = 0
        self._t0 = time.time()

    def tick(self, error: bool = False) -> None:
        self.done += 1
        if error:
            self.errors += 1
        if self.done == self.total or self.done % self.every_n == 0:
            elapsed = time.time() - self._t0
            rate = self.done / elapsed if elapsed > 0 else 0
            eta = (self.total - self.done) / rate if rate > 0 else 0
            err_str = f" errors={self.errors}" if self.errors else ""
            self.logger.info(
                "[%s] phase=%s progress=%d/%d (%d%%) elapsed=%.1fs eta=%.1fs%s",
                self.run_id,
                self.phase,
                self.done,
                self.total,
                self.done * 100 // self.total,
                elapsed,
                eta,
                err_str,
            )
