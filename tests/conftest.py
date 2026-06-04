# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Test configuration for standalone package imports."""


import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
