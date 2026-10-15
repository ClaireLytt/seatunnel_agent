# -*- coding: utf-8 -*-
"""Doctor agent — read-only environment diagnosis with a deterministic
no-key fallback. Prescribes fixes; never executes them."""

from .engine import DoctorResult, build_tools, diagnose

__all__ = ["DoctorResult", "build_tools", "diagnose"]
