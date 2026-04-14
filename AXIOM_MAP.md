# AXIOM_MAP.md — JobOS 4.0 Axiom Registry

Maps each axiom to its implementation file(s), test coverage, and phase scope.

**Core Axiom**: `Entity HIRES Entity IN Context TO MINIMIZE Imperfection.`

---

## Axiom Summary Table

| # | Name | Phase 1 Scope | Implementation | Tests |
|---|------|---------------|----------------|-------|
| 1 | Hierarchy | Full | `kernel/axioms.py` | `tests/unit/test_axioms.py` |
| 2 | Imperfection | Full | `kernel/axioms.py` | `tests/unit/test_axioms.py` |
| 3 | Duality + Contextual Variance | Heuristic | `kernel/axioms.py` | `tests/unit/test_axioms.py` |
| 4 | Singularity (level=0) | Full | `kernel/axioms.py` | `tests/unit/test_axioms.py` |
| 5 | Linguistic | Full (functional + experiential) | `kernel/axioms.py`, `kernel/experience.py` | `tests/unit/test_axioms.py`, `tests/unit/test_linguistic.py` |
| 6 | Singularity+ (root_token) | Application-level | `kernel/axioms.py`, `services/entity_service.py` | `tests/unit/test_axioms.py` |
| 7 | The Switch | Heuristic | `engines/switch_evaluator.py` | `tests/unit/test_switch_evaluator.py` |
| 8 | Market Topology | Stub | `kernel/market_topology.py` | `tests/unit/test_axioms.py` |

---

## Detailed Axiom Definitions

### Axiom 1 — Hierarchy
> "Child job's output must enable parent job's input."

- **Implementation**: `src/jobos/kernel/axioms.py` → `JobOSAxioms.validate_hierarchy()`
- **Neo4j edges**: `HIRES` (parent → child), `CHILD_OF` (child → parent for upward traversal)
- **Kernel model**: `kernel/hierarchy.py` — `HierarchyJob`, `HierarchyEdge`
- **Phase 1**: Full enforcement. Parent/child reference validated on create.

---

### Axiom 2 — Imperfection
> "Every Job has at least one Imperfection. Solutions decay — perfection is never permanent."

- **Implementation**: `src/jobos/kernel/axioms.py` → `JobOSAxioms.validate_imperfection_inherent()`
- **Entropy residual**: When no imperfections exist, a residual is synthesized
  with `severity=0.05`, `entropy_risk=0.3`.
- **Phase 1**: Full enforcement. Entropy residual created automatically.

---

### Axiom 3 — Duality + Contextual Variance
> "A completed Job's output can serve as Capability for a higher Job."
> "Context is mandatory for HUMAN executor jobs."

- **Duality implementation**: `JobOSAxioms.validate_duality()` — checks `status in ('completed', 'resolved')`
- **Contextual Variance**: `JobOSAxioms.validate_contextual_variance()` — requires context fields for `executor_type='HUMAN'`
- **Duality hook**: `entity_service.py` — adds `:Capability` label when job transitions to `completed`
- **Phase 1**: Heuristic. Duality is ontological (applied at service layer). Contextual variance is a property check.

---

### Axiom 4 — Singularity (level-based)
> "At most one root Job per optimization scope (level=0, no parent_id)."

- **Implementation**: `src/jobos/kernel/axioms.py` → `JobOSAxioms.validate_singularity()`
- **Phase 1**: Full enforcement on in-memory job lists.

---

### Axiom 5 — Linguistic
> "Job statements must start with an action verb (functional) OR experiential phrase (Experience Space)."

**Functional branch** (T1, T2, T3):
- Must start with a verb from `ACTION_VERBS` in `kernel/job_statement.py`
- Example: `"Define the success criteria"`, `"Deploy the service"`
- Implementation: `JobOSAxioms.validate_linguistic_structure(statement, experiential=False)`

**Experiential branch** (T4 — Dimension A):
- Must start with `"To Be"` or `"Feel"` (case-insensitive)
- Example: `"To Be seen as a trusted advisor"`, `"Feel confident in delivery"`
- Implementation: `JobOSAxioms.validate_linguistic_structure(statement, experiential=True)`
- Experience model: `kernel/experience.py` → `ExperienceProperties`, `validate_experiential_statement()`

**TypeScript parity**: `frontend/src/lib/validators.ts` → `validateJobStatement()`

- **Tests**: `tests/unit/test_axioms.py`, `tests/unit/test_linguistic.py`
- **Phase 1**: Full enforcement.

---

### Axiom 6 — Singularity+ (root_token)
> "At most one `root_token='ROOT'` per `scope_id`."

Enhanced version of Axiom 4 with explicit scope binding. Neo4j Community Edition
does not support conditional partial uniqueness constraints, so this is enforced
at the application layer in `entity_service.py`.

- **Implementation**: `kernel/axioms.py` → `JobOSAxioms.validate_root_token()`
- **Service hook**: `entity_service.py` — queries existing ROOT jobs in scope before persisting
- **Neo4j indexes**: `job_scope_idx` on `scope_id` (see `adapters/neo4j/schema.py`)
- **Phase 1**: Application-level enforcement.

