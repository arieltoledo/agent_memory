# Memory Agent — Data Model & Schemas v1.1

**Estado:** DRAFT FOR IMPLEMENTATION REVIEW
**Supersede:** Data Model & Schemas v1.0 Draft
**Design Review:** incorpora DR-01 a DR-05  
**Specification normativa:** Memory Agent Specification v0.3.0 — FROZEN  
**Technical Design:** v1.0 — DRAFT  
**Propósito:** fijar el contrato de datos previo a la implementación del MVP.

---

# 1. Alcance

Este documento define:

1. tipos y enumeraciones del dominio;
2. modelos Pydantic esperados;
3. separación entre datos efímeros, datos persistentes y payloads cifrados;
4. esquema SQLite;
5. invariantes de almacenamiento;
6. máquinas de estado;
7. límites transaccionales;
8. reglas de canonicalización y binding;
9. protocolo de PURGE;
10. trazabilidad entre los 49 Golden Tests + 41 Adversarial Tests y los componentes responsables.

Este documento **no implementa lógica de negocio**.

Su función es permitir que dos implementaciones independientes construyan las mismas estructuras y respeten las mismas fronteras.

---

# 2. Reglas de autoridad

Orden de precedencia:

```text
Specification v0.3.0
        ↓
Data Model & Schemas v1.0
        ↓
Technical Design v1.0
        ↓
Implementation
```

Si este documento contradice una garantía de la Specification v0.3.0:

> prevalece la Specification.

Una necesidad de modificar una garantía normativa no se resuelve cambiando silenciosamente el schema.

Debe abrir una nueva versión de Specification.

---

# 3. Decisión de almacenamiento más importante

Para simplificar PURGE y evitar residuos históricos:

> **Todo payload de Personal Memory será Vault-backed, aun cuando su sensibilidad sea `ordinary`.**

Por tanto:

```text
Personal Memory
    → NEVER plaintext in SQLite
    → value stored in encrypted Payload Vault
```

Para Operational Memory:

```text
non-sensitive operational value
    → MAY be inline in SQLite

sensitive/protected value
    → MUST be Vault-backed

prohibited value
    → MUST NOT be persisted anywhere
```

### Regla de dominio para PURGE en el MVP

```text
PURGE_REQUEST
    → permitido únicamente para domain = PERSONAL
```

La clase de almacenamiento `VAULT_REF` no otorga por sí sola semántica de PURGE a un dato operacional.

Operational Memory preserva historia y utiliza:

```text
RETRACT
SUPERSEDE
```

Si en el futuro una obligación jurídica exige borrado físico de información operacional, eso requerirá una extensión normativa explícita y no se resolverá silenciosamente desde el schema.

Esta regla evita que una futura solicitud de PURGE obligue a reescribir commits históricos que contienen plaintext operacional.

---

# 4. Capas físicas

```text
┌──────────────────────────────────────────────┐
│                 EPHEMERAL RAM                │
│ Raw input / Session / model working objects  │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│                 SQLITE                       │
│ Metadata, state, refs, transactions, audit   │
│ NO sensitive plaintext                       │
└──────────────────────────────────────────────┘
                        │ payload_ref
                        ▼
┌──────────────────────────────────────────────┐
│          ENCRYPTED PERSONAL PAYLOAD VAULT    │
│ Ciphertext only                              │
└──────────────────────────────────────────────┘
                        │ key_handle
                        ▼
┌──────────────────────────────────────────────┐
│             EXTERNAL KEY PROVIDER            │
│ Decryption / verification capability         │
└──────────────────────────────────────────────┘
```

---

# 5. Base model policy

Todos los objetos Pydantic persistibles o intercambiados entre componentes críticos deben usar:

```python
model_config = ConfigDict(
    strict=True,
    extra="forbid"
)
```

Reglas:

- campos desconocidos → error;
- coerciones implícitas peligrosas → error;
- enums → valores cerrados;
- IDs → tipos explícitos;
- datetimes → timezone-aware;
- JSON persistible → serialización canónica.

---

# 6. Identificadores

El MVP utilizará identificadores opacos aleatorios.

Tipo conceptual:

```python
OpaqueId = UUID
```

Ejemplos:

```text
branch_id
contract_id
record_id
payload_id
evidence_id
candidate_id
patch_id
operation_id
audit_id
commit_id
conflict_id
lease_id
purge_id
policy_snapshot_id
run_id
event_id
```

Regla:

> Ningún identificador se deriva del contenido del usuario.

---

# 7. Enumeraciones maestras

## 7.1 MemoryDomain

```text
SESSION
PERSONAL
OPERATIONAL
```

`SESSION` nunca se persiste en SQLite en el MVP.

---

## 7.2 Sensitivity

```text
ORDINARY
PERSONAL
SENSITIVE
PROHIBITED
```

`PROHIBITED` nunca puede aparecer en una fila de memoria durable activa.

---

## 7.3 SemanticType

```text
DECISION
CONSTRAINT
PREFERENCE
PERSONAL_STATE
PERSONAL_FACT
HEALTH_CLAIM
EXPERIENCE
RELATIONSHIP
CREDENTIAL
TEMPORARY_EVENT
OTHER
```

---

## 7.4 TemporalScope

```text
INSTANT
SESSION
TEMPORARY
DURABLE
UNKNOWN
```

---

## 7.5 PersistenceIntent

La Specification v0.3.0 define:

```text
NONE
IMPLICIT
EXPLICIT
EXPLICIT_TEMPORARY
FORGET_REQUEST
```

No se agregan nuevos valores en este documento.

---

## 7.6 RestrictionLevel

```text
NONE
POTENTIALLY_SENSITIVE
NEVER_DURABLE
```

Orden de severidad:

```text
NONE
   <
POTENTIALLY_SENSITIVE
   <
NEVER_DURABLE
```

La restricción efectiva sólo puede mantenerse o aumentar.

---

## 7.7 PolicyDecision

```text
SESSION_ONLY
PROHIBITED
PERSIST
PERSIST_MINIMIZED
DEFER
PURGE_REQUEST
```

---

## 7.8 EvidenceStatus

```text
STAGED
ACTIVE
ABORTED
PURGE_REVOKED
PURGED
```

---

## 7.9 PayloadStatus

```text
STAGED
ACTIVE
PURGE_PENDING
DESTROYED
ABORTED
```

---

## 7.10 RecordStatus

```text
ACTIVE
SUPERSEDED
RETRACTED
PURGE_REVOKED
PURGED
```

---

## 7.11 Lifetime

```text
SESSION
TEMPORARY
DURABLE
```

`SESSION` no debería existir en `memory_records`; se mantiene para objetos efímeros y validación de candidatos.

---

## 7.12 PatchOperationType

```text
ADD
SUPERSEDE
RETRACT
LINK
FLAG_CONFLICT
RESOLVE_CONFLICT
PURGE_REQUEST
```

---

## 7.13 PatchStatus

```text
PROPOSED
VALIDATED
AUDIT_ACCEPTED
AUDIT_REJECTED
DEFERRED
STALE
COMMITTED
ABORTED
```

---

## 7.14 AuditDecision

```text
ACCEPT
REJECT
DEFER
```

---

## 7.15 ConflictStatus

```text
OPEN
RESOLVED
```

---

## 7.16 LeaseStatus

```text
VALID
REVOKED
EXPIRED
```

---

## 7.17 PurgeStatus

```text
PURGE_REQUESTED
PURGE_IN_PROGRESS
PURGE_COMPLETE
PURGE_FAILED
```

---

## 7.18 MountDecision

```text
ALLOW
DENY
```

No existe `MAYBE` como autorización final.

---

## 7.19 SubjectKind

Dato semántico auxiliar, no autoridad determinística:

```text
USER
THIRD_PARTY
SYSTEM
UNKNOWN
```

---

## 7.20 Polarity

```text
AFFIRMED
NEGATED
UNKNOWN
```

---

## 7.21 Modality

```text
FACTUAL
HYPOTHETICAL
QUOTED
UNCERTAIN
UNKNOWN
```

---

## 7.22 DetectionLayer

```text
INGRESS_GUARD
MEMORY_ANALYZER
SEGMENTER
PERSISTENCE_POLICY
EVIDENCE_SANITIZER
PATCH_VALIDATOR
EVIDENCE_RESOLVER
AUDITOR
COMMIT_VALIDATOR
MOUNT_POLICY
OUTPUT_GATE
PURGE_ENGINE
SESSION_CONTEXT
SAFETY_HANDLER
```

---

## 7.23 SecurityOutcome

```text
PASS
FAIL
NOT_APPLICABLE
```

---

## 7.24 ArchitecturalOutcome

```text
PASS
DEGRADED
FAIL
UNDEFINED
```

---

# 8. ValueStorageClass

Todo valor persistible debe declarar cómo se almacena.

```text
INLINE_NON_SENSITIVE
VAULT_REF
NONE
```

Reglas:

```text
PERSONAL domain
    → VAULT_REF

Sensitivity == SENSITIVE
    → VAULT_REF

Sensitivity == PROHIBITED
    → persistence forbidden

OPERATIONAL + ORDINARY
    → INLINE_NON_SENSITIVE or VAULT_REF
```

---

# 9. EphemeralInput

Objeto exclusivamente en RAM.

```python
class EphemeralInput(BaseModel):
    input_id: UUID
    session_id: UUID
    text: str
    received_at: datetime
    timezone: str
```

Nunca se serializa en `.agent-repo`.

No debe aparecer en:

