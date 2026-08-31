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
actual (Coder 2, post P0/P1 + C2):

| # | Ataque | SQLite rechaza? | Estado |
|---|--------|-----------------|--------|
| 1 | `PatchStatus = GARBAGE` | SÍ (CHECK enum) | PASS |
| 2 | `AuditDecision = MAYBE` | SÍ (CHECK enum) | PASS |
| 3 | `PayloadStatus = WHATEVER` | SÍ (CHECK enum) | PASS |
| 4 | `LeaseStatus = WHATEVER` | SÍ (CHECK enum) | PASS |
| 5 | Personal Memory + INLINE | SÍ (CHECK PERSONAL→VAULT_REF) | PASS |
| 6 | Personal Memory non-VAULT | SÍ (CHECK) | PASS |
| 7 | ACTIVE payload sin key_handle | SÍ (CHECK lifecycle) | PASS |
| 8 | DESTROYED payload con key_handle | SÍ (CHECK lifecycle) | PASS |
| 9 | Dos ACTIVE operational mismo (branch, key) | SÍ (UNIQUE índice parcial) | PASS |
| 10 | Mismo (branch, revision) dos commits | SÍ (UNIQUE) | PASS |
| 11 | (C3-02) Patch A hash X AUDIT_REJECTED + Patch B hash X PROPOSED | coexisten | PASS |
| 12 | (C3-02) mismo patch_id commiteado 2 veces | SÍ (commits.patch_id UNIQUE) | PASS |

**12/12 PASS.** La capa SQLite es estricta y hermética frente a estados
estructualmente inválidos (enum CHECK + storage CHECK + UNIQUE). Sin gaps.

## 2. C3-03 — Pydantic ↔ SQLite parity (`tests/unit/schema_contract/test_parity.py`)

Driveo la MISMíSIMA forma a través de Pydantic y de SQLite y exijo que ambos
coincidan (ambos REJECT o ambos ACCEPT).

| Concepto | Pydantic | SQLite | v1.1 | Result |
|----------|----------|--------|------|--------|
| Personal + INLINE | REJECT | REJECT | required | PASS |
| Personal + VAULT (válido) | ACCEPT | ACCEPT | required | PASS |
| Payload DESTROYED con keys | REJECT | REJECT | required | PASS |
| Payload ACTIVE sin keys | REJECT | REJECT | required | PASS |
| Evidence BRANCH sin branch_id | REJECT | REJECT | required | PASS |
| Evidence PROHIBITED | REJECT | REJECT | impossible | PASS |
| **MemoryRecord OPERACIONAL+INLINE sin inline_value** | **ACCEPT** | **REJECT** | **required** | **MISMATCH** |

### Finding → DESIGN / C1-04 gap (cross-review a Coder 1)

**`MemoryRecord._memory_storage` era permissivo**: solo validaba PERSONAL→VAULT_REF
y PROHIBITED. No validaba la forma genérica de storage (INLINE requiere
`inline_value`; VAULT requiere `payload_ref`; NONE requiere ambos null) para
cualquier dominio. SQLite sí la validaba.

- Resultado detectado: **Pydantic ACCEPT / SQLite REJECT**
- Test falsable: `test_parity_memrec_inline_requires_inline_value`
- **Resolución:** Coder 1 cerró el gap en `MemoryRecord._memory_storage`
  (C1-04). El test pasó a verde. **Parity restaurada — Pydantic == SQLite == Spec.**

## 3. C3-04 — Harness status

El reporte de harness ahora distingue el resultado del Reference Kernel:
`HARNESS_VALIDATED (reference kernel): N` — **no** se reporta como Golden/Adversarial
PASS definitivo. Expected outcomes intactos. La falsabilidad real llega en OLA 2
al sustituir el reference kernel por los componentes reales.

---

## Métricas C3

- Tests schema_contract (ataques SQL + parity): **19 pass** (el único fail por el
  gap Pydantic pasó a verde tras el fix de Coder 1)
- Suite completa del repo: **72 passed, 3 skipped, 0 failed**
- FAIL = 0. Pydantic y SQLite ahora describen el mismo sistema en la frontera
  testeable.

## Open items

- **P2:** ADR-004 (T20 COMMIT_ENGINE vs enum) — siguera escalado a Spec Owner.
