# Coder 3 — Verification & Test Harness | OLA 1 Correction (C3)
## Direct SQL schema attacks + Pydantic ↔ SQLite parity

Rama: `feature/sprint-a-verification`. Se ataca el storage directamente, sin
repositories, para probar que la capa SQLite **por sí sola** rechaza estados
estructuralmente inválidos, y se compara contra la frontera Pydantic.

**Regla del supervisor aplicada:** se prefiere *test fails because the
architecture is strict* antes que *test passes because the implementation is
permissive*.

---

## 1. C3-01 — Schema Contract Tests (`tests/unit/schema_contract/`)

Ataques SQL directos a invariantes. Resultado contra el `0001_initial.sql`
actual (Coder 2, post P0/P1 + C2), **rehechos bajo P0-03** (ver §0):

| # | Ataque | SQLite rechaza? | Control + | Estado |
|---|--------|-----------------|-----------|--------|
| 1 | `PatchStatus = GARBAGE` | SÍ (CHECK enum) | PROPOSED ACCEPT | PASS |
| 2 | `AuditDecision = MAYBE` | SÍ (CHECK enum) | ACCEPT ACCEPT | PASS |
| 3 | `PayloadStatus = WHATEVER` | SÍ (CHECK enum) | ACTIVE ACCEPT | PASS |
| 4 | `LeaseStatus = WHATEVER` | SÍ (CHECK enum) | VALID ACCEPT | PASS |
| 5 | Personal Memory + INLINE | SÍ (CHECK PERSONAL→VAULT_REF) | VAULT ACCEPT | PASS |
| 6 | Personal Memory non-VAULT | SÍ (CHECK) | — | PASS |
| 7 | OPERACIONAL+INLINE sin inline_value | SÍ (storage CHECK) | con valor ACCEPT | PASS |
| 8 | ACTIVE payload sin key_handle | SÍ (CHECK lifecycle) | con keys ACCEPT | PASS |
| 9 | DESTROYED payload con key_handle | SÍ (CHECK lifecycle) | keys nulos ACCEPT | PASS |
| 10 | Dos ACTIVE operational mismo (branch, key) | SÍ (UNIQUE índice parcial) | key distinto ACCEPT | PASS |
| 11 | Mismo (branch, revision) dos commits | SÍ (UNIQUE) | rev nueva ACCEPT | PASS |
| 12 | (C3-02) Patch A hash X AUDIT_REJECTED + Patch B hash X PROPOSED | coexisten | — | PASS |
| 13 | (C3-02) mismo patch_id commiteado 2 veces | SÍ (commits.patch_id UNIQUE) | patch nuevo ACCEPT | PASS |

**13 ataques; todos con control positivo emparejado. SQLite es estricto y hermético.**

## 2. C3-03 — Pydantic ↔ SQLite parity (`tests/unit/schema_contract/test_parity.py`)

**Rehecho bajo P0-03**: se ascendió de strings a **instancias reales `uuid.UUID`**
en los campos UUID bajo `strict=True`, se fijaron FKs preexistentes, y **cada
negativo tiene su control positivo emparejado** (fixture válida + valor inválido
→ REJECT; fixture válida + valor válido → ACCEPT) en AMBOS lados.

| Concepto | Pydantic | SQLite | v1.1 | Result |
|----------|----------|--------|------|--------|
| Personal + INLINE | REJECT | REJECT | required | PASS |
| Personal + VAULT (válido, control +) | ACCEPT | ACCEPT | required | PASS |
| OPERACIONAL+INLINE sin inline_value | REJECT | REJECT | required | PASS |
| OPERACIONAL+INLINE con valor (control +) | ACCEPT | ACCEPT | required | PASS |
| Payload DESTROYED con keys | REJECT | REJECT | required | PASS |
| Payload DESTROYED keys nulos (control +) | ACCEPT | ACCEPT | required | PASS |
| Payload ACTIVE sin keys | REJECT | REJECT | required | PASS |
| Payload ACTIVE con keys (control +) | ACCEPT | ACCEPT | required | PASS |
| Evidence PROHIBITED | REJECT | REJECT | impossible | PASS |
| Evidence ORDINARY (control +) | ACCEPT | ACCEPT | impossible | PASS |
| **Evidence BRANCH sin branch_id** | **ACCEPT → REJECT** tras C1-05 | **REJECT** | **required** | **FIXED (PASS)** |
| Evidence BRANCH con branch_id (control +) | ACCEPT | ACCEPT | required | PASS |

### Finding → C1-05 gap (cross-review a Coder 1)

**`EvidenceRecord._not_prohibited` era permissivo**: solo validaba
`sensitivity != PROHIBITED`. No validaba `scope_type == BRANCH → branch_id != None`
(C1-05). SQLite sí lo valida por CHECK.

- Resultado detectado: **Pydantic ACCEPT / SQLite REJECT** (parity break genuino,
  expuesto al rehacer la suite sin falsos positivos de tipo)
- Test falsable: `test_parity_evidence_branch_requires_branch_id` — ROJO inicialmente
- **Resolución:** Coder 1 cerró el gap en `EvidenceRecord` (C1-05, validator
  `branch evidence requires branch_id`). Re-ejecuté y el test pasó a verde.
  **Parity restaurada — Pydantic == SQLite == Spec.**

### C1-04 (resuelto previamente)

**`MemoryRecord._memory_storage`** fue permissivo (credntia: no validaba la forma
genérica INLINE/VAULT/NONE para cualquier dominio). Coder 1 lo cerró (C1-04) y el
test `test_parity_memrec_inline_requires_inline_value` pasó a verde — ahora
cubierto por `test_parity_operational_inline_requires_inline_value`.

## 3. C3-04 — Harness status

El reporte de harness ahora distingue el resultado del Reference Kernel:
`HARNESS_VALIDATED (reference kernel): N` — **no** se reporta como Golden/Adversarial
PASS definitivo. Expected outcomes intactos. La falsabilidad real llega en OLA 2
al sustituir el reference kernel por los componentes reales.

---

## Métricas C3 (post P0-03)

- Tests schema_contract (ataques SQL + parity): **19 passed / 0 failed**
  (tras Coder 1 cerrar C1-05, el parity break de EvidenceRecord pasó a verde)
- Suite completa del repo: **72 passed / 3 skipped / 0 failed**
- **FAIL = 0.** Pydantic y SQLite describen el mismo sistema en la frontera testeable.

## Open items

- **P2:** ADR-004 (T20 COMMIT_ENGINE vs enum) — sigue escalado a Spec Owner.
