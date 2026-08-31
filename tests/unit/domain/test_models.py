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


def test_operational_sensitive_memory_is_never_inline():
    # SENSITIVE + INLINE in OPERATIONAL domain must be REJECTED
    with pytest.raises(ValidationError):
        record(
            domain=MemoryDomain.OPERATIONAL,
            branch_id=uuid4(),
            sensitivity=Sensitivity.SENSITIVE,
            storage_class=ValueStorageClass.INLINE_NON_SENSITIVE,
            inline_value="sensitive_data",
            payload_ref=None,
        )


def test_operational_sensitive_vault_accepted():
    # positive control: SENSITIVE + VAULT_REF in OPERATIONAL domain must be ACCEPTED
    rec = record(
        domain=MemoryDomain.OPERATIONAL,
        branch_id=uuid4(),
        sensitivity=Sensitivity.SENSITIVE,
        storage_class=ValueStorageClass.VAULT_REF,
        inline_value=None,
        payload_ref=uuid4(),
    )
    assert rec.sensitivity == Sensitivity.SENSITIVE
    assert rec.storage_class == ValueStorageClass.VAULT_REF


def test_prohibited_payload_object_rejected():
    from memory_agent.domain.models import PayloadObject
    from memory_agent.domain.enums import PayloadStatus
    # PROHIBITED PayloadObject must be REJECTED
    with pytest.raises(ValidationError):
        PayloadObject(
            payload_id=uuid4(),
            purpose="MEMORY_VALUE",
            status=PayloadStatus.ACTIVE,
            sensitivity=Sensitivity.PROHIBITED,
            key_handle="k1",
            ciphertext_location="loc1",
            created_at=now(),
            activated_at=now(),
            destroyed_at=None,
        )


def test_sensitive_payload_object_accepted():
    from memory_agent.domain.models import PayloadObject
    from memory_agent.domain.enums import PayloadStatus
    # Positive control: SENSITIVE PayloadObject is ACCEPTED
    p = PayloadObject(
        payload_id=uuid4(),
        purpose="MEMORY_VALUE",
        status=PayloadStatus.ACTIVE,
        sensitivity=Sensitivity.SENSITIVE,
        key_handle="k1",
        ciphertext_location="loc1",
        created_at=now(),
        activated_at=now(),
        destroyed_at=None,
    )
    assert p.sensitivity == Sensitivity.SENSITIVE


def test_payload_object_lifecycle_four_partial_cases():
    from memory_agent.domain.models import PayloadObject
    from memory_agent.domain.enums import PayloadStatus

    # Case 1: STAGED with key_handle != None, ciphertext_location == None -> REJECT
    with pytest.raises(ValidationError):
        PayloadObject(
            payload_id=uuid4(),
            purpose="MEMORY_VALUE",
            status=PayloadStatus.STAGED,
            sensitivity=Sensitivity.ORDINARY,
            key_handle="k1",
            ciphertext_location=None,
            created_at=now(),
            activated_at=None,
            destroyed_at=None,
        )

    # Case 2: STAGED with key_handle == None, ciphertext_location != None -> REJECT
    with pytest.raises(ValidationError):
        PayloadObject(
            payload_id=uuid4(),
            purpose="MEMORY_VALUE",
            status=PayloadStatus.STAGED,
            sensitivity=Sensitivity.ORDINARY,
            key_handle=None,
            ciphertext_location="loc1",
            created_at=now(),
            activated_at=None,
            destroyed_at=None,
        )

    # Case 3: DESTROYED with key_handle != None, ciphertext_location == None -> REJECT
    with pytest.raises(ValidationError):
        PayloadObject(
            payload_id=uuid4(),
            purpose="MEMORY_VALUE",
            status=PayloadStatus.DESTROYED,
            sensitivity=Sensitivity.ORDINARY,
            key_handle="k1",
            ciphertext_location=None,
            created_at=now(),
            activated_at=now(),
            destroyed_at=now(),
        )

    # Case 4: DESTROYED with key_handle == None, ciphertext_location != None -> REJECT
    with pytest.raises(ValidationError):
        PayloadObject(
            payload_id=uuid4(),
            purpose="MEMORY_VALUE",
            status=PayloadStatus.DESTROYED,
            sensitivity=Sensitivity.ORDINARY,
            key_handle=None,
            ciphertext_location="loc1",
            created_at=now(),
            activated_at=now(),
            destroyed_at=now(),
        )

