# Memory Agent — Technical Design v1.0

**Estado:** DRAFT FOR IMPLEMENTATION REVIEW  
**Specification:** Memory Agent Specification v0.3.0 — FROZEN  
**Objetivo:** Traducir las garantías normativas a componentes, interfaces, estructuras de datos y tecnologías implementables.

---

## 1. Prioridades del MVP

Orden:

1. corrección;
2. auditabilidad;
3. seguridad;
4. reproducibilidad;
5. portabilidad;
6. rendimiento.

No priorizar inicialmente:

- alta concurrencia;
- despliegue distribuido;
- GUI;
- escalabilidad extrema.

---

## 2. Stack base propuesto

```text
Python           3.12+
Pydantic         v2, strict mode
Persistence      SQLite
Sensitive data   Encrypted Personal Payload Vault
Cryptography     cryptography / AEAD
Tests            pytest
Test datasets    YAML
Serialization    JSON
LLM              provider-neutral adapter
DLP/PII          custom scanners + optional specialized detectors
```

---

## 3. Arquitectura de paquetes

```text
memory_agent/
|
+-- domain/
|   +-- models.py
|   +-- enums.py
|   +-- errors.py
|   +-- invariants.py
|
+-- ingress/
|   +-- buffer.py
|   +-- guard.py
|   +-- sanitizer.py
|   +-- scanners/
|       +-- regex.py
|       +-- credentials.py
|       +-- entropy.py
|       +-- pii.py
|
+-- session/
|   +-- store.py
|
+-- analyzer/
|   +-- service.py
|   +-- segmenter.py
|
+-- policy/
|   +-- engine.py
|   +-- loader.py
|   +-- mount.py
|
+-- evidence/
|   +-- materializer.py
|   +-- resolver.py
|
+-- memory/
|   +-- state.py
|   +-- patch.py
|   +-- patch_validator.py
|   +-- reconstruction.py
|
+-- audit/
|   +-- service.py
|
+-- commit/
|   +-- validator.py
|   +-- engine.py
|
+-- vault/
|   +-- payload_store.py
|   +-- crypto.py
|   +-- key_provider.py
|
+-- purge/
|   +-- coordinator.py
|   +-- verifier.py
|
+-- access/
|   +-- lease.py
|   +-- output_gate.py
|
+-- temporal/
|   +-- resolver.py
|
+-- providers/
|   +-- base.py
|   +-- openai_compatible.py
|   +-- mock.py
|
+-- telemetry/
|   +-- events.py
|
+-- repository/
    +-- sqlite.py
    +-- migrations/
```

---

## 4. `.agent-repo`

```text
.agent-repo/
|
+-- manifest.json
+-- memory.db
+-- policies/
|   +-- policy-001.yaml
|   +-- mount-policy-001.yaml
|
+-- vault/
|   +-- payloads/
|
+-- exports/
```

Las claves criptográficas no viven dentro de `.agent-repo`.

---

## 5. Pydantic como frontera

Todo output LLM o intercambio entre componentes críticos pasa por modelos tipados.

Política general:

```text
strict = true
extra = forbid
```

Flujo:

```text
LLM raw output
   -> JSON parser
   -> strict Pydantic validation
   -> typed object
```

Falla:

```text
INVALID_MODEL_OUTPUT
```

No continúa la transacción.

---

## 6. SQLite

SQLite será el kernel transaccional local del MVP.

Responsabilidades:

- branches;
- metadata;
- revisions;
- commits;
- audits;
- policies;
- conflicts;
- leases;
- purge jobs;
- telemetry estructural.

No es “la memoria semántica”.

### Journal mode inicial

```text
DELETE
```

No WAL en el primer MVP.

Motivos:

- single writer;
- menor superficie persistente;
- PURGE más controlable;
- menor complejidad de archivos auxiliares.

---

## 7. Regla de datos sensibles

> **Nunca almacenar plaintext sensible en SQLite.**

SQLite puede almacenar:

- IDs aleatorios;
- `payload_ref`;
- status;
- kind;
- scope;
- policy version;
- timestamps;
- relaciones.

El valor sensible vive en el Personal Payload Vault.

---

## 8. Tablas principales

```text
branches
branch_records
personal_records
operational_records
evidence
patches
patch_operations
audits
commits
policies
mount_policies
conflicts
access_leases
purge_jobs
detection_events
```

---

## 9. Identificadores

UUID4 o equivalente aleatorio para:

- branch;
- record;
- evidence;
- patch;
- audit;
- commit;
- payload;
- lease;
- purge.

Ningún ID se deriva del contenido.

---

