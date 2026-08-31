"""Fakes for the probabilistic / untrusted components.

These let the harness order any output we want and check that the
deterministic kernel still enforces its invariants. Example that this class
of fixture exists to expose:

    Analyzer deliberately says `ordinary` / `explicit persistence`
    but the Ingress Guard says `NEVER_DURABLE`
        -> the kernel must still block persistence (I29 / I30).

Each fake is fully driven by a `ForcedOutput` from the fixture, so results are
reproducible and never depend on a model call.
"""

from __future__ import annotations

from typing import Any

from ..domain.enums import RestrictionLevel

from .schema import ForcedOutput


class FakeGuard:
    """Independent deterministic Ingress Content Guard (hard restriction)."""

    def __init__(self, forced: ForcedOutput):
        self._restriction = forced.restriction or RestrictionLevel.NONE
        self._category = "credential"

    def restriction_for(self, text: str) -> RestrictionLevel:
        return self._restriction

    def restriction_map(self, text: str) -> list[dict[str, Any]]:
        if self._restriction == RestrictionLevel.NONE:
            return []
        return [
            {
                "span": [0, len(text)],
                "category": self._category,
                "restriction": self._restriction.value,
                "detector_id": "fixture-guard",
            }
        ]


class FakeAnalyzer:
    """Replaces Memory Analyzer (probabilistic classification)."""

    def __init__(self, forced: ForcedOutput):
        self._forced = forced

    def analyze(self, text: str) -> dict[str, Any]:
        return {
            "semantic_type": self._forced.semantic_type or "OTHER",
            "sensitivity": self._forced.sensitivity or "ORDINARY",
            "persistence_intent": self._forced.persistence_intent or "NONE",
            "temporal_scope": self._forced.temporal_scope or "DURABLE",
            "domain_hint": self._forced.domain_hint or "OPERATIONAL",
        }


class FakeSegmenter:
    """Replaces Atomic Segmenter. A fixture may force segmentation failure
    (a single operational_decision wrapping a secret) to test span
    propagation."""

    def __init__(self, forced: ForcedOutput):
        self._forced = forced

    def segment(self, text: str) -> list[dict[str, Any]]:
        if self._forced.segments is not None:
            return [dict(s) for s in self._forced.segments]
        return [{"source_start": 0, "source_end": len(text), "kind": "candidate"}]


class FakeGenerator:
    """Replaces the Generator (untrusted proposer). Emits a DraftPatch's
    operations under the fixture's control."""

    def __init__(self, forced: ForcedOutput):
        self._forced = forced

    def propose(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        if self._forced.operations is not None:
            return [dict(op) for op in self._forced.operations]
        return []

    def output_text(self) -> str | None:
        return self._forced.output_text


class FakeAuditor:
    """Replaces the Auditor (untrusted semantic judge).

    We can order FakeAuditor = ACCEPT even when the proposal is invalid; the
    deterministic kernel must still reject when warranted. This is the whole
    point: the Auditor is not the last line of defense."""

    def __init__(self, forced_auditor: ForcedOutput, injected: Any):
        self._forced = forced_auditor
        self._injected = injected

    def audit(self, patch: dict[str, Any]) -> dict[str, Any]:
        if self._injected.auditor_unavailable:
            raise RuntimeError("Auditor unavailable (fixture-injected failure)")
        return {
            "decision": (
                self._forced.auditor_decision.value
                if self._forced.auditor_decision
                else "ACCEPT"
            ),
            "reason_codes": ["fixture-forced"],
        }
