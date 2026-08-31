"""Detection Layer assertions.

A test is never a bare boolean. We assert `security_outcome` and
`architectural_outcome` separately, and we compare `expected_detection_layer`
vs `actual_detection_layer` to decide whether a prevention was on time or late.

Example:
    unsafe commit = prevented
        PANEL is fine, but the when matters:
        security_outcome = PASS (stopped)
        architectural_outcome = DEGRADED (stopped too late / at wrong layer)
"""

from __future__ import annotations

from .runner import TestResult


class AssertionError_(AssertionError):
    pass


def assert_security_outcome(tr: TestResult, expected: str) -> None:
    actual = tr.security_outcome.value if tr.security_outcome else None
    if actual != expected:
        raise AssertionError_(
            f"[{tr.test_id}] security_outcome: expected {expected!r}, got {actual!r}"
        )


def assert_architectural_outcome(tr: TestResult, expected: str) -> None:
    actual = tr.architectural_outcome.value if tr.architectural_outcome else None
    if actual != expected:
        raise AssertionError_(
            f"[{tr.test_id}] architectural_outcome: expected {expected!r}, got {actual!r}"
        )


def assert_detection_layer(tr: TestResult, *, expected: str, actual: str) -> None:
    if tr.expected_detection_layer != expected:
        raise AssertionError_(
            f"[{tr.test_id}] expected_detection_layer: expected {expected!r}, "
            f"got {tr.expected_detection_layer!r}"
        )
    if tr.actual_detection_layer != actual:
        raise AssertionError_(
            f"[{tr.test_id}] actual_detection_layer: expected {actual!r}, "
            f"got {tr.actual_detection_layer!r}"
        )


def assert_policy_bypass(tr: TestResult, expected: bool) -> None:
    if tr.policy_bypass != expected:
        raise AssertionError_(
            f"[{tr.test_id}] policy_bypass: expected {expected!r}, got {tr.policy_bypass!r}"
        )


def assert_error_code(tr: TestResult, expected: str) -> None:
    if tr.error_code != expected:
        raise AssertionError_(
            f"[{tr.test_id}] error_code: expected {expected!r}, got {tr.error_code!r}"
        )


def assert_test_result(tr: TestResult) -> None:
    """Assert a full test result against its frozen expected block."""
    e = tr.expected
    if e.get("security_outcome") is not None:
        assert_security_outcome(tr, e["security_outcome"])
    if e.get("architectural_outcome") is not None:
        assert_architectural_outcome(tr, e["architectural_outcome"])
    if e.get("error_code") is not None:
        assert_error_code(tr, e["error_code"])
    if e.get("expected_detection_layer") is not None:
        if e.get("actual_detection_layer") is not None:
            assert_detection_layer(
                tr,
                expected=e["expected_detection_layer"],
                actual=e["actual_detection_layer"],
            )
    if e.get("policy_bypass") is not None:
        assert_policy_bypass(tr, e["policy_bypass"])
