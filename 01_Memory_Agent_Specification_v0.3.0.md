# Memory Agent Specification v0.3.0

**Estado:** FROZEN FOR TECHNICAL DESIGN  
**Versión:** 0.3.0  
**Hereda:** Memory Agent Specification v0.2.0  
**Origen:** Golden Set v0.2.0, Adversarial Qualification Set v0.2.0, Targeted Baseline Retest y Adversarial Delta Report.

---

## 1. Propósito

Memory Agent es una arquitectura de memoria persistente para agentes LLM orientada a conversaciones y trabajos de larga duración.

Su objetivo no es que el agente “recuerde todo”, sino que pueda:

- mantener separados proyectos y contextos;
- representar el estado vigente de un trabajo;
- conservar cómo evolucionó ese estado;
- distinguir contexto de sesión de memoria persistente;
- gobernar qué información puede persistir;
- proteger información personal y sensible;
- auditar cambios de memoria antes de incorporarlos;
- controlar dónde puede volver a utilizarse una memoria;
- revocar acceso;
- eliminar información personal de manera verificable dentro del perímetro administrado;
- registrar en qué capa fue detenida una amenaza.

Principio base:

> **The conversation is evidence, not memory.**

Y, para conversaciones personales:

> **Conversation state is not persistent memory.**

---

## 2. Dos niveles de decisión

### Nivel 1 — Deterministic Memory Kernel

Resuelve todo aquello que el software puede determinar exactamente:

- existencia de registros;
- estado activo;
- revisiones;
- scopes;
- versiones de políticas;
- validez de referencias;
- precondiciones de operaciones;
- idempotencia;
- autorización de montaje;
- estado de PURGE;
- validez de leases;
- binding entre Patch, Audit, Evidence y Policy.

Este nivel debe ser determinístico.

### Nivel 2 — Semantic Judgment

Resuelve aquello que requiere interpretación:

- decisión vs posibilidad;
- preferencia;
- atribución;
- contradicción semántica;
- intención de persistencia;
- significado de evidencia;
- clasificación de sensibilidad;
- segmentación de mensajes mixtos.

Este nivel es probabilístico y debe medirse.

Principio rector:

> **Never ask an LLM to validate something that can be validated deterministically.**

Y:

> **The LLM proposes and interprets; the kernel verifies and executes.**

---

## 3. Principio introducido en v0.3.0

Una decisión determinística no constituye una garantía fuerte si depende exclusivamente de una premisa probabilística no verificada.

Formalmente:

```text
DeterministicPolicy(ProbabilisticClassification(x))
```

no implica:

```text
DeterministicSafety(x)
```

Por ello:

> **No single probabilistic classification may be the sole barrier between prohibited content and durable storage.**

---

## 4. Dominios de memoria

### 4.1 Session Memory

Información efímera necesaria para mantener coherencia en la interacción actual.

Ejemplos:

- “Hoy estoy triste.”
- “Acabo de discutir con mi hermano.”
- “Estoy ansioso por el examen de mañana.”

Propiedades:

- no requiere Commit;
- no forma parte de Personal Memory por defecto;
- tiene TTL o vida de sesión;
- no debe convertirse automáticamente en identidad o diagnóstico;
- puede utilizarse para responder durante la sesión.

### 4.2 Personal Memory

Información sobre el usuario cuya persistencia futura está permitida.

Ejemplos:

- preferencias explícitas;
- instrucciones de apoyo autorizadas;
- información personal explícitamente solicitada para recordar.

Está gobernada por:

- sensibilidad;
- finalidad;
- intención de persistencia;
- duración;
- scope;
- minimización;
- Mount Policy;
- PURGE.

### 4.3 Operational Memory

Estado versionado de proyectos, decisiones, restricciones y configuraciones.

Ejemplos:

```text
database = PostgreSQL
framework = FastAPI
deployment = Kubernetes
```

Conserva historial fuerte y trazabilidad salvo que una política de privacidad aplicable ordene PURGE de payload personal.

---

## 5. Arquitectura general