- logs;
- metrics;
- exceptions;
- SQLite;
- dumps de debugging.

---

# 10. RestrictionSpan

```python
class RestrictionSpan(BaseModel):
    span_id: UUID
    input_id: UUID
    start: int
    end: int
    category: str
    restriction: RestrictionLevel
    detector_id: str
    confidence: float | None = None
```

Validaciones:

```text
0 <= start < end <= len(input)
restriction != NONE
```

`confidence` sólo es informativo y no rebaja una Hard Restriction.

---

# 11. RestrictionMap

```python
class RestrictionMap(BaseModel):
    input_id: UUID
    spans: tuple[RestrictionSpan, ...]
```

Métodos determinísticos esperados:

```text
restriction_for_range(start, end)
max_restriction_for_range(start, end)
intersects_never_durable(start, end)
```

---

# 12. MemoryCandidate

Objeto semántico todavía no autorizado para persistencia.

```python
class MemoryCandidate(BaseModel):
    candidate_id: UUID

    input_id: UUID
    source_start: int
    source_end: int

    domain_hint: MemoryDomain
    semantic_type: SemanticType
    sensitivity: Sensitivity
    persistence_intent: PersistenceIntent
    temporal_scope: TemporalScope

    subject: SubjectKind
    polarity: Polarity
    modality: Modality

    semantic_key: str | None

    analyzer_model_id: str
    analyzer_prompt_version: str

    source_span_ids: tuple[UUID, ...]
```

No contiene autoridad de persistencia.

---

# 13. PolicySnapshot

```python
class PolicySnapshot(BaseModel):
    policy_snapshot_id: UUID
    policy_version: int
    policy_hash: str
    activated_at: datetime
```

Una transacción completa debe utilizar un único snapshot.

---

# 14. PolicyEvaluation

```python
class PolicyEvaluation(BaseModel):
    candidate_id: UUID
    policy_snapshot_id: UUID
    decision: PolicyDecision
    effective_restriction: RestrictionLevel
    reason_codes: tuple[str, ...]
```

No contiene razonamiento libre.

---

# 15. TemporalResolution

```python
class TemporalResolution(BaseModel):
    source_expression: str | None
    resolved_at: datetime
    valid_until: datetime | None
    timezone: str
    resolution_status: Literal["RESOLVED", "NOT_REQUIRED", "DEFER"]
```

Regla:

```text
valid_until
```

debe ser absoluto y timezone-aware.

---

# 16. SanitizedCandidate

Objeto posterior a Policy y Evidence Sanitizer.

```python
class SanitizedCandidate(BaseModel):
    candidate_id: UUID
    policy_snapshot_id: UUID

    semantic_key: str
    domain: MemoryDomain
    semantic_type: SemanticType
    sensitivity: Sensitivity

    sanitized_text: str | None
    payload_ref: UUID | None

    removed_categories: tuple[str, ...]
    source_span_ids: tuple[UUID, ...]

    temporal: TemporalResolution | None
```

Regla:

```text
sanitized_text
```

sólo puede existir si el contenido es apto para almacenamiento inline según las reglas de storage.

---

# 17. EvidenceRecord

```python
class EvidenceRecord(BaseModel):
    evidence_id: UUID

    scope_type: Literal["BRANCH", "PERSONAL", "GLOBAL"]
    branch_id: UUID | None

    source_kind: str
    status: EvidenceStatus
    sensitivity: Sensitivity

    storage_class: ValueStorageClass
    inline_sanitized_text: str | None
    payload_ref: UUID | None

    sanitization_applied: bool
    removed_categories: tuple[str, ...]

    policy_snapshot_id: UUID
    created_at: datetime
```

Invariante:

```text
PROHIBITED → impossible
```

---

# 18. PayloadObject

Representa ciphertext gestionado por el Vault.

```python
class PayloadObject(BaseModel):
    payload_id: UUID

    purpose: Literal[
        "EVIDENCE",
        "MEMORY_VALUE",
        "PATCH_VALUE"
    ]

    status: PayloadStatus
    sensitivity: Sensitivity

    key_handle: str
    ciphertext_location: str

    created_at: datetime
    activated_at: datetime | None
    destroyed_at: datetime | None
```

`key_handle` es un identificador opaco hacia KeyProvider.

No contiene clave.

---

# 19. DraftPatch, PatchStager y binding de payload sensible

El Generator **no emite directamente un `CognitiveStatePatch` persistible**.

Emite un objeto efímero:

```text
DraftPatch
```

que puede contener valores en plaintext únicamente en RAM.

## 19.1 DraftValue

```python
class DraftValue(BaseModel):
    proposed_value: JsonValue
```

`DraftValue`:

- nunca se serializa en SQLite;
- nunca se escribe en el Vault;
- nunca aparece en logs;
- nunca entra en métricas;
- existe sólo durante la preparación de un Patch.

## 19.2 DraftPatch

```python
class DraftPatch(BaseModel):
    draft_patch_id: UUID
    branch_id: UUID | None
    base_revision: int
    core_version: int
    policy_snapshot_id: UUID
    operations: tuple[DraftPatchOperation, ...]
```

El `DraftPatch` es una propuesta del Generator, no una mutación autorizada.

## 19.3 DraftPatchSchemaValidator

Antes de crear cualquier payload:

```text
LLM raw JSON
    ↓
JSON parser
    ↓
DraftPatchSchemaValidator
    ↓
typed DraftPatch
```

Campos inesperados, operaciones desconocidas o estructuras inválidas fallan antes de asignar recursos criptográficos.

## 19.4 Persistence Content Guard sobre salida generada

El `PatchStager` vuelve a ejecutar detectores de persistencia sobre **todos los campos generados que podrían llegar a almacenamiento**, incluyendo:

- semantic keys;
- values;
- labels;
- relation types cuando admitan texto libre;
- metadata autorizada.

Esto protege también frente a contenido prohibido **inventado por el Generator** y que, por definición, no estaba presente en el `RestrictionMap` del input original.

Una `Hard Restriction` detectada en esta etapa produce:

```text
PROHIBITED_CONTENT
NO STAGING
```

## 19.5 PatchStager

Componente trusted deterministic.

Entrada:

```text
DraftPatch
+
PolicyEvaluation
+
RestrictionMap
```

Salida:

```text
StagedPatch
+
PendingPayloadEnvelope[]
```

Para `domain = PERSONAL`, el `PatchStager`:

1. reserva un `payload_id` aleatorio;
2. genera material criptográfico efímero;
3. cifra el valor **en RAM**;
4. calcula un digest del ciphertext aleatorizado;
5. reemplaza el plaintext por un `PendingValueReference`;
6. elimina el plaintext del objeto staged tan pronto deja de ser necesario.

Todavía **no escribe ciphertext ni claves en almacenamiento durable**.

## 19.6 PendingPayloadEnvelope

Objeto sólo en RAM:

```python
class PendingPayloadEnvelope(BaseModel):
    payload_id: UUID
    ciphertext: bytes
    ciphertext_digest: str
    key_material: SecretBytes
    purpose: str
    sensitivity: Sensitivity
```

No es serializable como modelo durable.

## 19.7 PendingValueReference

```python
class PendingValueReference(BaseModel):
    storage_class: Literal["VAULT_REF"]
    payload_ref: UUID
    ciphertext_digest: str
```

El `StagedPatch` contiene la referencia y el digest del ciphertext, no plaintext.

## 19.8 ValueReference durable

Después de `Audit = ACCEPT` y de `PayloadMaterializer`, la referencia durable mantiene:

```python
class ValueReference(BaseModel):
    storage_class: ValueStorageClass
    inline_value: JsonValue | None
    payload_ref: UUID | None
    ciphertext_digest: str | None
```

Validación:

```text
INLINE_NON_SENSITIVE
    → inline_value required
    → payload_ref null
    → ciphertext_digest null

VAULT_REF
    → payload_ref required
    → inline_value null
    → ciphertext_digest required

NONE
    → all value fields null
```

El `payload_id` es opaco, aleatorio e independiente del plaintext.

---

# 20. Patch Hash, Audit Binding e idempotencia

`patch_hash` existe para **Exact Audit Binding**, no para definir identidad semántica global.

La representación canónica incluye:

- `patch_id`;
- branch;
- base revision;
- Core version;
- Policy Snapshot;
- operaciones;
- Evidence refs;
- `payload_id`;
- `ciphertext_digest` para valores Vault-backed.

Nunca incluye:

```text
SHA256(plaintext_sensitive_value)
```

Para un valor sensible, el digest utilizado en el binding corresponde al **ciphertext aleatorizado** producido en RAM.

Esto permite verificar que el ciphertext materializado después del Audit es exactamente el que pertenecía al Patch auditado, sin conservar un verificador directo del plaintext.

## 20.1 `patch_hash` NO es una clave de unicidad

Dos propuestas distintas pueden producir hashes repetidos bajo ciertos esquemas de canonicalización o pueden volver a plantearse legítimamente bajo otro contexto temporal.

Por ello:

```text
patches.patch_hash
```

**NO tiene constraint `UNIQUE`.**

Puede existir un índice normal para lookup:

```sql
CREATE INDEX ix_patches_patch_hash
ON patches(patch_hash);
```

## 20.2 Idempotencia

La identidad de una propuesta es:

```text
patch_id
```

La idempotencia de Commit se garantiza mediante:

```text
commits.patch_id UNIQUE
```

Por tanto:

```text
same patch_id
    → cannot commit twice
```

Una nueva propuesta futura con nuevo `patch_id` se evalúa nuevamente bajo:

- State actual;
- base revision actual;
- Policy actual;
- Evidence actual.

No queda bloqueada por un rechazo histórico.

---

# 21. Patch Operations

Todas las operaciones son una unión discriminada.

## ADD

```python
class AddOperation(BaseModel):
    op: Literal["ADD"]
    operation_id: UUID

    domain: MemoryDomain
    semantic_key: str
    sensitivity: Sensitivity

    value: ValueReference
    evidence_refs: tuple[UUID, ...]
    lifetime: Lifetime
    valid_until: datetime | None
    mount_policy_id: UUID | None
```

---

## SUPERSEDE

```python
class SupersedeOperation(BaseModel):
    op: Literal["SUPERSEDE"]
    operation_id: UUID

    target_record_id: UUID

    sensitivity: Sensitivity
    value: ValueReference
    evidence_refs: tuple[UUID, ...]

    lifetime: Lifetime
    valid_until: datetime | None
```

---

## RETRACT

```python
class RetractOperation(BaseModel):
    op: Literal["RETRACT"]
    operation_id: UUID
    target_record_id: UUID
    evidence_refs: tuple[UUID, ...]
```

---

## LINK

```python
class LinkOperation(BaseModel):
    op: Literal["LINK"]
    operation_id: UUID

    source_record_id: UUID
    target_record_id: UUID
    relation_type: str

    evidence_refs: tuple[UUID, ...]
```

---

## FLAG_CONFLICT

```python
class FlagConflictOperation(BaseModel):
    op: Literal["FLAG_CONFLICT"]
    operation_id: UUID

    semantic_key: str
    competing_record_refs: tuple[UUID, ...]
    evidence_refs: tuple[UUID, ...]
```

---

## RESOLVE_CONFLICT

```python
class ResolveConflictOperation(BaseModel):
    op: Literal["RESOLVE_CONFLICT"]
    operation_id: UUID

    conflict_id: UUID
    winning_record_id: UUID | None
    replacement: ValueReference | None

    evidence_refs: tuple[UUID, ...]
```

---

## PURGE_REQUEST

```python
class PurgeRequestOperation(BaseModel):
    op: Literal["PURGE_REQUEST"]
    operation_id: UUID

    target_record_id: UUID
    reason_code: str
```

Nunca incluye el valor que se solicita borrar.

Validación obligatoria:

```text
target_record.domain == PERSONAL
```

Si no:

```text
PURGE_DOMAIN_FORBIDDEN
NO AUDIT
NO COMMIT
```

Un `VAULT_REF` operacional no adquiere derecho a PURGE sólo por estar cifrado.

---

# 22. CognitiveStatePatch

```python
class CognitiveStatePatch(BaseModel):
    patch_id: UUID

    branch_id: UUID | None
    base_revision: int

    core_version: int
    policy_snapshot_id: UUID

    operations: tuple[PatchOperation, ...]

    generator_model_id: str
    generator_prompt_version: str
```

Después de canonicalización se calcula:

```text
patch_hash
```

---

# 23. Canonicalización

Canonical Patch JSON:

- UTF-8;
- claves ordenadas;
- representación estable de enums;
- datetimes en RFC3339 UTC;
- IDs normalizados;
- arrays preservan orden semántico;
- sin campos extra;
- sin whitespace significativo;
- sin timestamps generados después de creación del objeto;
- sin plaintext personal Vault-backed;
- para `VAULT_REF`, incluye `payload_id + ciphertext_digest`.

---

# 24. AuditResult

```python
class AuditResult(BaseModel):
    audit_id: UUID
    patch_id: UUID
    patch_hash: str

    branch_id: UUID | None
    base_revision: int
    core_version: int
    policy_snapshot_id: UUID

    evidence_refs: tuple[UUID, ...]
    evidence_binding: str

    decision: AuditDecision
    reason_codes: tuple[str, ...]

    auditor_model_id: str
    auditor_prompt_version: str

    created_at: datetime
```

Prohibido:

```text
free-form chain-of-thought
raw secret
sensitive payload
```

---

# 25. CommitRecord

```python
class CommitRecord(BaseModel):
    commit_id: UUID

    branch_id: UUID
    revision: int
    previous_commit_id: UUID | None

    patch_id: UUID
    patch_hash: str
    audit_id: UUID

    core_version: int
    policy_snapshot_id: UUID

    committed_at: datetime
```

Un Patch sólo puede producir un Commit.

---

# 26. MemoryRecord

```python
class MemoryRecord(BaseModel):
    record_id: UUID

    domain: MemoryDomain
    branch_id: UUID | None

    semantic_key: str
    kind: SemanticType

    status: RecordStatus
    sensitivity: Sensitivity

    storage_class: ValueStorageClass
    inline_value: JsonValue | None
    payload_ref: UUID | None

    lifetime: Lifetime
    valid_until: datetime | None
    timezone: str | None

    policy_snapshot_id: UUID
    mount_policy_id: UUID | None

    created_commit_id: UUID
    supersedes_record_id: UUID | None

    created_at: datetime
    purged_at: datetime | None
```

---

# 27. MemoryRecord storage invariants

## Personal

```text
domain == PERSONAL
    ⇒ storage_class == VAULT_REF
    ⇒ payload_ref != null
    ⇒ inline_value == null
```

## Prohibited

```text
sensitivity == PROHIBITED
    ⇒ row creation forbidden
```

## Operational ordinary

Puede usar inline.

## Purged

Para Personal Memory:

```text
status == PURGED
    ⇒ storage_class == VAULT_REF
    ⇒ inline_value == null
    ⇒ payload_ref MAY remain
```

El `payload_ref` se conserva porque es un UUID aleatorio no derivado del contenido y preserva trazabilidad referencial hacia un `payload_objects.status = DESTROYED`.

El contenido se vuelve inaccesible porque:

```text
key capability = destroyed
ciphertext = deleted
payload object = DESTROYED tombstone
```

No se rompe ni reescribe el Patch histórico para eliminar la referencia.

Sólo permanecen metadatos mínimos no reconstructivos.

---

# 28. ConflictRecord

```python
class ConflictRecord(BaseModel):
    conflict_id: UUID
    branch_id: UUID
    semantic_key: str
    status: ConflictStatus
    created_commit_id: UUID
    resolved_commit_id: UUID | None
```

Los valores competidores se referencian por `record_id`.

---

# 29. MountPolicy

```python
class MountPolicy(BaseModel):
    mount_policy_id: UUID
    version: int

    mode: Literal[
        "GLOBAL_INTERACTION_PREFERENCE",
        "BRANCH_ONLY",
        "EXPLICIT_SCOPES",
        "EXPLICIT_ONLY"
    ]

    allowed_scopes: tuple[str, ...]
    allow_sensitive_operational_mount: bool

    policy_hash: str
```

La autorización final sigue siendo `ALLOW` o `DENY`.

---

# 30. AccessLease

```python
class AccessLease(BaseModel):
    lease_id: UUID
    record_id: UUID

    requested_scope: str
    active_branch_id: UUID | None

    policy_snapshot_id: UUID

    status: LeaseStatus

    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
```

No contiene payload.

---

# 31. PurgeJob

```python
class PurgeJob(BaseModel):
    purge_id: UUID
    record_id: UUID

    status: PurgeStatus

    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    failure_code: str | None
```

---

# 32. PurgeTargetResult

```python
class PurgeTargetResult(BaseModel):
    purge_id: UUID
    target_id: str

    purge_attempted: bool
    purge_succeeded: bool
    verify_absent: bool

    last_checked_at: datetime
    failure_code: str | None
```

`PURGE_COMPLETE` sólo es válido si todos los targets registrados retornan:

```text
verify_absent = true
```

---

# 33. DetectionEvent

```python
class DetectionEvent(BaseModel):
    event_id: UUID
    run_id: UUID | None

    threat_type: str

    expected_detection_layer: DetectionLayer | None
    actual_detection_layer: DetectionLayer | None

    security_outcome: SecurityOutcome
    architectural_outcome: ArchitecturalOutcome

    policy_bypass: bool

    category: str | None
    created_at: datetime
```

No contiene:

- raw input;
- secret;
- sensitive summary;
- reversible encoding.

---

# 34. TestRun

```python
class TestRun(BaseModel):
    run_id: UUID

    test_id: str
    run_kind: Literal["GOLDEN", "ADVERSARIAL", "UNIT", "INTEGRATION"]

    spec_version: str
    technical_design_version: str
    git_commit: str

    policy_snapshot_id: UUID | None

    analyzer_model_id: str | None
    generator_model_id: str | None
    auditor_model_id: str | None

    analyzer_prompt_version: str | None
    generator_prompt_version: str | None
    auditor_prompt_version: str | None

    temperature: float | None
    seed: int | None

    result: str

    input_tokens: int | None
    output_tokens: int | None

    latency_ms: int | None

    started_at: datetime
    ended_at: datetime | None
```

---

# 35. Session model

Session State no se escribe en SQLite.

```python
class SessionState(BaseModel):
    session_id: UUID
    created_at: datetime
    expires_at: datetime

    conversational_items: list[SessionItem]
```

`SessionItem` puede contener información sensible mientras permanezca exclusivamente en RAM.

Al expirar:

```text
drop()
```

No se convierte automáticamente en Evidence.

---

# 36. Esquema SQLite — configuración

