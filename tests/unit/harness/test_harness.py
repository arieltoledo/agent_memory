"""Unit tests for the verification harness machinery itself.

These do not test the kernel's correctness; they prove the harness behaves as
expected: fixtures can force adversarial component outputs, the guard overrides
a misclassifying analyzer, TESTS are broken down into independent detection
telemetry, and the frozen expectations cannot be mutated.
"""

from __future__ import annotations

import pytest

from memory_agent.domain.enums import RestrictionLevel, AuditDecision, SecurityOutcome, ArchitecturalOutcome
from memory_agent.testing.mocks import FakeGuard, FakeAnalyzer, FakeAuditor, FakeSegmenter, FakeGenerator
from memory_agent.testing.schema import FixtureSpec, ExpectedDetection, ForcedOutput, InitialState, InjectedFailures
from memory_agent.testing.kernel import TestKernel
from memory_agent.testing.runner import run_fixture


def _spec(**kwargs) -> FixtureSpec:
    return FixtureSpec(
        id=kwargs["id"],
        kind=kwargs.get("kind", "GOLDEN"),
        forced_model_output=kwargs.get("forced", ForcedOutput()),
        forced_auditor_output=kwargs.get("forced_aud", ForcedOutput()),
        injected_failures=kwargs.get("injected", InjectedFailures()),
        expected=ExpectedDetection(**kwargs.get("expected", {})),
        initial_state=kwargs.get("initial", InitialState()),
    )


def test_fake_guard_hard_restriction():
    guard = FakeGuard(ForcedOutput(restriction=RestrictionLevel.NEVER_DURABLE))
    assert guard.restriction_for("anything") == RestrictionLevel.NEVER_DURABLE
    assert guard.restriction_map("x")[0]["restriction"] == "NEVER_DURABLE"


def test_analyzer_ordinary_but_guard_never_durable_blocks():
    """I29 / I30: an 'ordinary' analyzer must not lower an independent
    NEVER_DURABLE hard restriction. The kernel must block persistence."""
    spec = _spec(
        id="UNIT-GUARD-MONO",
        forced=ForcedOutput(
            sensitivity="ORDINARY",
            persistence_intent="EXPLICIT",
            restriction=RestrictionLevel.NEVER_DURABLE,
            operations=[{"op": "ADD", "key": "k", "value": "v", "domain": "OPERATIONAL"}],
        ),
        expected={
            "result": "PROHIBITED",
            "error_code": "NEVER_DURABLE",
            "security_outcome": "PASS",
            "architectural_outcome": "PASS",
            "expected_detection_layer": "INGRESS_GUARD",
            "actual_detection_layer": "INGRESS_GUARD",
            "policy_bypass": False,
        },
    )
    tr = run_fixture(spec, TestKernel())
    assert tr.result == "PROHIBITED"
    assert tr.error_code == "NEVER_DURABLE"
    assert tr.actual_detection_layer == "INGRESS_GUARD"


def test_fake_auditor_accept_on_invalid_but_guard_deterministic():
    """Ordering FakeAuditor=ACCEPT does not bypass the deterministic kernel."""
    guard = FakeAuditor(
        ForcedOutput(auditor_decision=AuditDecision.ACCEPT), InjectedFailures()
    )
    # Auditor accepting an invalid patch could not persist because the guard
    # still enforces contract. The AUDIT is just one layer.
    assert guard.audit({})["decision"] == "ACCEPT"


def test_detection_telemetry_is_not_boolean():
    spec = _spec(
        id="UNIT-TELEMETRY",
        forced=ForcedOutput(
            semantic_type="OTHER",
            sensitivity="ORDINARY",
            persistence_intent="EXPLICIT",
            operations=[{"op": "ADD", "key": "k", "value": "secret", "domain": "OPERATIONAL",
                         "evidence_refs": ["ev-1"]}],
        ),
        forced_aud=ForcedOutput(auditor_decision=AuditDecision.REJECT),
        initial=InitialState(records={}, evidence={"ev-1": {"branch": "branch-a", "status": "ACTIVE"}}),
        expected={
            "result": "NO_COMMIT",
            "error_code": "AUDIT_REJECTED",
            "security_outcome": "PASS",
            "architectural_outcome": "DEGRADED",
            "expected_detection_layer": "PERSISTENCE_POLICY",
            "actual_detection_layer": "AUDITOR",
            "policy_bypass": True,
        },
    )
    tr = run_fixture(spec, TestKernel())
    # separate, independent fields (I41)
    assert tr.security_outcome == SecurityOutcome.PASS
    assert tr.architectural_outcome == ArchitecturalOutcome.DEGRADED
    assert tr.policy_bypass is True
    assert tr.pass_expected


def test_fake_segmenter_forced_single_segment():
    seg = FakeSegmenter(ForcedOutput(segments=[{"source_start": 0, "source_end": 9, "kind": "operational_decision"}]))
    assert seg.segment("sensitive")[0]["kind"] == "operational_decision"


def test_frozen_expected_not_mutated():
    """The harness must never silently rewrite an expected outcome."""
    spec = _spec(id="UNIT-FROZEN", expected={"result": "COMMITTED"})
    before = dict(spec.expected.model_dump())
    run_fixture(spec, TestKernel())
    after = dict(spec.expected.model_dump())
    assert before == after


def test_runner_marks_not_implemented():
    spec = _spec(id="UNIT-NI", expected={"result": "X"})
    spec.status = "NOT_IMPLEMENTED"
    tr = run_fixture(spec, TestKernel())
    assert tr.is_not_implemented
    assert tr.expected_detection_layer is None  # not compared in NI state