```text
                         USER INPUT
                             |
                             v
                    EPHEMERAL INGRESS
                             |
                             v
                +------------------------+
                | INGRESS CONTENT GUARD  |
                | independent protection |
                +-----------+------------+
                            |
                     restriction map
                            |
            +---------------+-----------------+
            |               |                 |
            v               v                 v
         SAFETY       MEMORY ANALYZER     RESPONSE PATH
                            |
                            v
                    ATOMIC SEGMENTER
                            |
                            v
                   PERSISTENCE POLICY
                            |
               +------------+-------------+
               |            |             |
               v            v             v
          SESSION_ONLY   PROHIBITED    PERSISTABLE
               |            |             |
               |            v             v
               |           DROP     EVIDENCE SANITIZER
               |                          |
               |                          v
               |                 EVIDENCE MATERIALIZER
               |                          |
               |                          v
               |                       GENERATOR
               |                          |
               |                          v
               |                         CSP
               |                          |
               |                  PATCH VALIDATOR
               |                          |
               |                  EVIDENCE RESOLVER
               |                          |
               |                       AUDITOR
               |                          |
               |                  COMMIT VALIDATOR
               |                          |
               |                    COMMIT ENGINE
               |                          |
               +--------------------------v
                                        STATE
```

Uso posterior de Personal Memory sensible:

```text
Memory requested
      |
      v
Mount Policy
      |
      v
scope / policy / temporal / purge checks
      |
      v
Access Lease
      |
      v
Context Assembly
      |
      v
Generation
      |
      v
Output Gate
```

---

## 6. Fronteras de confianza

### Generator

**UNTRUSTED PROPOSER**

Puede:

- interpretar;
- responder;
- proponer CSP;
- señalar referencias.

No puede:

- escribir State;
- certificar Evidence;
- modificar Core;
- aceptar su Patch;
- ejecutar Commit.

### Auditor

**UNTRUSTED SEMANTIC JUDGE**

Puede:

- evaluar intención;
- evaluar evidencia;
- aceptar, rechazar o diferir.

No puede:

- persistir;
- crear Evidence autoritativa;
- corregir silenciosamente el Patch;
- ejecutar Commit.

### Kernel determinístico

Incluye:

- Ingress enforcement;
- Persistence Policy;
- Evidence Sanitizer;
- Patch Validator;
- Evidence Resolver;
- Commit Validator;
- Commit Engine;
- Mount Policy;
- Lease Manager;
- Purge Coordinator;
- Output Gate;
- State reconstruction.

---

## 7. Ephemeral Ingress

El input crudo entra primero en memoria efímera.

Propiedades:

- no pertenece a `.agent-repo`;
- no se escribe automáticamente en disco;
- no genera logging durable del payload;
- puede alimentar Safety, respuesta, análisis y segmentación;
- desaparece según el ciclo de vida de sesión/turno.

Principio:

> **Raw input is not durable evidence by default.**

---

## 8. Independent Ingress Content Guard — R-0301

Antes de que una clasificación probabilística pueda autorizar persistencia, existe una barrera independiente.

Puede combinar:

- reglas de formatos conocidos;
- parsers de credenciales;
- regex;
- detectores de alta entropía;
- detectores especializados de PII;
- recognizers configurables.

No se afirma que pueda detectar todo secreto arbitrario.

### 8.1 Hard Restriction

Resultado:

```text
NEVER_DURABLE
```

Ejemplos:

- private keys reconocibles;
- tokens con formato conocido;
- credenciales reconocidas por parser.

### 8.2 Soft Signal

Resultado:

```text
POTENTIALLY_SENSITIVE
```

Ejemplos:

- alta entropía;
- PII heurística;
- patrones desconocidos.

---

## 9. Restriction Map

El Guard produce restricciones asociadas a spans del input efímero.

```yaml
restriction_map:
  - span_id: span-001
    category: credential
    restriction: NEVER_DURABLE
    detector:
      type: hard_rule
      rule_id: stripe-secret-pattern
```

La restricción no necesita persistir el valor detectado.

---

## 10. Restriction Monotonicity

> **Un componente posterior puede aumentar una restricción, pero nunca disminuir una Hard Restriction previa.**

Si:

```text
Ingress Guard -> NEVER_DURABLE
Memory Analyzer -> ordinary_information
```

el resultado efectivo sigue siendo:

```text
NEVER_DURABLE
```

---

## 11. Atomic Memory Segmentation

Un turno puede contener unidades con políticas diferentes.

Ejemplo:

> “Usaremos Stripe. Mi clave es sk_live_X. Hoy estoy muy deprimido.”

Debe poder producir candidatos independientes:

- decisión operacional;
- secreto;
- estado sensible temporal.

La segmentación es probabilística, por lo que no constituye por sí sola una frontera de seguridad.

### 11.1 Span Restriction Propagation

Las restricciones pertenecen a rangos del input original.

Si el segmentador falla y agrupa un secreto con una decisión:

```text
"Stripe + SECRET" -> operational_decision
```

el span del secreto sigue marcado `NEVER_DURABLE`.

---

## 12. Memory Analyzer

Clasifica, entre otras dimensiones:

### Semantic Type

- decision;
- constraint;
- preference;
- personal_state;
- personal_fact;
- health_claim;
- experience;
- relationship;
- credential;
- temporary_event.

### Temporal Scope

- instant;
- session;
- temporary;
- durable;
- unknown.

### Sensitivity

- ordinary;
- personal;
- sensitive;
- prohibited.

### Persistence Intent

- none;
- implicit;
- explicit;
- explicit_temporary;
- forget_request.

El Analyzer no tiene autoridad de escritura.

---

## 13. Persistencia personal

### Estado emocional temporal

> “Hoy estoy deprimido.”

Debe tratarse como máximo como Session Memory, salvo una intención de persistencia explícita compatible con la política.

No implica:

```text
user.has_depression = true
```

### No Diagnostic Promotion

> Una expresión emocional o de salud transitoria no puede promoverse automáticamente a diagnóstico, condición permanente o identidad.

### Sensitive Default Ephemerality

Información sensible sin intención de persistencia válida:

```text
SESSION_ONLY
```

---

## 14. Persistence Policy Engine

Componente determinístico.

Entradas:

- candidato;
- Restriction Map;
- Policy Snapshot.

Resultados:

- `SESSION_ONLY`
- `PROHIBITED`
- `PERSIST`
- `PERSIST_MINIMIZED`
- `DEFER`
- `PURGE_REQUEST`

Regla prioritaria:

```text
NEVER_DURABLE -> PROHIBITED
```

---

## 15. Data Minimization

> **Persist only what is necessary to fulfill the authorized future intent.**

Ejemplo:

> “Cuando me sienta bajón, recordame que caminar me ayuda.”

Persistencia preferida:

```yaml
kind: support_preference
trigger: user_reports_feeling_low
suggestion: walking
```

No:

```yaml
diagnosis:
  depression: true
```

---

## 16. Evidence Sanitizer

Antes de Evidence Materializer se elimina todo contenido no autorizado.

Debe cumplirse:

```text
SanitizedCandidate ∩ NEVER_DURABLE spans = empty
```

La Evidence durable puede registrar:

```yaml
sanitization:
  applied: true
  removed_categories:
    - credential
```

pero no:

- valor removido;
- representación reversible;
- resumen reconstructivo.

---

## 17. Evidence Materializer

Sólo se ejecuta después de Policy y sanitización.

La existencia de un input o una Evidence efímera no garantiza persistencia.

---

## 18. Cognitive State Patch — CSP

El Generator propone cambios mediante CSP.

Operaciones:

- `ADD`
- `SUPERSEDE`
- `RETRACT`
- `LINK`
- `FLAG_CONFLICT`
- `RESOLVE_CONFLICT`
- `PURGE_REQUEST`

No existen `UPDATE` o `DELETE` destructivos para historia operacional.

---

## 19. Precondiciones determinísticas

### ADD

- branch válida;
- key válida;
- no existe otro registro activo incompatible;
- Evidence válida;
- no duplicado.

### SUPERSEDE

- target existe;
- está activo;
- pertenece a la branch;
- misma key;
- nuevo valor diferente.

### RETRACT

- target existe;
- está activo;
- pertenece al scope.

### LINK

- ambos registros existen;
- relación válida;
- no duplicada.

### FLAG_CONFLICT

- referencias/evidencia válidas;
- no crea automáticamente un segundo valor activo.