## 10. Personal Payload Vault

Flujo:

```text
plaintext
   -> AEAD encryption
   -> ciphertext
   -> vault/payloads/<payload-id>
```

SQLite conserva sólo `payload_id`.

---

## 11. Criptografía

AEAD recomendado:

```text
AES-GCM
```

o equivalente seguro provisto por una biblioteca mantenida.

Cada payload utiliza:

- clave independiente;
- nonce apropiado;
- associated data estructural.

La primitive exacta se confirma en revisión criptográfica.

---

## 12. KeyProvider

Interfaz conceptual:

```python
class KeyProvider:
    create_key(record_id): ...
    get_key(key_handle): ...
    destroy_key(key_handle): ...
    exists(key_handle): ...
```

Implementaciones:

- InMemoryKeyProvider — tests;
- OSKeyringProvider — local;
- ExternalKMSProvider — producción.

---

## 13. Crypto-erasure

PURGE sensible:

```text
logical revoke
 -> revoke leases
 -> destroy key
 -> delete ciphertext
 -> erase derived artifacts
 -> verify closure
```

Una copia de ciphertext sin una clave administrada disponible no debe ser descifrable por Memory Agent.

---

## 14. Sensitive verification tags

No usar:

```text
SHA256(plaintext)
```

como identificador/verificador persistente de datos personales sensibles.

Si se necesita verificación:

```text
HMAC(record-specific-secret, plaintext)
```

y la capacidad de verificación debe destruirse con PURGE.

---

## 15. EphemeralIngressBuffer

El raw input vive en RAM.

Reglas:

- no persistence;
- no debug dump;
- no logging de payload;
- lifetime de turno/sesión;
- acceso limitado.

---

## 16. IngressContentGuard

Pipeline:

```text
Raw Input
 |
 +-- KnownSecretScanner
 +-- StructuredCredentialScanner
 +-- RegexRecognizers
 +-- EntropyScanner
 +-- PII/Sensitive Detector
 |
 v
RestrictionMap
```

### Hard Rules

Para formatos que podamos reconocer con suficiente certeza:

```text
NEVER_DURABLE
```

### Soft Signals

Para heurísticas:

```text
POTENTIALLY_SENSITIVE
```

No reemplazan al Analyzer.

---

## 17. RestrictionSpan

```text
span_id
start
end
category
restriction
detector_id
```

Offsets referidos al input efímero original.

---

## 18. Restriction propagation

Cada `MemoryCandidate` mantiene los spans de origen.

Un candidato que contiene un span `NEVER_DURABLE` no puede materializar ese span aunque el Analyzer lo clasifique como ordinario.

---

## 19. Evidence Sanitizer

Firma conceptual:

```python
sanitize(candidate, restriction_map) -> SanitizedCandidate
```

Invariante:

```text
SanitizedCandidate ∩ NEVER_DURABLE = empty
```

---

## 20. Memory Analyzer

Interfaz:

```python
analyze(ephemeral_text, session_context) -> AnalysisResult
```

Produce:

- semantic types;
- sensitivity estimate;
- persistence intent;
- temporal expressions;
- candidate boundaries;
- subject/modal information cuando corresponda.

No tiene autoridad.

---

## 21. Atomic Segmenter

Componente lógico independiente aunque inicialmente pueda compartir modelo con Analyzer.

Produce:

```text
MemoryCandidate[]
```

Cada candidato:

- source span;
- subject;
- semantic type;
- sensitivity;
- persistence intent;
- temporal scope.

---

## 22. PersistencePolicyEngine

100% determinístico.

Entrada:

```text
Candidate
RestrictionMap
PolicySnapshot
```

Salida:

```text
SESSION_ONLY
PROHIBITED
PERSIST
PERSIST_MINIMIZED
DEFER
PURGE_REQUEST
```

---

## 23. Policy files

Versionados en YAML.

```yaml
version: 1

rules:
  - when:
      restriction: NEVER_DURABLE
    result: PROHIBITED

  - when:
      sensitivity: sensitive
      persistence_intent: none
    result: SESSION_ONLY

  - when:
      sensitivity: sensitive
      persistence_intent: explicit
    result: PERSIST_MINIMIZED
```

Cada carga genera:

- policy version;
- snapshot ID;
- policy hash.

---

## 24. Evidence Materialization

Sólo después de:

```text
sanitization + policy permission
```

La Evidence puede contener:

- sanitized text;
- structured claim;
- payload ref;
- provenance.

No raw prohibited spans.

---

## 25. LLM Provider Abstraction

```python
class LLMProvider:
    def generate(messages, output_schema, model_config):
        ...
```