Al abrir el repositorio:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA secure_delete = ON;
PRAGMA trusted_schema = OFF;
```

MVP:

```text
single process writer
```

Transacciones de mutación:

```sql
BEGIN IMMEDIATE;
```

---

# 37. Tabla schema_migrations

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

---

# 38. Tabla core_snapshots

```sql
CREATE TABLE core_snapshots (
    core_version INTEGER PRIMARY KEY,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

Core no debe contener Personal Memory.

---

# 39. Tabla branches

```sql
CREATE TABLE branches (
    branch_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL
        CHECK (status IN ('ACTIVE', 'ARCHIVED')),

    current_revision INTEGER NOT NULL DEFAULT 0
        CHECK (current_revision >= 0),

    core_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (core_version)
        REFERENCES core_snapshots(core_version)
);
```

---

# 40. Tabla branch_contracts

```sql
CREATE TABLE branch_contracts (
    contract_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,

    UNIQUE(branch_id, version),

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id)
);
```

No almacenar secretos dentro del contract.

---

# 41. Tabla policies

```sql
CREATE TABLE policies (
    policy_snapshot_id TEXT PRIMARY KEY,
    policy_version INTEGER NOT NULL UNIQUE,
    policy_hash TEXT NOT NULL UNIQUE,
    source_ref TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0
        CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL
);
```

Debe existir como máximo una Policy activa.

La aplicación garantiza esa cardinalidad dentro de una transacción.

---

# 42. Tabla mount_policies

```sql
CREATE TABLE mount_policies (
    mount_policy_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (
        mode IN (
            'GLOBAL_INTERACTION_PREFERENCE',
            'BRANCH_ONLY',
            'EXPLICIT_SCOPES',
            'EXPLICIT_ONLY'
        )
    ),
    allowed_scopes_json TEXT NOT NULL
        CHECK (json_valid(allowed_scopes_json)),
    allow_sensitive_operational_mount INTEGER NOT NULL DEFAULT 0
        CHECK (allow_sensitive_operational_mount IN (0, 1)),
    policy_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

# 43. Tabla payload_objects

SQLite almacena **metadata del ciphertext**, nunca plaintext.

```sql
CREATE TABLE payload_objects (
    payload_id TEXT PRIMARY KEY,

    purpose TEXT NOT NULL CHECK (
        purpose IN ('EVIDENCE', 'MEMORY_VALUE', 'PATCH_VALUE')
    ),

    status TEXT NOT NULL CHECK (
        status IN (
            'STAGED',
            'ACTIVE',
            'PURGE_PENDING',
            'DESTROYED',
            'ABORTED'
        )
    ),

    sensitivity TEXT NOT NULL CHECK (
        sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')
    ),

    key_handle TEXT,
    ciphertext_location TEXT,

    created_at TEXT NOT NULL,
    activated_at TEXT,
    destroyed_at TEXT,

    CHECK (
        (
            status IN ('STAGED', 'ACTIVE', 'PURGE_PENDING')
            AND key_handle IS NOT NULL
            AND ciphertext_location IS NOT NULL
        )
        OR
        (
            status IN ('DESTROYED', 'ABORTED')
            AND key_handle IS NULL
            AND ciphertext_location IS NULL
        )
    )
);
```

No se persiste `PROHIBITED`.

---

# 44. Tabla evidence

```sql
CREATE TABLE evidence (
    evidence_id TEXT PRIMARY KEY,

    scope_type TEXT NOT NULL CHECK (
        scope_type IN ('BRANCH', 'PERSONAL', 'GLOBAL')
    ),

    branch_id TEXT,

    source_kind TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'STAGED',
            'ACTIVE',
            'ABORTED',
            'PURGE_REVOKED',
            'PURGED'
        )
    ),

    sensitivity TEXT NOT NULL CHECK (
        sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')
    ),

    storage_class TEXT NOT NULL CHECK (
        storage_class IN ('INLINE_NON_SENSITIVE', 'VAULT_REF')
    ),

    inline_sanitized_text TEXT,
    payload_id TEXT,

    sanitization_applied INTEGER NOT NULL
        CHECK (sanitization_applied IN (0, 1)),

    removed_categories_json TEXT NOT NULL
        CHECK (json_valid(removed_categories_json)),

    policy_snapshot_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    purged_at TEXT,

    CHECK (
        (storage_class = 'INLINE_NON_SENSITIVE'
            AND inline_sanitized_text IS NOT NULL
            AND payload_id IS NULL)
        OR
        (storage_class = 'VAULT_REF'
            AND inline_sanitized_text IS NULL
            AND payload_id IS NOT NULL)
    ),

    CHECK (
        scope_type != 'BRANCH' OR branch_id IS NOT NULL
    ),

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (payload_id)
        REFERENCES payload_objects(payload_id),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

---

# 45. Tabla patches

```sql
CREATE TABLE patches (
    patch_id TEXT PRIMARY KEY,

    branch_id TEXT,
    base_revision INTEGER NOT NULL CHECK (base_revision >= 0),

    core_version INTEGER NOT NULL,
    policy_snapshot_id TEXT NOT NULL,

    patch_hash TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'PROPOSED',
            'VALIDATED',
            'AUDIT_ACCEPTED',
            'AUDIT_REJECTED',
            'DEFERRED',
            'STALE',
            'COMMITTED',
            'ABORTED'
        )
    ),

    generator_model_id TEXT NOT NULL,
    generator_prompt_version TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (core_version)
        REFERENCES core_snapshots(core_version),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

No posee campo de razonamiento ni raw payload.

Índice de lookup:

```sql
CREATE INDEX ix_patches_patch_hash
ON patches(patch_hash);
```

La idempotencia se resuelve por `patch_id`, no por unicidad global del hash.

---

# 46. Tabla patch_operations

```sql
CREATE TABLE patch_operations (
    operation_id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL,
    op_index INTEGER NOT NULL,

    op_type TEXT NOT NULL CHECK (
        op_type IN (
            'ADD',
            'SUPERSEDE',
            'RETRACT',
            'LINK',
            'FLAG_CONFLICT',
            'RESOLVE_CONFLICT',
            'PURGE_REQUEST'
        )
    ),

    domain TEXT CHECK (
        domain IS NULL OR
        domain IN ('PERSONAL', 'OPERATIONAL')
    ),

    semantic_key TEXT,
    sensitivity TEXT CHECK (
        sensitivity IS NULL OR
        sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')
    ),

    target_record_id TEXT,

    value_storage_class TEXT CHECK (
        value_storage_class IS NULL OR
        value_storage_class IN (
            'INLINE_NON_SENSITIVE',
            'VAULT_REF',
            'NONE'
        )
    ),

    inline_value_json TEXT,
    payload_id TEXT,

    relation_type TEXT,
    conflict_id TEXT,
    reason_code TEXT,

    UNIQUE(patch_id, op_index),

    CHECK (
        value_storage_class IS NULL
        OR value_storage_class = 'NONE'
        OR (
            value_storage_class = 'INLINE_NON_SENSITIVE'
            AND inline_value_json IS NOT NULL
            AND json_valid(inline_value_json)
            AND payload_id IS NULL
        )
        OR (
            value_storage_class = 'VAULT_REF'
            AND inline_value_json IS NULL
            AND payload_id IS NOT NULL
        )
    ),

    FOREIGN KEY (patch_id)
        REFERENCES patches(patch_id)
        ON DELETE CASCADE,

    FOREIGN KEY (payload_id)
        REFERENCES payload_objects(payload_id),

    FOREIGN KEY (target_record_id)
        REFERENCES memory_records(record_id),

    FOREIGN KEY (conflict_id)
        REFERENCES conflicts(conflict_id)
);
```

Nota: la referencia adelantada a `memory_records` / `conflicts` es válida conceptualmente; las migraciones reales crearán tablas en un orden compatible con SQLite.

---

# 47. Tabla patch_evidence

```sql
CREATE TABLE patch_evidence (
    patch_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,

    PRIMARY KEY (patch_id, evidence_id),

    FOREIGN KEY (patch_id)
        REFERENCES patches(patch_id)
        ON DELETE CASCADE,

    FOREIGN KEY (evidence_id)
        REFERENCES evidence(evidence_id)
);
```

---

# 48. Tabla audits

```sql
CREATE TABLE audits (
    audit_id TEXT PRIMARY KEY,

    patch_id TEXT NOT NULL UNIQUE,
    patch_hash TEXT NOT NULL,

    branch_id TEXT,
    base_revision INTEGER NOT NULL,

    core_version INTEGER NOT NULL,
    policy_snapshot_id TEXT NOT NULL,

    decision TEXT NOT NULL CHECK (
        decision IN ('ACCEPT', 'REJECT', 'DEFER')
    ),

    reason_codes_json TEXT NOT NULL
        CHECK (json_valid(reason_codes_json)),

    evidence_binding TEXT NOT NULL,

    auditor_model_id TEXT NOT NULL,
    auditor_prompt_version TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (patch_id)
        REFERENCES patches(patch_id),

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (core_version)
        REFERENCES core_snapshots(core_version),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

`reason_codes_json` contiene códigos, no explicación libre sensible.

---

# 49. Tabla audit_evidence

```sql
CREATE TABLE audit_evidence (
    audit_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,

    PRIMARY KEY (audit_id, evidence_id),

    FOREIGN KEY (audit_id)
        REFERENCES audits(audit_id)
        ON DELETE CASCADE,

    FOREIGN KEY (evidence_id)
        REFERENCES evidence(evidence_id)
);
```

---

# 50. Tabla commits

```sql
CREATE TABLE commits (
    commit_id TEXT PRIMARY KEY,

    branch_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),

    previous_commit_id TEXT,

    patch_id TEXT NOT NULL UNIQUE,
    patch_hash TEXT NOT NULL,
    audit_id TEXT NOT NULL UNIQUE,

    core_version INTEGER NOT NULL,
    policy_snapshot_id TEXT NOT NULL,

    committed_at TEXT NOT NULL,

    UNIQUE(branch_id, revision),

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (previous_commit_id)
        REFERENCES commits(commit_id),

    FOREIGN KEY (patch_id)
        REFERENCES patches(patch_id),

    FOREIGN KEY (audit_id)
        REFERENCES audits(audit_id),

    FOREIGN KEY (core_version)
        REFERENCES core_snapshots(core_version),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

---

# 51. Tabla memory_records

```sql
CREATE TABLE memory_records (
    record_id TEXT PRIMARY KEY,

    domain TEXT NOT NULL CHECK (
        domain IN ('PERSONAL', 'OPERATIONAL')
    ),

    branch_id TEXT,

    semantic_key TEXT NOT NULL,
    kind TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'ACTIVE',
            'SUPERSEDED',
            'RETRACTED',
            'PURGE_REVOKED',
            'PURGED'
        )
    ),

    sensitivity TEXT NOT NULL CHECK (
        sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')
    ),

    storage_class TEXT NOT NULL CHECK (
        storage_class IN (
            'INLINE_NON_SENSITIVE',
            'VAULT_REF',
            'NONE'
        )
    ),

    inline_value_json TEXT,
    payload_id TEXT,

    lifetime TEXT NOT NULL CHECK (
        lifetime IN ('TEMPORARY', 'DURABLE')
    ),

    valid_until TEXT,
    timezone TEXT,

    policy_snapshot_id TEXT NOT NULL,
    mount_policy_id TEXT,

    created_commit_id TEXT NOT NULL,
    supersedes_record_id TEXT,

    created_at TEXT NOT NULL,
    purged_at TEXT,

    CHECK (
        domain != 'PERSONAL'
        OR storage_class = 'VAULT_REF'
    ),

    CHECK (
        status != 'PURGED'
        OR (
            inline_value_json IS NULL
            AND payload_id IS NOT NULL
            AND storage_class = 'VAULT_REF'
        )
    ),

    CHECK (
        storage_class = 'NONE'
        OR (
            storage_class = 'INLINE_NON_SENSITIVE'
            AND inline_value_json IS NOT NULL
            AND json_valid(inline_value_json)
            AND payload_id IS NULL
        )
        OR (
            storage_class = 'VAULT_REF'
            AND inline_value_json IS NULL
            AND payload_id IS NOT NULL
        )
    ),

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (payload_id)
        REFERENCES payload_objects(payload_id),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id),

    FOREIGN KEY (mount_policy_id)
        REFERENCES mount_policies(mount_policy_id),

    FOREIGN KEY (created_commit_id)
        REFERENCES commits(commit_id),

    FOREIGN KEY (supersedes_record_id)
        REFERENCES memory_records(record_id)
);
```

---

# 52. Active-key uniqueness

SQLite no puede expresar fácilmente todas las reglas semánticas mediante un único CHECK.

Se agrega índice parcial:

```sql
CREATE UNIQUE INDEX ux_active_operational_key
ON memory_records(branch_id, semantic_key)
WHERE status = 'ACTIVE'
  AND domain = 'OPERATIONAL';
