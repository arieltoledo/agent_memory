"""Memory Agent — Deterministic Verification & Test Harness.

Owned by Coder 3 (Verification & Test Harness Owner).

This package contains everything needed to prove, deterministically and
falsifiably, where the Memory Agent kernel behaves correctly and where it
goes wrong — WITHOUT a real LLM.

Probabilistic components (Memory Analyzer, Segmenter, Generator, Auditor)
are replaced by fixtures-controlled fakes (see mocks.py). The deterministic
kernel rules are implemented as a small reference driver (see kernel.py);
OLA 2 swaps in the real kernel components behind the same driver interface.
"""

from .schema import FixtureBundle, FixtureSpec, ExpectedDetection, UnfrozenError
from .loader import load_fixture, load_bundle, discover_fixtures
from .mocks import (
    FakeGuard,
    FakeAnalyzer,
    FakeSegmenter,
    FakeGenerator,
    FakeAuditor,
)
from .kernel import TestKernel, KernelResult
from .runner import run_fixture, TestResult
from .assertions import assert_test_result
from .report import build_report, Report

__all__ = [
    "FixtureBundle",
    "FixtureSpec",
    "ExpectedDetection",
    "UnfrozenError",
    "load_fixture",
    "load_bundle",
    "discover_fixtures",
    "FakeGuard",
    "FakeAnalyzer",
    "FakeSegmenter",
    "FakeGenerator",
    "FakeAuditor",
    "TestKernel",
    "KernelResult",
    "run_fixture",
    "TestResult",
    "assert_test_result",
    "build_report",
    "Report",
]
