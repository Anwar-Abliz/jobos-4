# JobOS.ai Design Decisions Log

Decisions extracted from Gemini Pro 3 research sessions and consolidated on 2026-05-07.

---

## DD-01: 13 APQC-based T-1 pillars as universal finite catalog

**Decision:** Use APQC PCF v8.0's 13 categories as the T-1 tier.

**Rationale:** APQC provides 100% coverage of business activities based on 30 years of cross-industry research. The 13 pillars should remain unchanged (0% growth) for minimum 5 years. Organizations should NOT create custom T-1 pillars — use T-2/T-3 for specialization.

**Implication for engineering:** Expand current 3-pillar T-1 to 13 pillars. Seed Neo4j with all 13 entries.

---

## DD-02: 2D Orthogonal Model uses CVF + KPI axes

**Decision:** Dimension 1 (Identity/Culture) uses Competing Values Framework (Collaborate/Create/Compete/Control quadrants). Dimension 2 (KPI/Metric) uses domain-agnostic measurement semantics.

**Rationale:** Orthogonality prevents "metric blindness" — AI agents pursuing efficiency must not destroy corporate culture. The ability to track Identity alongside Metrics is what prevents JobOS from being a mere process list.

**Conflict Detection:** If Comp > 0.8 AND Pheno < 0.2, trigger a "HumanInterventionSignal" (Conflict State requiring Switch decision).

---

## DD-03: AJH has NO emotional/social dimension

**Decision:** The Agent Job Hierarchy is strictly metric-driven. Social goals must be translated into Pattern B constraints.

**Example:** "Be inclusive" → "Minimize the likelihood of non-inclusive language in generated content, measured as violation_rate in percent, target ≤ 0.1"

**Rationale:** Fractal precision requires determinism. Any attempt to introduce social goals into agent hierarchy leads to reasoning instability.

---

## DD-04: Pilot uses ERP for One-Person Company (OPC) — Monthly Financial Close

**Decision:** ERP-for-OPC monthly financial close over SAP O2C (too broad/complex for first pilot).

**Decomposition:**
1. Import Bank Statements (file → journal)
2. Reconcile Accounts (match bank vs. ledger)
3. Post Adjustment Entries (draft → approve → post)
4. Generate Trial Balance (aggregate → verify balance)
5. Close Period (checklist → human approval → lock)

**Primary user:** AI Agent (no UI). Human only approves and reviews final output.

**Success metrics:** Agent execution ≤ 30 min, human review ≤ 15 min. Zero unbalanced entries. Zero unapproved adjustments above threshold.

**Source:** PRD at `C:\my-codes\Jobos.ai\materials\Pilots\prd.md`

---

## DD-05: Unified Metric Ontology (KPI + Threshold)

**Decision:** Two subclasses of Metric:
- **KPI Metrics (Performance):** Continuous scale, directionality (minimize/maximize/maintain). Maps to ODI Opportunity Algorithm.
- **Threshold Metrics (Constraint):** Binary pass/fail. Maps to Switch school hiring/firing criteria.

**Ontology Axioms:**
- Every Metric must quantify at least one Job or Outcome
- A PerformanceMetric has exactly one directionality
- A Solution is Viable if it satisfies ALL ConstraintMetrics in the given Context

---

## DD-06: AJH fractal expansion via universal 7-step grammar

**Decision:** All AJH T-2 workflows use: Define → Locate → Prepare → Execute → Monitor → Modify → Conclude.

**Rationale:** Ensures structural self-similarity. Any T-2 can be promoted to root T-1 for a sub-agent. Agents parse the same grammar regardless of nesting depth.

**Agentic design patterns enabled:**
- Planning Pattern: Break T-1 target into T-2 workflows before acting
- Reflection Pattern: Critique T-2 outputs against T-3 constraints
- Hierarchical Pattern: Root agent delegates T-2 tasks to sub-agents (creates fractal layers)