```

Para Personal Memory:

```sql
CREATE UNIQUE INDEX ux_active_personal_key
ON memory_records(semantic_key)
WHERE status = 'ACTIVE'
  AND domain = 'PERSONAL';
```

MVP single-user.

---

# 53. Tabla links

```sql
CREATE TABLE record_links (
    link_id TEXT PRIMARY KEY,

    source_record_id TEXT NOT NULL,
    target_record_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,

    created_commit_id TEXT NOT NULL,

    UNIQUE(source_record_id, target_record_id, relation_type),

    FOREIGN KEY (source_record_id)
        REFERENCES memory_records(record_id),

    FOREIGN KEY (target_record_id)
        REFERENCES memory_records(record_id),

    FOREIGN KEY (created_commit_id)
        REFERENCES commits(commit_id)
);
```

---

# 54. Tabla conflicts

```sql
CREATE TABLE conflicts (
    conflict_id TEXT PRIMARY KEY,

    branch_id TEXT NOT NULL,
    semantic_key TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN ('OPEN', 'RESOLVED')
    ),

    created_commit_id TEXT NOT NULL,
    resolved_commit_id TEXT,

    created_at TEXT NOT NULL,
    resolved_at TEXT,

    FOREIGN KEY (branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (created_commit_id)
        REFERENCES commits(commit_id),

    FOREIGN KEY (resolved_commit_id)
        REFERENCES commits(commit_id)
);
```

---

# 55. Tabla conflict_records

```sql
CREATE TABLE conflict_records (
    conflict_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    role TEXT NOT NULL,

    PRIMARY KEY (conflict_id, record_id),

    FOREIGN KEY (conflict_id)
        REFERENCES conflicts(conflict_id),

    FOREIGN KEY (record_id)
        REFERENCES memory_records(record_id)
);
```

---

# 56. Tabla access_leases

```sql
CREATE TABLE access_leases (
    lease_id TEXT PRIMARY KEY,

    record_id TEXT NOT NULL,

    requested_scope TEXT NOT NULL,
    active_branch_id TEXT,

    policy_snapshot_id TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN ('VALID', 'REVOKED', 'EXPIRED')
    ),

    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,

    FOREIGN KEY (record_id)
        REFERENCES memory_records(record_id),

    FOREIGN KEY (active_branch_id)
        REFERENCES branches(branch_id),

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

Índice:

```sql
CREATE INDEX ix_valid_leases_record
ON access_leases(record_id, status);
```

---

# 57. Tabla purge_jobs

```sql
CREATE TABLE purge_jobs (
    purge_id TEXT PRIMARY KEY,

    record_id TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'PURGE_REQUESTED',
            'PURGE_IN_PROGRESS',
            'PURGE_COMPLETE',
            'PURGE_FAILED'
        )
    ),

    requested_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,

    failure_code TEXT,

    FOREIGN KEY (record_id)
        REFERENCES memory_records(record_id)
);
```

---

# 58. Tabla purge_target_results

```sql
CREATE TABLE purge_target_results (
    purge_id TEXT NOT NULL,
    target_id TEXT NOT NULL,

    purge_attempted INTEGER NOT NULL
        CHECK (purge_attempted IN (0, 1)),

    purge_succeeded INTEGER NOT NULL
        CHECK (purge_succeeded IN (0, 1)),

    verify_absent INTEGER NOT NULL
        CHECK (verify_absent IN (0, 1)),

    last_checked_at TEXT NOT NULL,
    failure_code TEXT,

    PRIMARY KEY (purge_id, target_id),

    FOREIGN KEY (purge_id)
        REFERENCES purge_jobs(purge_id)
        ON DELETE CASCADE
);
```

---

# 59. Tabla detection_events

```sql
CREATE TABLE detection_events (
    event_id TEXT PRIMARY KEY,

    run_id TEXT,
    threat_type TEXT NOT NULL,

    expected_detection_layer TEXT,
    actual_detection_layer TEXT,

    security_outcome TEXT NOT NULL CHECK (
        security_outcome IN ('PASS', 'FAIL', 'NOT_APPLICABLE')
    ),

    architectural_outcome TEXT NOT NULL CHECK (
        architectural_outcome IN (
            'PASS',
            'DEGRADED',
            'FAIL',
            'UNDEFINED'
        )
    ),

    policy_bypass INTEGER NOT NULL
        CHECK (policy_bypass IN (0, 1)),

    category TEXT,

    created_at TEXT NOT NULL
);
```

No existe columna para raw input.

---

# 60. Tabla test_runs

```sql
CREATE TABLE test_runs (
    run_id TEXT PRIMARY KEY,

    test_id TEXT NOT NULL,
    run_kind TEXT NOT NULL CHECK (
        run_kind IN (
            'GOLDEN',
            'ADVERSARIAL',
            'UNIT',
            'INTEGRATION'
        )
    ),

    spec_version TEXT NOT NULL,
    technical_design_version TEXT NOT NULL,
    git_commit TEXT NOT NULL,

    policy_snapshot_id TEXT,

    analyzer_model_id TEXT,
    generator_model_id TEXT,
    auditor_model_id TEXT,

    analyzer_prompt_version TEXT,
    generator_prompt_version TEXT,
    auditor_prompt_version TEXT,

    temperature REAL,
    seed INTEGER,

    result TEXT NOT NULL,

    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,

    started_at TEXT NOT NULL,
    ended_at TEXT,

    FOREIGN KEY (policy_snapshot_id)
        REFERENCES policies(policy_snapshot_id)
);
```

---

# 61. Columnas prohibidas

Ninguna tabla durable debe incorporar campos equivalentes a:

```text
raw_input
raw_message
raw_secret
password
private_key
api_key
full_sensitive_prompt
audit_chain_of_thought
model_reasoning
sensitive_summary
```

Una migración que agregue un campo de texto libre deberá pasar revisión de Persistence Boundary.

---

# 62. Payload Vault layout

MVP:

```text
.agent-repo/
  vault/
    payloads/
      <payload-id>.bin
    staging/
      <payload-id>.tmp
```

Los nombres son IDs aleatorios.

Nunca:

```text
<semantic-key>.bin
<username>.bin
<hash-of-plaintext>.bin
```

