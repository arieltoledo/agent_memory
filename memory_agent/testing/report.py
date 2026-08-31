"""Report generation for the verification harness.

Produces the deliverable evidence report:

    Fixtures created:
    Tests executable:
    PASS:
    FAIL:
    NOT_IMPLEMENTED:
    TEST_SPEC_CONFLICT:
    Design observations:

plus a per-test table:

    test_id | expected_detection_layer | current_component | status
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .runner import TestResult
from .kernel import TestKernel
from .schema import FixtureSpec


@dataclass
class Report:
    fixtures_created: int = 0
    tests_executable: int = 0
    pass_count: int = 0
    fail_count: int = 0
    not_implemented_count: int = 0
    conflict_count: int = 0
    design_observations: list[str] = field(default_factory=list)
    table_rows: list[dict] = field(default_factory=list)

    def render(self) -> str:
        lines: list[str] = []
        lines.append("=== Verification Harness Report (Coder 3) ===")
        lines.append(f"Fixtures created: {self.fixtures_created}")
        lines.append(f"Tests executable: {self.tests_executable}")
        # C3-04: until OLA 2 substitutes real components, reference-kernel
        # results are HARNESS_VALIDATED, NOT a definitive Golden/Adversarial
        # PASS. Expected outcomes are never modified.
        lines.append(f"HARNESS_VALIDATED (reference kernel): {self.pass_count}")
        lines.append(f"FAIL: {self.fail_count}")
        lines.append(f"NOT_IMPLEMENTED: {self.not_implemented_count}")
        lines.append(f"TEST_SPEC_CONFLICT: {self.conflict_count}")
        lines.append("")
        lines.append(
            "Note: PASS above is HARNESS_VALIDATED only (reference kernel). "
            "It proves fixture/harness internal consistency, NOT a definitive "
            "Golden/Adversarial PASS of the production kernel (OLA 2)."
        )
        lines.append("")
        lines.append("Design observations:")
        for obs in self.design_observations:
            lines.append(f"  - {obs}")
        lines.append("")
        lines.append("| test_id | expected_detection_layer | current_component | status |")
        lines.append("|---|---|---|---|")
        for row in self.table_rows:
            lines.append(
                f"| {row['test_id']} | {row['expected_detection_layer']} | "
                f"{row['current_component']} | {row['status']} |"
            )
        return "\n".join(lines)


def build_report(fixtures: Iterable[FixtureSpec], kernel: TestKernel | None = None) -> tuple[Report, list[TestResult]]:
    kernel = kernel or TestKernel()
    report = Report()
    results: list[TestResult] = []
    from .runner import run_fixture

    for spec in fixtures:
        tr = run_fixture(spec, kernel)
        results.append(tr)
        report.fixtures_created += 1
        report.tests_executable += 1

        status = tr.status
        if status == "NOT_IMPLEMENTED":
            report.not_implemented_count += 1
        elif status == "TEST_SPEC_CONFLICT":
            report.conflict_count += 1
        elif tr.pass_expected:
            report.pass_count += 1
        else:
            report.fail_count += 1

        report.table_rows.append(
            {
                "test_id": tr.test_id,
                "expected_detection_layer": tr.expected_detection_layer or "-",
                "current_component": tr.actual_detection_layer or "-",
                "status": ("PARTIAL" if status == "NOT_IMPLEMENTED" else status),
            }
        )
    return report, results