---

### Axiom 7 — The Switch
> "Hire/Fire justified by context change OR metric breach."

The full heuristic Switch evaluator with hysteresis dead-band to prevent oscillation.

- **Implementation**: `src/jobos/engines/switch_evaluator.py` → `switch_evaluator()` async function
- **Boolean gate**: `kernel/axioms.py` → `JobOSAxioms.validate_switch()` (simple OR gate)
- **Input data**: `adapters/postgres/models.py` → `JobMetricsRow` (Dimension B)
- **Port**: `ports/relational_port.py` → `insert_job_metric()`, `get_job_metrics()`
- **Migration**: `alembic/versions/001_add_job_metrics.py`

**SwitchDecision outputs**:
- `HIRE`: Context change detected → new executor needed
- `FIRE`: Metric breach detected → terminate current executor
- `NONE`: All stable

**Hysteresis**: `hysteresis_band=0.05` (default) prevents rapid HIRE/FIRE cycling
when a metric oscillates near the bound. State is caller-managed via `_state` dict.

- **Tests**: `tests/unit/test_switch_evaluator.py`
- **Phase 1**: Heuristic (no NSAIG EFE, no CDEE stability check).
- **Phase 2**: Replace context_threshold with learned threshold from VFE history.
- **Phase 3**: Replace with full NSAIG `SwitchLogic` + CDEE `DynamicController` integration.

---

### Axiom 8 — Market Topology
> "Jobs cluster by unmet outcome patterns — this is the market."

- **Implementation**: `src/jobos/kernel/market_topology.py` → `discover_market_clusters()`
- **Also in**: `kernel/axioms.py` → `JobOSAxioms.discover_market_clusters()` (delegates)
- **IPS vector utility**: `market_topology.py` → `compute_ips_vector()`
- **Phase 1**: Stub. Returns single cluster with all jobs.
- **Phase 2**: KMeans on normalized IPS vectors from `job_metrics` table (Dimension B).
- **Phase 3**: Louvain community detection on imperfection co-occurrence graph in Neo4j.

---

## Dimension Map

| Dimension | Name | Neo4j Label | PostgreSQL Table | Axiom |
|-----------|------|-------------|-----------------|-------|
| Functional Execution | T1–T4 Job Tiers | `:Entity:Job` | — | 1, 2, 4, 5 |
| A — Experience Space | Felt states | `:Entity:Experience` | — | 5 (experiential) |
| B — Evaluation Space | Performance metrics | — | `job_metrics` | 7, 8 |

---

## Neo4j Relationships

| Relationship | Direction | Axiom | Description |
|-------------|-----------|-------|-------------|
| `HIRES` | parent → child | 1 | Core golden axiom |
| `FIRES` | hirer → hiree | 7 | Switch termination |
| `MINIMIZES` | capability → imperfection | 2, 3 | Causal claim |
| `PART_OF` | child → parent | 1 | Hierarchy upward |
| `CHILD_OF` | child → parent | 1 | Upward traversal alias |
| `QUALIFIES` | context → job | 3 | Markov blanket |
| `MEASURED_BY` | job → metric | 7 | Metric linkage |
| `OCCURS_IN` | imperfection → job | 2 | Imperfection location |
| `IMPACTS` | imperfection → metric | 2, 7 | Causal impact |
| `ABOUT` | assumption → entity | — | Epistemic link |
| `SUPPORTS` | evidence → assumption | — | Bayesian update |
| `REFUTES` | evidence → assumption | — | Bayesian falsification |
| `DUAL_AS` | job → capability | 3 | Ontological superposition |

---

## File Index

```
src/jobos/kernel/
├── axioms.py           — All 8 axiom validators (JobOSAxioms class)
├── entity.py           — EntityBase + JobProperties (executor_type, root_token, tier)
├── hierarchy.py        — HierarchyJob (root_token, scope_id) + T3_STANDARD_STEPS
├── experience.py       — Dimension A: ExperienceProperties + validate_experiential_statement
├── market_topology.py  — Axiom 8 scaffold + compute_ips_vector
├── generative_model.py — Tier → GenerativeModel mapping
└── job_statement.py    — ACTION_VERBS + validate_verb (Axiom 5 functional)

src/jobos/engines/
└── switch_evaluator.py — Axiom 7 heuristic SwitchEvaluator with hysteresis

src/jobos/adapters/
├── neo4j/schema.py     — Neo4j indexes (tier, scope, experience)
└── postgres/
    ├── models.py       — JobMetricsRow ORM (Dimension B)
    └── metric_repo.py  — insert_job_metric + get_job_metrics

src/jobos/ports/
└── relational_port.py  — Abstract job_metrics methods

alembic/versions/
└── 001_add_job_metrics.py — Migration: creates job_metrics table

frontend/src/lib/
└── validators.ts       — TypeScript parity validators (Axiom 5)

tests/unit/
├── test_switch_evaluator.py — Axiom 7 heuristic tests
├── test_axioms.py           — All 8 axioms unit tests
└── test_linguistic.py       — Axiom 5 experiential edge cases
```