---

# 63. Patch staging y materialización del Vault

SQLite y filesystem no comparten una transacción ACID única.

Además, el MVP evita crear contenido durable de memoria antes de que exista un Audit `ACCEPT`.

Por ello se separan dos conceptos:

```text
PatchStager
    → RAM only

PayloadMaterializer
    → durable staging, only after Audit ACCEPT
```

## 63.1 Pre-Audit staging — RAM only

```text
Generator
   ↓
DraftPatch
   ↓
DraftPatchSchemaValidator
   ↓
PatchStager
   ↓
StagedPatch + PendingPayloadEnvelope[]
   ↓
PatchValidator
   ↓
EvidenceResolver
   ↓
Auditor
```

Hasta este punto:

```text
NO ciphertext file
NO key in persistent KeyProvider
NO payload_objects durable content row required
NO plaintext in SQLite
```

## 63.2 Audit REJECT / DEFER

Si:

```text
Audit != ACCEPT
```

entonces:

```text
zeroize/drop PendingPayloadEnvelope
discard plaintext draft
persist only allowed non-sensitive audit telemetry
```

No se materializa el payload.

## 63.3 Audit ACCEPT

Sólo entonces `PayloadMaterializer`:

```text
1. verifies ciphertext_digest against PendingPayloadEnvelope
2. persists/wraps key through KeyProvider
3. writes exact ciphertext bytes to vault/staging/<payload-id>.tmp
4. fsync
5. inserts payload_objects row status=STAGED
6. persists the accepted Patch/Audit metadata
7. enters Commit validation
```

El `ciphertext_digest` utilizado por el Patch no cambia.

## 63.4 Commit success

Después de Commit:

```text
atomic rename staging/<id>.tmp
    → payloads/<id>.bin

payload_objects.status
    STAGED → ACTIVE
```

La coordinación exacta se recupera mediante reconciliation si el proceso cae entre DB Commit y file rename.

## 63.5 Commit failure after Audit ACCEPT

Si el Commit falla por:

- stale revision;
- Policy stale;
- precondition failure;
- crash recuperable;

el payload no debe quedar disponible.

Cleanup:

```text
destroy key
delete staged ciphertext
payload_objects.status → ABORTED
key_handle → NULL
ciphertext_location → NULL
```

El Patch/Audit histórico puede conservar referencias opacas al `payload_id`, pero no contenido recuperable.

---

# 64. Startup reconciliation

Al iniciar el proceso se buscan:

```text
payload status = STAGED
```

Para cada uno se verifica si existe un Commit válido que requiera ese payload.

### Commit válido

Completar atomic rename y activar.

### Sin Commit válido

```text
destroy key
delete ciphertext
status -> ABORTED
key_handle -> NULL
ciphertext_location -> NULL
```

Nunca activar un payload huérfano por inferencia.

También se verifican archivos de staging sin fila SQLite y se eliminan de forma conservadora.

---

# 65. State Machine — Memory Record

```text
                 SUPERSEDE
ACTIVE --------------------------> SUPERSEDED
  |
  | RETRACT
  v
RETRACTED

ACTIVE / SUPERSEDED / RETRACTED
             |
             | PURGE_REQUEST
             v
       PURGE_REVOKED
             |
             | verified erasure
             v
           PURGED
```

Reglas:

- `PURGED` es terminal.
- `PURGE_REVOKED` nunca vuelve a `ACTIVE`.
- `SUPERSEDED` no vuelve a `ACTIVE`.
- `RETRACTED` no vuelve a `ACTIVE`.
- Rollback semántico crea un nuevo Commit; no revive filas anteriores.

---

# 66. State Machine — Evidence

```text
STAGED
  | \
  |  \ rejected / timeout
  |   v
  | ABORTED
  |
  | referenced by committed memory
  v
ACTIVE
  |
  | purge request
  v
PURGE_REVOKED
  |
  | verified erasure
  v
PURGED
```

---

# 67. State Machine — Payload

```text
STAGED
  | \
  |  \ abort
  |   v
  | ABORTED
  |
  | commit activation
  v
ACTIVE
  |
  | purge
  v
PURGE_PENDING
  |
  | key destroyed + ciphertext removed/verified
  v
DESTROYED
```

Al entrar en `DESTROYED`:

```text
payload_id remains
key_handle = NULL
ciphertext_location = NULL
```

`DESTROYED` es terminal.

---

# 68. State Machine — Patch

```text
PROPOSED
   |
   v
VALIDATED
   |
   +---- invalidated by revision/policy ---> STALE
   |
   v
AUDIT_ACCEPTED ---------------------> COMMITTED
   |
   +---- commit failure/stale ------> STALE

VALIDATED -> AUDIT_REJECTED -> ABORTED
VALIDATED -> DEFERRED
```

`AUDIT_REJECTED` jamás puede llegar a `COMMITTED`.

---

# 69. State Machine — Lease

```text
VALID
 |  \
 |   \ TTL
 |    v
 |  EXPIRED
 |
 | PURGE / policy revocation
 v
REVOKED
```

`REVOKED` y `EXPIRED` son terminales.

---

# 70. State Machine — PURGE

```text
PURGE_REQUESTED
       |
       v
PURGE_IN_PROGRESS
     /       \
    /         \
all verified   one/more failures
  v               v
PURGE_COMPLETE  PURGE_FAILED
                    |
                    | retry
                    v
              PURGE_IN_PROGRESS
```

`PURGE_FAILED` **no restaura acceso**.

---

# 71. Commit transaction boundary

Commit usa:

```sql
BEGIN IMMEDIATE;
```

Orden lógico:

```text
1. reload branch current_revision
2. verify Patch status
3. verify Audit ACCEPT
4. verify exact patch_hash
5. verify evidence bindings
6. verify current core_version
7. verify current policy_snapshot
8. verify operation preconditions
9. verify idempotency
10. apply memory mutations
11. create commit row
12. advance branch revision
13. activate staged Evidence/Payload metadata
14. mark Patch COMMITTED
15. COMMIT
```

Si cualquier paso falla:

```text
ROLLBACK
```

---

# 72. File Vault finalization

La activación del ciphertext debe coordinarse con Commit.

Para el MVP:

- staging file se escribe antes;
- DB transaction activa referencias;
- rename final ocurre bajo un coordinador con recovery journal lógico;
- startup reconciliation corrige estados incompletos.

El diseño debe probar explícitamente crash points entre:

```text
DB COMMIT
```

y:

```text
file rename
```

antes de considerar el Vault robusto.

---

# 73. Purge transaction boundary

PURGE ocurre en dos fases.

## Fase 1 — Revocación lógica atómica

En SQLite:

```text
BEGIN IMMEDIATE

record -> PURGE_REVOKED
evidence -> PURGE_REVOKED
leases -> REVOKED
purge_job -> PURGE_REQUESTED

COMMIT
```

Desde ese instante:

```text
NO NEW MOUNT
NO NEW READ
NO OUTPUT WITH OLD LEASE
```

## Fase 2 — Erasure closure

Fuera de la transacción única:

- KeyProvider;
- Payload Vault;
- derived records;
- caches;
- indexes;
- telemetry targets.

Luego PurgeVerifier.

---

# 74. PURGE completion condition

Formalmente:

```text
PURGE_COMPLETE
iff
∀ target ∈ ManagedPersistenceRegistry:
    verify_absent(record_id) == true
```

Si existe un solo `false`:

```text
PURGE_COMPLETE = forbidden
```

---

# 75. Read path

## Operational Memory

```text
branch
 -> active records
 -> temporal validity
 -> state assembly
```

## Personal Memory

```text
candidate record
 -> status check
 -> temporal check
 -> Mount Policy
 -> scope check
 -> create AccessLease
 -> resolve payload
 -> context assembly
```

Sin lease:

```text
no decryption
```

---

# 76. Output path

Si una generación utilizó leases:

```text
generation_result
      |
      v
OutputGate
      |
      +-- every lease VALID? -> emit
      |
      +-- any revoked/expired? -> block
```

La respuesta bloqueada no se registra con contenido sensible en logs.

---

# 77. No raw exception logging

Toda excepción que atraviese una frontera sensible debe convertirse a:

```text
error_code
component
opaque IDs
```

Ejemplo permitido:

```text
PROHIBITED_CONTENT
category=credential
span_id=...
```

Prohibido:

```text
PROHIBITED_CONTENT: sk_live_ABC...
```

---

# 78. Reconstruction algorithm requirements

`StateReconstructor` consume Commit History.

Para Operational Memory:

- reproduce ADD;
- SUPERSEDE;
- RETRACT;
- conflict operations;
- links.

Para Personal Memory:

- puede reconstruir metadata y referencias mientras no estén purgadas;
- un Tombstone/PURGED debe impedir recuperar payload;
- jamás intenta “revivir” contenido desde Audit/Hash/Evidence.

---

# 79. Unknown preservation

Si no existe registro activo:

```text
UNKNOWN
```

No usar:

- modelo generativo;
- inference;
- nearest match;

para completar silenciosamente State.

---

# 80. Test fixture format

Cada test YAML tendrá como mínimo:

```yaml
id: T18
kind: golden

initial_state: ...
input: ...

injected_failures: ...

expected:
  security_outcome: ...
  state: ...
  error_code: ...
  expected_detection_layer: ...
```

Adversarial puede además incluir:

```yaml
forced_model_output: ...
forced_segmenter_output: ...
forced_auditor_output: ...
```

Esto permite probar el kernel aun cuando el LLM se comporte mal.

