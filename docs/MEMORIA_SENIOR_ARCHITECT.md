# Memoria Técnica y Arquitectónica — Senior Architect
**Proyecto:** Memory Agent  
**Rol:** Senior Architect — Governance, Contract Parity & Integrity Owner  
**Autor:** Antigravity (Senior Architect)  
**Fecha:** 2026-08-31 / 2026-09-01  
**Baseline Autoritativa:**
1. `Memory Agent Specification v0.3.0 — FROZEN`
2. `06_Memory_Agent_Data_Model_and_Schemas_v1.1_DRAFT.md`
3. `05_Memory_Agent_Technical_Design_v1.0_DRAFT.md`
4. Golden Set (49 escenarios) & Adversarial Set (41 ataques)

---

## 1. Misión y Principio Rector

La función del **Senior Architect** en este proyecto es garantizar que **el código nunca modifique implícitamente la arquitectura**. Si una necesidad de implementación exige una regla ausente en la especificación congelada, esta debe formalizarse como `DESIGN_GAP` y no como una concesión en el código.

El principio fundacional demostrado es:
- **Sprint A — OLA 1:** *Invalid state => cannot be represented*.
- **Sprint A — OLA 2A:** *Valid structures + invalid transaction => cannot mutate State*.

---

## 2. Historial de Intervenciones y Bloqueos Arquitectónicos

### 2.1. Bloqueo Inicial de OLA 1 (Reviews #1 y #2)
Durante la fase inicial de OLA 1, se detectaron discrepancias graves entre el Data Model v1.1 y la implementación en Python/SQLite:
1. **Agujero en la frontera de tipado (`P0-01`):** `DraftPatch` utilizaba `operations: tuple[dict[str, Any], ...]`, permitiendo la inyección de cargas no validadas desde el LLM.
2. **Violación de Vault-Only Universal (`P0-02`):** `MemoryRecord` y `EvidenceRecord` permitían almacenar datos sensibles o de dominio personal inline si no se disparaban ciertos checks.
3. **Ghost Audits (`P0-03` / `TP-05`):** La tabla `commits` no tenía una Foreign Key real hacia `audits(id)`, posibilitando commits huérfanos o con auditorías falsas.
4. **Estados parciales en Payloads (`P1-01`):** La máquina de estados de `PayloadObject` permitía estados híbridos donde existían claves criptográficas sin ubicación de cifrado o viceversa.
5. **Falsos positivos en pruebas de paridad:** Pruebas negativas en SQLite fallaban por colisiones accidentales de `UNIQUE` o falta de dependencias base en lugar de fallar por la restricción (`CHECK`) testeada.

**Acción del Arquitecto:** Se decretó **SPRINT A — OLA 1 BLOCKED**, deteniendo el inicio de OLA 2 y emitiendo directivas de corrección obligatorias a Coder 1 (Domain), Coder 2 (Persistence) y Coder 3 (Verification).

---

## 3. Decisiones Arquitectónicas Clave (ADRs Gobernados)

| Identificador | Decisión / Invariante | Solución Implementada |
| :--- | :--- | :--- |
| **ADR-006** | **Core Snapshot Retrieval** | Definición de `CoreSnapshot(PersistentModel)` y firma inmutable `CoreRepository.get_snapshot(core_version: int)`. |
| **ADR-008** | **DraftPatch Discriminated Union** | Creación de 7 modelos tipados (`DraftAddOperation`, `DraftSupersedeOperation`, etc.) discriminados estrictamente por `op`, con `proposed_value: JsonValue` en memoria. |
| **ADR-011** | **Nominal Recursive JsonValue** | Definición `JsonValue = TypeAliasType(...)` erradicando completamente el uso de `Any` y `dict[str, Any]` en el dominio. |
| **Data Model §17, §24** | **Vault-Only Universal** | Invariante estricto: `sensitivity == SENSITIVE` o `domain == PERSONAL` => `storage_class == VAULT_REF`, `payload_ref is not None`, `inline_value is None`. |
| **Data Model §26** | **Prohibición de `PROHIBITED`** | Validación universal: `PROHIBITED` es rechazado en todas las tablas durables (`memory_records`, `evidence`, `payload_objects`, `patch_operations`). |
| **Data Model §27** | **Exclusión de `SESSION` en Persistencia** | `domain` y `lifetime` restringidos a tipos durables (`OPERATIONAL`/`PERSONAL`, `TEMPORARY`/`DURABLE`), excluyendo `SESSION`. |
| **Principio Rector** | **Fix the Fixture, Never Weaken the Schema** | Ante fallos en pruebas de constraints, se adaptaron las fixtures y generadores de datos sin debilitar los `CHECK` ni las `FOREIGN KEY` de SQLite. |

---

## 4. Metodología de Triple Paridad y Certificación

Para certificar la frontera entre capas, se estableció el marco formal de **Triple Paridad**:
$$\text{Specification Predicate} \equiv \text{Pydantic Model Validation} \equiv \text{SQLite DDL Constraints} \equiv \text{Observed Test Behavior}$$

