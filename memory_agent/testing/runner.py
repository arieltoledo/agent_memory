"""Runner: executes a fixture and produces a structured TestResult.

A TestResult carries the kernel result plus independent telemetry
(security_outcome, architectural_outcome, expected/actual detection layer,
policy_bypass) so a consumer (e.g. `assertions.py`, the report generator) can
assert on each separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import ArchitecturalOutcome, SecurityOutcome
from .schema import FixtureSpec, FixtureBundle
from .kernel import TestKernel, KernelResult


@dataclass
class TestResult:
    test_id: str
    kind: str
    status: str  # ACTIVE | NOT_IMPLEMENTED | TEST_SPEC_CONFLICT
    result: str
    error_code: str | None
    expected: dict  # frozen expected block (never mutated)
    state: dict
    security_outcome: SecurityOutcome
    architectural_outcome: ArchitecturalOutcome
    expected_detection_layer: str | None
    actual_detection_layer: str | None
    policy_bypass: bool
    log: list[str] = field(default_factory=list)

    @property
    def pass_expected(self) -> bool:
        """True if this run satisfies the frozen `expected` block."""
        return _matches_expectations(self)

    @property
    def is_conflict(self) -> bool:
        return self.status == "TEST_SPEC_CONFLICT"

    @property
    def is_not_implemented(self) -> bool:
        return self.status == "NOT_IMPLEMENTED"


def _matches_expectations(tr: TestResult) -> bool:
    e = tr.expected
    checks = []

    def eq(actual, expected):
        if expected is None:
            return True
        return actual == expected

    checks.append(eq(tr.error_code, e.get("error_code")))
    checks.append(eq(tr.result, e.get("result")))
    checks.append(
        eq(tr.security_outcome.value if tr.security_outcome else None,
           e.get("security_outcome"))
    )
    checks.append(
        eq(tr.architectural_outcome.value if tr.architectural_outcome else None,
           e.get("architectural_outcome"))
    )
    checks.append(
        eq(tr.expected_detection_layer, e.get("expected_detection_layer"))
    )
    checks.append(
        eq(tr.actual_detection_layer, e.get("actual_detection_layer"))
    )
    checks.append(eq(tr.policy_bypass, e.get("policy_bypass")))
    return all(checks)


def run_fixture(spec: FixtureSpec, kernel: TestKernel | None = None) -> TestResult:
    kernel = kernel or TestKernel()
    kr: KernelResult = kernel.run(spec)
    exp = spec.expected.model_dump()

    return TestResult(
        test_id=spec.id,
        kind=spec.kind,
        status=spec.status,
        result=kr.result,
        error_code=kr.error_code,
        expected=exp,
        state=kr.state,
        security_outcome=kr.security_outcome,
        architectural_outcome=kr.architectural_outcome,
        expected_detection_layer=(
            exp.get("expected_detection_layer")
            if spec.status == "ACTIVE"
            else None
        ),
        actual_detection_layer=(
            (kr.actual_detection_layer.value
             if hasattr(kr.actual_detection_layer, "value")
             else kr.actual_detection_layer)
            if kr.actual_detection_layer
            else None
        ),
        policy_bypass=kr.policy_bypass,
        log=kr.log,
    )
