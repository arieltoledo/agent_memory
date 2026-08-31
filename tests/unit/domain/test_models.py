from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from memory_agent.domain.enums import Lifetime, MemoryDomain, RecordStatus, SemanticType, Sensitivity, ValueStorageClass
from memory_agent.domain.models import MemoryRecord, RestrictionSpan, ValueReference


def now(): return datetime.now(timezone.utc)


def record(**overrides):
    values = dict(record_id=uuid4(), domain=MemoryDomain.PERSONAL, branch_id=None, semantic_key="preference", kind=SemanticType.PREFERENCE, status=RecordStatus.ACTIVE, sensitivity=Sensitivity.PERSONAL, storage_class=ValueStorageClass.VAULT_REF, inline_value=None, payload_ref=uuid4(), lifetime=Lifetime.DURABLE, valid_until=None, timezone=None, policy_snapshot_id=uuid4(), mount_policy_id=None, created_commit_id=uuid4(), supersedes_record_id=None, created_at=now(), purged_at=None)
    values.update(overrides)
    return MemoryRecord(**values)


def test_personal_memory_is_never_inline():
    with pytest.raises(ValidationError): record(storage_class=ValueStorageClass.INLINE_NON_SENSITIVE, inline_value="x", payload_ref=None)


def test_prohibited_memory_is_not_durable():
    with pytest.raises(ValidationError): record(sensitivity=Sensitivity.PROHIBITED)


def test_purged_tombstone_keeps_opaque_payload_reference():
    assert record(status=RecordStatus.PURGED, purged_at=now()).payload_ref is not None


def test_vault_reference_needs_payload_and_digest():
    with pytest.raises(ValidationError): ValueReference(storage_class=ValueStorageClass.VAULT_REF, payload_ref=uuid4())


def test_inline_reference_cannot_have_payload():
    with pytest.raises(ValidationError): ValueReference(storage_class=ValueStorageClass.INLINE_NON_SENSITIVE, inline_value="x", payload_ref=uuid4())


def test_restriction_span_is_nonempty():
    from memory_agent.domain.enums import RestrictionLevel
    with pytest.raises(ValidationError): RestrictionSpan(span_id=uuid4(), input_id=uuid4(), start=3, end=3, category="credential", restriction=RestrictionLevel.NEVER_DURABLE, detector_id="test")


def test_persistent_datetimes_must_be_aware():
    with pytest.raises(ValidationError): record(created_at=datetime.now())