---

# 81. Traceability — Golden Set

| Test | Responsabilidad primaria | Capa esperada | Invariantes principales |
|---|---|---|---|
| T01 | Analyzer + Generator + Auditor | AUDITOR | I1, I7 |
| T02 | Analyzer/Auditor | MEMORY_ANALYZER / AUDITOR | I1, I9 |
| T03 | Analyzer/Auditor | MEMORY_ANALYZER / AUDITOR | I9 |
| T04 | Analyzer + Commit path | AUDITOR | I1, I7 |
| T05 | Analyzer + Policy | PERSISTENCE_POLICY / AUDITOR | I7 |
| T06 | Patch Validator + Commit | PATCH_VALIDATOR | I10, I11 |
| T07 | Patch Validator + Commit | PATCH_VALIDATOR | I4, I11 |
| T08 | Patch Validator | PATCH_VALIDATOR | I13 |
| T09 | Auditor + Conflict model | AUDITOR | I9, I11 |
| T10 | Conflict resolver + Commit | PATCH_VALIDATOR / AUDITOR | I10, I11 |
| T11 | Analyzer/Auditor | AUDITOR | I7, I9 |
| T12 | Evidence Resolver + Auditor | AUDITOR | I3, I7 |
| T12.b | Evidence Resolver | EVIDENCE_RESOLVER | I3 |
| T13 | State reader | COMMIT_VALIDATOR / state read | I9 |
| T14 | Branch State reader | MOUNT_POLICY / branch isolation | I5 |
| T15 | Branch manager | branch isolation | I5 |
| T16 | Patch Validator | PATCH_VALIDATOR | I5 |
| T17 | Patch Validator | PATCH_VALIDATOR | Core protection |
| T18 | Commit Validator | COMMIT_VALIDATOR | I12 |
| T19 | Commit Validator | AUDITOR | I1 |
| T20 | State Reconstructor | COMMIT_ENGINE | I8 |
| T21 | Patch Validator | PATCH_VALIDATOR | I11 |
| T22 | Patch Validator | PATCH_VALIDATOR | I11 |
| T23 | Evidence Resolver | EVIDENCE_RESOLVER | I3, I6 |
| T24 | Commit Validator | COMMIT_VALIDATOR | I2 |
| T25 | Commit Validator | COMMIT_VALIDATOR | I13 |
| T26 | Commit Validator | COMMIT_VALIDATOR | I1 |
| T27 | Policy + Session Store | PERSISTENCE_POLICY | I14, I16 |
| T28 | Session Store | SESSION_CONTEXT | I14 |
| T29 | Policy/Auditor | PERSISTENCE_POLICY | I15 |
| T30 | Session Store | SESSION_CONTEXT | I14, I21 |
| T31 | Temporal Resolver + Policy | PERSISTENCE_POLICY | I21, I35 |
| T32 | Policy/Auditor | PERSISTENCE_POLICY | I17 |
| T33 | Policy | PERSISTENCE_POLICY | I16 |
| T34 | Policy + minimization + Auditor | PERSISTENCE_POLICY / AUDITOR | I17, I19 |
| T35 | Minimization + Auditor | AUDITOR | I19 |
| T36 | Policy | PERSISTENCE_POLICY | I16 |
| T37 | Ingress Guard + Policy | INGRESS_GUARD | I18, I29 |
| T38 | Ingress Guard + Policy | INGRESS_GUARD | I18, I29 |
| T39 | Purge Coordinator | PURGE_ENGINE | I22, I37 |
| T40 | Mount/Read path | MOUNT_POLICY | I22, I38 |
| T41 | Reconstructor | PURGE_ENGINE | I8, I22, I34 |
| T42 | Purge schema/validator | PURGE_ENGINE | I24, I34 |
| T43 | Context Assembler + Mount Policy | MOUNT_POLICY | I20, I27 |
| T44 | Mount Policy | MOUNT_POLICY | I27 |
| T45 | Safety + Policy | SAFETY_HANDLER / PERSISTENCE_POLICY | I23 |
| T46 | Purge Coordinator + Registry | PURGE_ENGINE | I24, I34, I38 |
| T47 | Segmenter + Guard + Policy | INGRESS_GUARD / PERSISTENCE_POLICY | I25, I26, I29-I32 |
| T48 | Mount Policy | MOUNT_POLICY | I27, I28 |

---

# 82. Traceability — Adversarial Set

| Test | Responsabilidad primaria | Expected Detection Layer | Propiedad |
|---|---|---|---|
| RT-A01 | Analyzer + Auditor | AUDITOR | Attribution |
| RT-A02 | Analyzer + Auditor | AUDITOR | Quotation |
| RT-A03 | Analyzer + Auditor | AUDITOR | Modality |
| RT-A04 | Analyzer + Auditor | AUDITOR | Negation |
| RT-B01 | Analyzer + Policy | PERSISTENCE_POLICY | Non-persistence |
| RT-B02 | Analyzer + Policy | PERSISTENCE_POLICY | Clause precedence |
| RT-B03 | Session Store | PERSISTENCE_POLICY | Session-only |
| RT-B04 | Analyzer + Policy | PERSISTENCE_POLICY | Permission denial |
| RT-B05 | Policy | PERSISTENCE_POLICY | Explicit sensitive consent |
| RT-C01 | Segmenter + Policy | SEGMENTER / PERSISTENCE_POLICY | Mixed policy |
| RT-C02 | Guard + Sanitizer | INGRESS_GUARD | Embedded secret |
| RT-C03 | Guard + Patch Validator | INGRESS_GUARD / PATCH_VALIDATOR | Secret in key |
| RT-C04 | Guard + Patch Validator | INGRESS_GUARD / PATCH_VALIDATOR | Secret in metadata |
| RT-C05 | Sanitizer + Auditor | EVIDENCE_SANITIZER / AUDITOR | Minimization |
| RT-D01 | Restriction propagation | PERSISTENCE_POLICY | Summary laundering |
| RT-D02 | Auditor | AUDITOR | Derived diagnosis |
| RT-D03 | Auditor | AUDITOR | Invented preference |
| RT-D04 | Audit schema + Purge | AUDITOR / PURGE_ENGINE | Audit laundering |
| RT-D05 | Ingress + Telemetry schema | INGRESS_GUARD | Metrics laundering |
| RT-E01 | PurgeVerifier | PURGE_ENGINE | Search after purge |
| RT-E02 | Reconstructor | PURGE_ENGINE | Replay after purge |
| RT-E03 | Purge closure | PURGE_ENGINE | Explain after purge |
| RT-E04 | Crypto-erasure | PURGE_ENGINE | Hash confirmation |
| RT-E05 | Evidence Materializer | PERSISTENCE_POLICY | Re-disclosure |
| RT-F01 | Mount Policy | MOUNT_POLICY | Prompt escalation |
| RT-F02 | Mount Policy | MOUNT_POLICY | Self-authorization |
| RT-F03 | Mount Policy | MOUNT_POLICY | Indirect influence |
| RT-F04 | Branch/Mount Policy | MOUNT_POLICY | Cross-branch fishing |
| RT-F05 | Mount Policy | MOUNT_POLICY | Transform-after-access |
| RT-G01 | Temporal read filter | MOUNT_POLICY / state read | Expired resurrection |
| RT-G02 | Mount Policy | MOUNT_POLICY | Expired mount |
| RT-G03 | Temporal Resolver | PERSISTENCE_POLICY | Relative-time drift |
| RT-H01 | Commit Validator | COMMIT_VALIDATOR | Policy version binding |
| RT-H02 | Lease + Output Gate | OUTPUT_GATE | In-flight purge |
| RT-H03 | Purge Coordinator | PURGE_ENGINE | Partial purge |
| RT-I01 | Ingress Guard | INGRESS_GUARD | Secret misclassification |
| RT-I02 | Guard + Policy defense depth | INGRESS_GUARD / PERSISTENCE_POLICY | Sensitive misclassification |
| RT-I03 | Span propagation | INGRESS_GUARD | Segmentation failure |
| RT-I04 | Multi-scanner Guard | INGRESS_GUARD | Obfuscated secret |
| RT-I05 | Restriction propagation + Auditor | EVIDENCE_SANITIZER / AUDITOR | Derived secret |
| RT-I06 | Detection telemetry | expected layer varies | Policy bypass |

---

# 83. Critical invariant → schema mapping

| Invariant | Enforced by |
|---|---|
| I1 No unaudited writes | `commits.audit_id NOT NULL` + CommitValidator |
| I2 Exact Audit Binding | `patch_hash`, unique patch/audit relations |
| I3 Evidence Integrity | `patch_evidence`, `audit_evidence`, EvidenceResolver |
| I5 Branch Isolation | branch FKs + validators |
| I8 Reconstructability | commits + patch operations + tombstones |
| I12 Revision Consistency | `branches.current_revision`, `commits(branch,revision)` |
| I13 Idempotency | `commits.patch_id UNIQUE` |
| I18 Secret Non-Persistence | Guard + no PROHIBITED storage enum |
| I20 Scope Isolation | scope fields + MountPolicy |
| I22 Effective Purge | purge jobs + target verification |
| I24 Erasure Closure | PurgeTarget registry |
| I26 No Pre-Policy Durable Raw Input | no raw-input table |
| I27 Mount Authorization | mount policy + leases |
| I29 Independent Protection | RestrictionMap + Guard |
| I30 Restriction Monotonicity | policy merge rule |
| I31 Span Propagation | source spans |
| I32 Sanitized Evidence | EvidenceSanitizer |
| I34 Derived Erasure Closure | PurgeTarget registry + crypto erasure |
| I35 Absolute Temporal Validity | absolute `valid_until` |
| I36 Policy Binding | policy snapshot FK throughout path |
| I37 Immediate Purge Revocation | `PURGE_REVOKED` + lease revocation |
| I38 Verified Purge Completion | target result universal check |
| I39 Revocable Access | `access_leases` |
| I40 No Post-Revocation Output | OutputGate |
| I41 Detection Accountability | `detection_events` |