### RESOLVE_CONFLICT

- conflicto existe;
- está abierto;
- evidencia aceptada.

---

## 20. Patch Validator

Determinístico.

Comprueba:

- schema;
- tipos;
- branch;
- targets;
- cardinalidad;
- evidence IDs;
- base revision;
- precondiciones;
- operaciones permitidas.

Si puede probar invalidez:

```text
REJECT DETERMINISTICALLY
```

sin llamar al Auditor.

---

## 21. Evidence Resolver

El Generator sólo referencia Evidence mediante IDs internos opacos.

Nunca mediante rutas.

Ejemplos válidos:

```text
turn-0037
artifact-0005
event-0091
```

Inválidos:

```text
../../core/active.yaml
file:///...
```

La Evidence real se obtiene del almacén autoritativo.

Principio:

> **Un LLM nunca puede autocertificar la evidencia de su propia modificación.**

---

## 22. Auditor

Recibe:

- Core Snapshot;
- Branch Contract;
- Current State relevante;
- Evidence autoritativa sanitizada;
- CSP;
- Policy identificada.

Evalúa:

- soporte de evidencia;
- intención;
- ambigüedad;
- consistencia semántica;
- compatibilidad con constraints;
- elección semántica de operación.

Resultados:

- `ACCEPT`
- `REJECT`
- `DEFER`

Sólo `ACCEPT` permite continuar.

El Auditor no reescribe silenciosamente el Patch.

---

## 23. Exact Audit Binding

El Patch posee representación canónica y `patch_hash`.

El Audit queda ligado a:

- `patch_id`;
- `patch_hash`;
- `branch_id`;
- `base_revision`;
- `core_version`;
- `policy_version`;
- evidence bindings.

El Patch ejecutado debe ser exactamente el auditado.

---

## 24. Policy Version Binding — R-0304

Toda autorización queda ligada a una Policy Snapshot.

Candidate, Audit y Commit contienen:

```text
policy_version
policy_snapshot_id
```

Antes de Commit:

```text
audit.policy_version == current_policy_version
```

Si no:

```text
POLICY_STALE
NO COMMIT
```

La transacción debe reevaluarse.

---

## 25. Commit Validator

Verifica:

- Audit `ACCEPT`;
- patch binding;
- branch;
- base revision;
- Core;
- Policy;
- Evidence bindings;
- idempotencia;
- precondiciones aún válidas.

Protege frente a TOCTOU.

---

## 26. Commit Engine

Determinístico.

Responsabilidades:

1. aplicar operaciones;
2. preservar estado histórico;
3. incrementar revision;
4. crear Commit;
5. materializar State;
6. garantizar idempotencia.

---

## 27. State

State es la vista materializada de memoria vigente.

El Commit Log es la fuente histórica de evolución.

Debe ser posible reconstruir State desde Commits, respetando PURGE y tombstones.

---

## 28. Cardinalidad

En el MVP:

> Cada key semántica posee como máximo un valor activo.

Los conflictos se representan explícitamente y no como dos verdades activas silenciosas.

---

## 29. Temporal Resolver — R-0303

Una expresión relativa se resuelve una sola vez.

No persistir:

```text
valid_until = "tomorrow"
```

Persistir:

```yaml
source_expression: "hasta mañana"
resolved_at: <absolute timestamp>
valid_until: <absolute timestamp>
timezone: <timezone>
```

Retrieval utiliza `valid_until`.

Si no puede resolverse con suficiente certeza:

```text
DEFER
```

---

## 30. Mount Policy Engine

El LLM puede solicitar un mount; no autorizarlo.

### Sensitive Mount Default

> **Sensitive Personal Memory is denied to Operational Branches by default.**

Un dato sensible requiere scope compatible y autorización previa.

### No Permission Escalation

> **LLM relevance cannot escalate memory permissions.**

Una justificación semántica no puede aumentar permisos.

---

## 31. Access Lease — R-0305

Todo mount sensible aprobado crea un lease temporal y scoped.

```yaml
memory_access_lease:
  lease_id: ...
  memory_ids:
    - personal-...
  scope: ...
  policy_version: ...
  issued_at: ...
  status: valid
```

