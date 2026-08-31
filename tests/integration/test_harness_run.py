"""Integration: run every fixture through the deterministic harness and assert
against the frozen `expected` block.

These are the executable, falsifiable contracts. A fixture that a real kernel
does not satisfy must show as FAIL here — that is exactly the evidence this
harness is meant to produce.
"""

from __future__ import annotations

import pytest

from memory_agent.testing.fixtures import golden_fixtures, adversarial_fixtures
from memory_agent.testing.kernel import TestKernel
from memory_agent.testing.runner import run_fixture
from memory_agent.testing.assertions import assert_test_result

_KERNEL = TestKernel()


def _collect(bundle):
    return list(bundle.fixtures.values())


GOLDEN = _collect(golden_fixtures())
ADVERSARIAL = _collect(adversarial_fixtures())


@pytest.mark.parametrize("spec", GOLDEN, ids=lambda s: s.id)
def test_golden_fixture(spec):
    tr = run_fixture(spec, _KERNEL)
    if spec.status == "NOT_IMPLEMENTED":
        pytest.skip(f"{spec.id} marked NOT_IMPLEMENTED (expected frozen)")
    if spec.status == "TEST_SPEC_CONFLICT":
        pytest.skip(f"{spec.id} marked TEST_SPEC_CONFLICT (frozen for review)")
    assert_test_result(tr)


@pytest.mark.parametrize("spec", ADVERSARIAL, ids=lambda s: s.id)
def test_adversarial_fixture(spec):
    tr = run_fixture(spec, _KERNEL)
    if spec.status == "NOT_IMPLEMENTED":
        pytest.skip(f"{spec.id} marked NOT_IMPLEMENTED (expected frozen)")
    if spec.status == "TEST_SPEC_CONFLICT":
        pytest.skip(f"{spec.id} marked TEST_SPEC_CONFLICT (frozen for review)")
    assert_test_result(tr)


def test_fixture_count():
    assert len(GOLDEN) == 17, "golden T16-T26 + T39-T42/T46/T48 = 17 fixtures"
    assert len(ADVERSARIAL) == 16, "RT-E(4)+RT-F(5)+RT-G(3)+RT-H(3)+RT-I06 = 16 fixtures"