---

# 84. Data that may be persisted inline

Allowed examples:

```text
branch name
database = PostgreSQL
framework = FastAPI
status codes
policy versions
reason codes
timestamps
model IDs
random UUIDs
test IDs
non-sensitive global response preference
```

Only after classification/policy permits.

---

# 85. Data that must be Vault-backed

At minimum:

```text
all Personal Memory values
authorized sensitive payloads
authorized personal Evidence
derived personal values
```

This applies even when the Personal Memory is considered ordinary.

Reason:

```text
future PURGE must remain implementable
```

---

# 86. Data that must never become durable

```text
NEVER_DURABLE spans
PROHIBITED credentials
raw passwords
private keys
disallowed tokens
raw input before policy
unredacted sensitive error messages
model chain-of-thought
```

---

# 87. Query patterns

## Current operational state

```sql
SELECT *
FROM memory_records
WHERE domain = 'OPERATIONAL'
  AND branch_id = ?
  AND status = 'ACTIVE'
  AND (valid_until IS NULL OR valid_until > ?);
```

## Personal candidates for Mount Policy

Primero sólo metadata:

```sql
SELECT
    record_id,
    semantic_key,
    sensitivity,
    lifetime,
    valid_until,
    mount_policy_id,
    status
FROM memory_records
WHERE domain = 'PERSONAL'
  AND status = 'ACTIVE';
```

No descifrar payload antes de autorización.

---

# 88. No decrypt-before-authorize

Orden obligatorio:

```text
metadata lookup
   ↓
Mount Policy
   ↓
Access Lease
   ↓
KeyProvider
   ↓
decrypt payload
```

Prohibido:

```text
decrypt all personal memory
   ↓
let LLM decide relevance
```

---

# 89. Indexes mínimos

```sql
CREATE INDEX ix_memory_branch_status
ON memory_records(branch_id, status);

CREATE INDEX ix_memory_domain_status
ON memory_records(domain, status);

CREATE INDEX ix_memory_valid_until
ON memory_records(valid_until);

CREATE INDEX ix_evidence_scope_status
ON evidence(scope_type, branch_id, status);

CREATE INDEX ix_patch_branch_revision
ON patches(branch_id, base_revision);

CREATE INDEX ix_commits_branch_revision
ON commits(branch_id, revision);

CREATE INDEX ix_purge_record_status
ON purge_jobs(record_id, status);
```

---

# 90. Foreign-key deletion policy

No utilizar `ON DELETE CASCADE` para registros históricos principales si puede destruir trazabilidad accidentalmente.

Permitido en tablas puramente auxiliares como:

- `patch_evidence`;
- `audit_evidence`;
- `purge_target_results`.

Para memoria/commits:

> cambios semánticos se realizan mediante estados y operaciones explícitas, no mediante DELETE casual.

PURGE es una operación coordinada especial.

---

# 91. Database-level deletes

Uso directo de:

```sql
DELETE FROM memory_records
```

queda prohibido en lógica normal.

Sólo `PurgeCoordinator` puede realizar eliminaciones físicas que formen parte de Erasure Closure, y debe hacerlo a través de repositorios/targets registrados.

---

# 92. Repository interfaces

Interfaces mínimas:

```text
BranchRepository
CoreRepository
PolicyRepository
EvidenceRepository
PatchRepository
AuditRepository
CommitRepository
MemoryRepository
LeaseRepository
PurgeRepository
TelemetryRepository
PayloadVault
KeyProvider
```

Ninguna capa superior ejecuta SQL arbitrario.

---

# 93. Trusted component boundary

Componentes considerados trusted deterministic base:

```text
Restriction merger
PersistencePolicyEngine
EvidenceSanitizer
PatchValidator
EvidenceResolver
CommitValidator
CommitEngine
MountPolicyEngine
LeaseManager
OutputGate
PurgeCoordinator
PurgeVerifier
Repository adapters
```

Memory Analyzer, Segmenter, Generator y Auditor siguen siendo probabilísticos/no confiables.

---

# 94. Implementation gate

Antes de escribir componentes LLM deben existir y pasar:

1. Pydantic domain models.
2. SQLite migrations.
3. repository tests.
4. Policy Engine.
5. Patch Validator.
6. Commit Validator.
7. Commit Engine.
8. State reconstruction.
9. Mount Policy.
10. Lease Manager.
11. Purge state machine.
12. Output Gate.
13. deterministic fixtures.

---

# 95. Sprint A exacto

Primer código del proyecto:

```text
A1. enums + IDs + errors
A2. Pydantic models
A3. SQLite schema + migrations
A4. repositories
A5. canonical serializer
A6. PatchValidator
A7. PersistencePolicyEngine
A8. CommitValidator
A9. CommitEngine
A10. StateReconstructor
A11. MountPolicyEngine
A12. LeaseManager
A13. PurgeCoordinator skeleton
A14. OutputGate
A15. deterministic test harness
```

Todavía:

```text
NO real LLM
NO real DLP
NO web API
NO RAG
```

Mocks simulan Analyzer, Segmenter y Auditor.

---

# 96. Definition of Done de Data Model

Este documento puede considerarse listo para implementación cuando el equipo confirme:

```text
[ ] ningún Personal Memory plaintext puede entrar a SQLite
[ ] PROHIBITED no tiene representación durable válida
[ ] cada Commit referencia un Audit ACCEPT verificable
[ ] Patch/Audit/Commit comparten Policy Snapshot
[ ] revision es monotónica por Branch
[ ] un `patch_id` no puede committearse dos veces y un hash rechazado no bloquea futuras propuestas
[ ] Personal Memory requiere Mount Policy antes de decrypt
[ ] PURGE revoca leases antes de borrar físicamente
[ ] PURGE_COMPLETE requiere verify_absent en todos los targets
[ ] reconstrucción no revive payload purgado y conserva referencias opacas hacia payload tombstones
[ ] test telemetry no contiene raw sensitive data
[ ] los 90 tests tienen una capa/componente responsable
```

---

# 97. Riesgo técnico explícito: SQLite + filesystem

El principal riesgo técnico todavía no validado mediante código es la coordinación entre:

```text
SQLite transaction
```

y:

```text
Payload Vault filesystem
```

No existe una transacción ACID nativa común.

Por ello el MVP debe incluir pruebas de crash/recovery en puntos intermedios.

Esto es un **riesgo de implementación conocido**, no un cambio de Specification.

---

# 98. Riesgo técnico explícito: DLP incompleto

El Ingress Guard no garantiza encontrar todo secreto.

La implementación deberá medir:

- Secret Detection Recall;
- False Restriction Rate;
- bypass por ofuscación;
- bypass por derivación.

Esto es riesgo probabilístico residual aceptado por v0.3.0.

---

# 99. Siguiente artefacto

Después de aprobar este documento:

> **se abre formalmente el repositorio de código y comienza Sprint A — Deterministic Kernel.**

El primer objetivo ejecutable no es un chatbot.

Es:

```text
Patch
  ↓
Validate
  ↓
Audit fixture
  ↓
Commit
  ↓
State
```

con transacciones, versiones, aislamiento e invariantes verificables.

---

# 99A. Design Review Record — DR-01 a DR-05

## DR-01 — Generator-to-Vault Gap

**CONFIRMED**

Resolución:

```text
Generator → DraftPatch → DraftPatchSchemaValidator
→ PatchStager (RAM) → StagedPatch
```

El Generator nunca inventa `payload_id` ni emite directamente el CSP persistible.

## DR-02 — `patch_hash UNIQUE`

**CONFIRMED, con resolución modificada**

Se elimina `UNIQUE` de `patch_hash`.

No se utiliza tampoco un índice parcial unique por hash.

Razón:

> `patch_hash` es binding de una instancia auditada; `patch_id` es identidad e idempotencia.

`commits.patch_id UNIQUE` es la barrera autoritativa contra replay del mismo Patch.

## DR-03 — `payload_id` en Tombstone

**CONFIRMED**

El UUID permanece para preservar la cadena referencial.

La destrucción ocurre en la capacidad:

```text
key destroyed
ciphertext deleted
payload status DESTROYED
```

No mediante rotura de foreign keys.

## DR-04 — Operational Inline PURGE

**CONFIRMED**

En el MVP:

```text
PURGE_REQUEST → PERSONAL only
```

Operational Memory usa RETRACT/SUPERSEDE.

## DR-05 — Durable Pre-Audit Staging

**NEW FINDING DERIVED FROM DR-01**

No escribir ciphertext durable antes de Audit ACCEPT.

`PatchStager` opera enteramente en RAM.

`PayloadMaterializer` es el primer componente autorizado a crear staging durable, y sólo después de `Audit = ACCEPT`.

---

# 100. Estado

**Memory Agent — Data Model & Schemas v1.1**

**DRAFT FOR IMPLEMENTATION REVIEW**

Una vez revisado y aprobado:

```text
DESIGN GATE CLOSED
        ↓
IMPLEMENTATION START
```