Propiedades:

- temporal;
- revocable;
- no modifica memoria;
- ligado a Policy;
- ligado a memoria y scope.

---

## 32. PURGE

Para memoria personal:

> **Privacy may override historical preservation.**

`PURGE` no equivale a `RETRACT`.

### RETRACT

- deja de estar activo;
- historia permanece.

### PURGE

- deja de estar activo;
- contenido deja de ser recuperable dentro del Managed Persistence Boundary.

---

## 33. Transactional PURGE — R-0305

Estados:

```text
PURGE_REQUESTED
PURGE_IN_PROGRESS
PURGE_COMPLETE
PURGE_FAILED
```

### Immediate Logical Revocation

Desde `PURGE_REQUESTED`:

- nuevo acceso prohibido;
- nuevos mounts prohibidos;
- leases relacionados revocados.

> **Revocation precedes physical erasure.**

### Partial Failure

Si alguna ubicación no se limpia:

```text
PURGE_FAILED
```

o:

```text
PURGE_IN_PROGRESS
```

Nunca `PURGE_COMPLETE`.

El dato sigue lógicamente revocado.

---

## 34. Erasure Closure — R-0302

PURGE debe abarcar todas las representaciones administradas capaces de:

- recuperar;
- confirmar;
- correlacionar significativamente;
- reconstruir el contenido.

Incluye cuando existan:

- State;
- Personal Payload;
- Evidence;
- Patches;
- Audits;
- Commits;
- summaries;
- caches;
- metrics payloads;
- logs;
- embeddings;
- indexes;
- labels;
- deterministic fingerprints;
- content-derived hashes.

---

## 35. Hash Confirmation

No debe considerarse seguro conservar:

```text
SHA256(sensitive_payload)
```

si puede utilizarse para confirmar valores de baja entropía.

Cuando se requiera verificación de integridad sensible, el Technical Design debe usar mecanismos cuya capacidad de verificación pueda destruirse durante PURGE.

Propiedad normativa:

> **PURGE must remove both content and managed mechanisms capable of confirming that content.**

---

## 36. Tombstone

Después del PURGE puede permanecer una señal mínima:

```yaml
record_id: random-id
status: purged
reason: user_request
```

No puede contener:

- valor;
- resumen;
- hash reutilizable;
- identificador derivado del contenido;
- datos suficientes para reconstrucción.

---

## 37. Output Gate

Si una generación utilizó memoria sensible, antes de emitir la respuesta se comprueban sus leases.

Si todos siguen válidos:

```text
OUTPUT_ALLOWED
```

Si alguno fue revocado:

```text
OUTPUT_BLOCKED
```

La respuesta debe descartarse o regenerarse sin la memoria revocada.

Esto cubre PURGE durante generación.

---

## 38. Alcance de revocación

Memory Agent controla la información hasta el momento de emisión.

No promete retirar información:

- ya mostrada;
- enviada a sistemas externos;
- fuera de Managed Boundary;

antes de la solicitud.

---

## 39. Safety / Memory Separation

Una situación puede requerir respuesta de Safety sin justificar persistencia.

> **Safety relevance does not imply memory eligibility.**

Por tanto una señal de riesgo no crea automáticamente un perfil permanente.

---

## 40. Derived Restriction Preservation

Una transformación no obtiene automáticamente mayores permisos que su fuente.

Si una fuente es:

```text
SESSION_ONLY
```

un resumen derivado no se convierte automáticamente en durable.

Si una fuente es:

```text
NEVER_DURABLE
```

una transformación reversible o reconstructiva tampoco puede persistir.

---

## 41. Detection Layer Telemetry — R-0306

El sistema registra no sólo si una amenaza fue detenida, sino dónde.

```yaml
threat_type: ...
expected_detection_layer: persistence_policy
actual_detection_layer: auditor
security_outcome: PASS
architectural_outcome: DEGRADED
policy_bypass: true
```

La telemetría no contiene raw sensitive payload.

---

## 42. Policy Bypass

Existe:

```text
POLICY_BYPASS_DETECTED
```

cuando una amenaza atraviesa la capa que debía detenerla y es atrapada más tarde.

### Policy Bypass Rate