Debe permitir proveedores:

- OpenAI-compatible;
- Ollama;
- llama.cpp;
- mocks;
- otros.

Analyzer, Generator y Auditor pueden usar proveedores/modelos distintos.

---

## 26. Generator

Input:

- Core;
- Branch Contract;
- Current State;
- Session context autorizado;
- current sanitized/current input.

Output:

- response draft;
- optional CSP.

Nunca escribe memoria.

---

## 27. CognitiveStatePatch

Campos:

```text
patch_id
branch_id
base_revision
policy_version
evidence_refs
operations
```

Operaciones como modelos discriminados:

- AddOperation;
- SupersedeOperation;
- RetractOperation;
- LinkOperation;
- FlagConflictOperation;
- ResolveConflictOperation;
- PurgeRequestOperation.

---

## 28. Canonical Patch

Serialización determinística:

- UTF-8;
- keys ordenadas;
- sin extras;
- sin timestamps variables en el hash.

Luego:

```text
SHA-256(canonical_patch)
```

para exact Audit Binding.

---

## 29. Auditor

Input mínimo:

- Core snapshot;
- Policy snapshot ID;
- Branch Contract;
- State relevante;
- Evidence sanitizada autoritativa;
- CSP.

Output:

- ACCEPT;
- REJECT;
- DEFER;
- reason codes.

No persistir chain-of-thought.

---

## 30. Audit persistence

Persistir únicamente:

- decision;
- reason codes;
- checks;
- model ID;
- latency;
- patch hash;
- evidence refs;
- policy version.

No razonamiento libre que pueda reintroducir secretos.

---

## 31. Commit Validator

En una única transacción verifica:

- Audit ACCEPT;
- patch hash;
- branch;
- base revision;
- Core version;
- Policy version;
- Evidence bindings;
- precondiciones;
- idempotencia.

Falla:

```text
ROLLBACK
```

---

## 32. Commit Engine

Conceptualmente:

```text
BEGIN
  validate
  apply operations
  increment revision
  write commit
  materialize state
COMMIT
```

En error:

```text
ROLLBACK
```

MVP:

```text
single process writer
```

con optimistic concurrency mediante `base_revision`.

---

## 33. Session Store

Inicial:

```text
InMemorySessionStore
```

Contiene:

- session ID;
- TTL;
- conversational context;
- ephemeral sensitive state.

No sobrevive reinicio.

---

## 34. TemporalResolver

Primera versión soporta un vocabulario acotado:

- today;
- tomorrow;
- this week;
- for N days;
- explicit date.

Convierte a datetime absoluto UTC manteniendo timezone original.

Ambigüedad:

```text
DEFER
```

---

## 35. MountPolicyEngine

Entrada:

- record;
- requested scope;
- active branch;
- Policy snapshot;
- current time.

Valida:

- status;
- sensitivity;
- scope;
- expiration;
- purge;
- allowed scopes.

Salida final:

```text
ALLOW
DENY
```

---

## 36. AccessLease

Un mount sensible aprobado crea:

- lease ID;
- record ID;
- scope;
- issued at;
- expires at;
- policy version;
- status.

No contiene payload.

---

## 37. OutputGate

Una generación registra sus leases.

Antes de emitir:

```text
for lease in used_leases:
    assert lease.status == VALID
```

Si no:

```text
OUTPUT_BLOCKED
```

Regenerar sin memoria revocada cuando sea posible.

---

## 38. PurgeCoordinator

```text
PURGE_REQUESTED
 -> logical revocation
 -> revoke leases
 -> key destruction
 -> ciphertext deletion
 -> derived artifact erasure
 -> cache/index cleanup
 -> verify closure
 -> PURGE_COMPLETE
```

Si falla algo:

```text
PURGE_IN_PROGRESS
```

o:

```text
PURGE_FAILED
```

pero la memoria continúa lógicamente revocada.

---

## 39. PurgeVerifier

Enumera todos los backends declarados en un `ManagedPersistenceRegistry`.

Todo backend persistente debe implementar:

```python
class PurgeTarget:
    def purge(record_id): ...
    def verify_absent(record_id) -> bool: ...
```

Un backend no puede añadirse sin registrarse como PurgeTarget.

---

## 40. Telemetry

Registrar:

- run ID;
- threat type;
- expected detection layer;
- actual detection layer;
- security outcome;
- architectural outcome;
- policy bypass;
- latencies;
- token counts.

Nunca:

- raw secret;
- sensitive payload;
- raw conversation content sensible.

---

## 41. Error taxonomy

Inicial:

```text
INVALID_MODEL_OUTPUT
INVALID_PATCH
INVALID_EVIDENCE
CROSS_SCOPE_EVIDENCE
PRECONDITION_FAILED
STALE_STATE
POLICY_STALE
AUDIT_REJECTED
AUDIT_BINDING_FAILURE
MOUNT_DENIED
LEASE_REVOKED
OUTPUT_BLOCKED
PURGE_IN_PROGRESS
PURGE_FAILED
PROHIBITED_CONTENT
```

Nunca hacer echo del secreto dentro del error.

---

## 42. Tests como archivos

```text
tests/
|
+-- golden/
|   +-- T01.yaml
|   +-- ...
|
+-- adversarial/
|   +-- RT-A01.yaml
|   +-- ...
|
+-- unit/
+-- integration/
+-- fixtures/
```

Los datasets de test son independientes del código.

---

## 43. Plan de implementación

### Sprint A — Deterministic Kernel

Sin LLM:

- domain models;
- SQLite;
- Policy Engine;
- Patch Validator;
- Commit Validator;
- Commit Engine;
- Mount Policy;
- Lease Manager;
- Purge Coordinator;
- Output Gate.

Objetivo:

```text
100% deterministic tests
```

### Sprint B — Persistence Security

- Ephemeral Ingress;
- Ingress Guard;
- RestrictionMap;
- Evidence Sanitizer;
- Payload Vault;
- KeyProvider;
- Erasure Closure.

### Sprint C — Probabilistic Components

- Memory Analyzer;
- Atomic Segmenter;
- Generator;
- Auditor.

Primero con MockProvider, luego modelos reales.

### Sprint D — Experimental Harness

Ejecutar:

```text
49 Golden scenarios
+
41 Adversarial scenarios
```

Registrar modelos, prompts, policies, tokens, latencias y detection layer.

---

## 44. Definition of Done — Kernel

Debe mantenerse:

```text
0 unaudited writes
0 cross-branch writes
0 stale commits
0 audit substitution
0 duplicate state mutations
0 unauthorized mounts
0 post-revocation outputs
0 false PURGE_COMPLETE
```

---

## 45. Definition of Done — Security Boundary

En el corpus conocido:

```text
Hard-restricted durable leakage = 0
Purge residual = 0
Restriction downgrade = 0
Unauthorized sensitive mount = 0
```

No equivale a detección universal de secretos desconocidos.

---

## 46. Métricas probabilísticas

- Candidate Accuracy
- Segmentation Accuracy
- Persistence Precision
- Persistence Recall
- Audit Precision
- Audit Recall
- Diagnostic Promotion Rate
- Policy Bypass Rate
- Secret Detection Recall
- False Restriction Rate

---

## 47. API inicial

MVP:

```text
Python library + CLI
```

Comandos conceptuales:

```text
agent-repo init
branch create
branch activate
chat
memory list
memory inspect
memory history
memory forget
policy show
test golden
test adversarial
```

No FastAPI hasta validar el kernel.

---

## 48. RAG

No Vector DB en Technical Design v1.0.

Motivo:

Validar primero el kernel versionado sin retrieval como variable extra.

RAG será baseline experimental posterior.

---

## 49. Frameworks de agentes

No usar LangChain/LangGraph/CrewAI/AutoGen como núcleo.

Memory Agent mantiene interfaces propias.

Adapters podrán agregarse después.

---

## 50. Separación física central

```text
1. SQLITE
   metadata + transactional state

2. ENCRYPTED VAULT
   sensitive payloads

3. EXTERNAL KEY PROVIDER
   decryption capability
```

Esto permite que copiar `.agent-repo` no otorgue por sí solo acceso a todo Personal Memory sensible.

---

## 51. Resultado esperado del MVP

El MVP debe ser una máquina experimental capaz de observar:

```text
Input
 -> classification
 -> policy
 -> proposed mutation
 -> audit
 -> transaction
 -> versioned state
```

y responder:

- qué quiso recordar;
- por qué;
- qué Evidence lo soportaba;
- qué Policy lo autorizó;
- qué barrera lo bloqueó;
- qué modelo participó;
- qué cambió;
- qué versión quedó vigente;
- si hubo bypass arquitectónico.

---

## 52. Estado

> **Memory Agent Technical Design v1.0 — DRAFT FOR IMPLEMENTATION REVIEW**

El siguiente documento técnico recomendado es:

**Data Model & Schemas v1.0**

con:

- modelos Pydantic completos;
- schema SQLite;
- foreign keys;
- constraints;
- índices;
- estados y enums;
- mapeo test -> componente.