### Clasificación de Casos:
- **Caso A (Pydantic ACCEPT / SQLite REJECT):** Brecha donde el dominio permite algo que la DB rechaza => **0 casos**.
- **Caso B (Pydantic REJECT / SQLite ACCEPT):** Brecha donde la DB permite algo que el dominio prohíbe => **0 casos**.
- **Caso C (Pydantic ACCEPT / SQLite ACCEPT / Spec FORBIDS):** Falso positivo donde ambas capas permiten lo prohibido => **0 casos**.

### Batería TP-01 a TP-18:
Se construyeron 18 casos de prueba con **controles negativos y positivos emparejados**, aislando de forma unívoca la causa del rechazo:
- `TP-01..04`: Reglas de memoria personal, payloads destruidos, aislamiento de scope y no-repetición.
- `TP-05`: Eliminación de Ghost Audits (`commits.audit_id REFERENCES audits(id)`).
- `TP-06`: Positividad estricta de revisión (`commits.revision > 0`).
- `TP-07`: Exactitud de tipos de operación de patch (`op_type NOT NULL`).
- `TP-08`: Restricción de storage class en evidencia (prohibición de `NONE`).
- `TP-09`: Sanitización y validación JSON de categorías eliminadas (`removed_categories_json`).
- `TP-10`: Propósitos cerrados de payload (`EVIDENCE`, `MEMORY_VALUE`, `PATCH_VALUE`).
- `TP-11`: Rechazo de `SESSION` como dominio o ciclo de vida durable.
- `TP-12`: Linaje relacional de supersesión (`supersedes_record_id REFERENCES memory_records(id)`).
- `TP-13`: Rechazo de payloads prohibidos para evidencia.
- `TP-14`: Rechazo de sensibilidad prohibida en `patch_operations`.
- `TP-15`: Formas válidas e inválidas de `value_storage_class` en operaciones.
- `TP-16`: Estados válidos de rama (`ACTIVE`/`ARCHIVED`) y `current_revision >= 0`.
- `TP-17`: Modos de `mount_policies` y JSON válido en `allowed_scopes_json`.
- `TP-18`: Esquema íntegro y paridad de tabla `conflicts`.

**Resultado de la Suite:** **130 passed, 3 skipped, 0 failed** en 0.80s.

---

## 5. Lanzamiento y Blueprint de Sprint A — OLA 2A (Mutation Kernel)

Tras el cierre y certificación formal de OLA 1, el Senior Architect diseñó y publicó los contratos normativos para OLA 2A:

### 5.1. Contratos de Interfaz Definidos:
1. **`PatchValidator` (Coder 1)**:
   - Validación pre-commit de `CognitiveStatePatch` contra el estado activo de la rama.
   - Precondiciones semánticas para `ADD`, `SUPERSEDE`, `RETRACT`, `LINK`, `FLAG_CONFLICT`, `RESOLVE_CONFLICT`, `PURGE_REQUEST`.
   - Invariantes de contención: `0 cross-branch mutations`, `0 Core writes`.
2. **`PersistencePolicyEngine` (Coder 1)**:
   - Evaluación 100% determinista. Precedencia inviolable: $\text{NEVER\_DURABLE} \implies \text{PROHIBITED}$.
3. **`CommitValidator` (Coder 2)**:
   - Relectura inmediata de estado autoritativo antes del commit.
   - Protección contra TOCTOU:
     - `STALE_STATE`: Si la revisión de la rama avanzó mientras se auditaba.
     - `POLICY_STALE`: Si la política activa cambió mientras se auditaba.
     - `AUDIT_BINDING_FAILURE`: Si el hash o los IDs del patch difieren de la auditoría aceptada.
     - `ALREADY_COMMITTED`: Idempotencia estricta sin mutación redundante de estado.
4. **`CommitEngine` (Coder 2)**:
   - Transacción atómica SQLite con `BEGIN IMMEDIATE;` y `ROLLBACK` total ante fallos.
   - Escritura de `CommitRecord`, avance de `current_revision` y materialización de `memory_records`.
5. **`StateReconstructor` (Coder 2)**:
   - Reconstrucción determinista del estado activo exclusivamente desde la historia de operaciones (`patch_operations` y `commits`).
   - Resolución del caso obligatorio T20: `database: SQLite -> backend: FastAPI -> database superseded: PostgreSQL -> offline: true`.

---

## 6. Estado Actual del Repositorio y Próximos Pasos

- **Rama Activa de Desarrollo:** `feature/ola2-commit-state` (sincronizada y subida a `origin`).
- **Integración de Coder 3:** Espera de la consolidación de `PatchValidator` y `PersistencePolicyEngine` de Coder 1 para desplegar el `ProductionKernel` adapter sobre los fixtures `T16..T26` y `RT-H01`.
- **Métricas:** 130 tests en verde, 0 P0s abiertos, 0 P1s abiertos, 0 falsos positivos.

---
*Documento registrado y firmado en el repositorio por Senior Architect.*