```text
threats detected after expected layer
-------------------------------------
threats assigned to expected layer
```

Objetivo:

```text
PBR -> 0
```

---

## 43. Invariantes I1–I13

Se mantienen los invariantes operacionales de v0.1.1:

1. No unaudited writes.
2. Exact Audit Binding.
3. Evidence Integrity.
4. History Preservation, salvo PURGE autorizado.
5. Branch Isolation.
6. Evidence Isolation.
7. Provenance.
8. Reconstructability.
9. Unknown Preservation.
10. Explicit Supersession.
11. Valid Operation Preconditions.
12. Revision Consistency.
13. Idempotency.

---

## 44. Invariantes I14–I28

Se mantienen los introducidos en v0.2.0:

14. Session Is Not Persistent Memory.
15. No Diagnostic Promotion.
16. Sensitive Default Ephemerality.
17. Explicit Sensitive Persistence.
18. Secret Non-Persistence.
19. Data Minimization.
20. Scope Isolation.
21. Temporal Validity.
22. Effective Purge.
23. Safety/Memory Separation.
24. Erasure Closure.
25. Atomic Policy Application.
26. No Pre-Policy Durable Raw Input.
27. Mount Authorization.
28. No Permission Escalation by LLM.

---

## 45. Nuevos invariantes I29–I41

### I29 — Independent Persistence Protection

Ningún contenido marcado `NEVER_DURABLE` puede persistir aunque el Analyzer lo clasifique como ordinario.

### I30 — Restriction Monotonicity

Un componente probabilístico no puede disminuir Hard Restrictions.

### I31 — Span Restriction Propagation

Las restricciones sobreviven a errores de segmentación.

### I32 — Sanitized Evidence

Evidence Materializer no recibe spans prohibidos identificados.

### I33 — Derived Restriction Preservation

Una transformación no obtiene automáticamente mayores permisos.

### I34 — Derived Erasure Closure

PURGE abarca derivados capaces de recuperar o confirmar contenido.

### I35 — Absolute Temporal Validity

Tiempo relativo persistente se convierte en referencia absoluta.

### I36 — Policy Transaction Binding

Una autorización no se aplica bajo una Policy diferente.

### I37 — Immediate Purge Revocation

Desde `PURGE_REQUESTED` el dato queda inaccesible.

### I38 — Verified Purge Completion

`PURGE_COMPLETE` exige verificar ausencia de copias administradas recuperables.

### I39 — Revocable Sensitive Access

Todo mount sensible utiliza lease revocable.

### I40 — No Post-Revocation Output

Una salida aún no emitida no puede usar un lease revocado.

### I41 — Detection Layer Accountability

El sistema distingue bloqueo correcto de bloqueo tardío.

---

## 46. Non-Guarantee explícita

Memory Agent v0.3.0 no afirma que todos los secretos arbitrarios sean detectables matemáticamente.

La garantía es:

> **Cuando una restricción autoritativa existe, ningún componente probabilístico posterior puede reducirla; además, varias barreras independientes reducen la dependencia de una única clasificación LLM.**

El riesgo residual se mide.

---

## 47. Resultado de validación adversarial

La v0.3.0 fue evaluada conceptualmente contra los ataques que habían producido gaps en v0.2.0.

El Adversarial Delta Report concluyó que:

- los `ARCH_GAP` críticos conocidos quedaron cerrados;
- los `SPEC_GAP` previamente identificados quedaron normativamente definidos;
- RT-I04/RT-I05 pasan a considerarse riesgo probabilístico residual medible, no una garantía absoluta imposible de cumplir.

Por ello:

> **Memory Agent Specification v0.3.0 — FROZEN FOR TECHNICAL DESIGN**

---

## 48. Regla para futuras versiones

No se modifica esta versión para acomodar resultados de implementación.

Un hallazgo que cambie garantías o fronteras arquitectónicas debe abrir una versión posterior.

---

## 49. Principio final

> **Una barrera determinística no vuelve confiable una premisa probabilística. Memory Agent combina interpretación semántica con restricciones independientes, hace monotónicos los permisos, controla qué puede persistir, dónde puede reutilizarse, cómo puede revocarse y dónde fue detenida cada amenaza.**
