# ERP for OPC — Sharing & Collaboration Guide

---

## Part 1: How to Share the Codebase

### Option A: GitHub Desktop (Recommended)

Best for: code review, comments on specific lines, collaboration via PRs.

**Step-by-step in GitHub Desktop:**

1. **Open the repository**
   - Open GitHub Desktop
   - If `jobos-4` isn't listed, click **File → Add Local Repository** and browse to `C:\my-codes\jobos-4`

2. **Create a new branch**
   - Click the **Current Branch** dropdown at the top center
   - Click **New Branch**
   - Name it: `pilot/erp-opc`
   - Base it on: `main` (or your current default branch)
   - Click **Create Branch**

3. **Review the changes**
   - In the left panel, you'll see all new/modified files listed under "Changes"
   - Check the boxes next to the files you want to include:
     - `pilots/erp-opc/` (all files in this folder)
     - `src/jobos/pilots/` (all files in this folder)
     - `src/jobos/adapters/neo4j/entity_repo.py`
     - `src/jobos/api/app.py`
     - `src/jobos/kernel/t3_dsl.py`
   - Uncheck any files you do NOT want to share (e.g., `.env`, `node_modules`)

4. **Commit**
   - In the bottom-left "Summary" field, type: `feat: ERP-for-OPC pilot — agent-first financial close engine`
   - Optionally add a description: `Monthly financial close for one-person companies. Agent-first API, no UI. 5 capabilities, 12 constraints, full test suite.`
   - Click **Commit to pilot/erp-opc**

5. **Push to GitHub**
   - Click the **Publish branch** button (top bar, where it says "Publish branch to GitHub")
   - Wait for the push to complete — you'll see a success indicator

6. **Share the link**
   - Click **View on GitHub** (or go to the repo in your browser)
   - Switch to the `pilot/erp-opc` branch using the branch dropdown
   - Navigate to `pilots/erp-opc/`
   - Copy the URL: `https://github.com/Anwar-Abliz/jobos-4/tree/pilot/erp-opc/pilots/erp-opc`
   - Share this link with your team

7. **Optional: Create a Pull Request for review**
   - In GitHub Desktop, click **Create Pull Request** (or in the browser, click "Compare & pull request")
   - Title: `[Pilot] ERP for OPC — Agent-First Financial Close`
   - Body: Paste the non-technical summary from Part 3 below
   - Assign reviewers from your project team
   - This gives teammates a dedicated space to comment on specific code lines

Teammates can:
- Browse code directly on GitHub
- Comment on the PR with line-level feedback
- Fork and build their own design variant in their own folder (as the PRD specifies — 7 independent approaches)

### Option B: Standalone ZIP Export

Best for: quick sharing with people who don't use Git or aren't on the repo.

```powershell
cd C:\my-codes\jobos-4
tar -czf erp-opc-pilot.tar.gz pilots/erp-opc/ src/jobos/pilots/erp_opc/
```

Share via Teams/OneDrive/SharePoint. Include the `AGENT_GUIDE.md` as the entry point.

### Option C: SharePoint / OneDrive Folder

Best for: SAP internal teams who work through Microsoft 365.

1. Upload `pilots/erp-opc/` to a shared OneDrive folder
2. Grant edit access to the project team
3. They can view the JSON/Markdown files directly in browser
4. For code collaboration, pair with Option A

### Option D: SAP Dev Spaces / GitHub Codespaces

Best for: letting teammates run and test the code without local setup.

1. Push to GitHub (Option A)
2. Team members open in Codespaces or SAP Business Application Studio
3. They can run `python -m pytest pilots/erp-opc/test_e2e.py -v` immediately

### My Recommendation

**Use Option A (GitHub branch) + share the non-technical summary (Part 3) in your team chat/email.** This gives reviewers both context (the summary) and depth (the code). The PRD says each participant works in their own folder — GitHub branches naturally support this model.

---

## Part 2: Technical Summary

### ERP for OPC — Technical Overview

**What is this?**

A pilot implementation of an agent-first ERP system for one-person companies, focused exclusively on the monthly financial close process. There is no UI — the system exposes only machine-readable API endpoints designed to be consumed by an AI Agent.

**Architecture:**

```
AI Agent (Claude/GPT/etc.)
    │ reads AGENT_GUIDE.md
    │ calls API endpoints
    ▼
FastAPI Service (localhost:8000/api/pilot/erp-opc/*)
    │
    ├── ingest_bank_data      — Parse CSV/OFX → journal entries
    ├── reconcile_entries     — Match bank txns vs. ledger (amount+date+ref)
    ├── draft_adjustments     — Create journal entries, auto-post < threshold
    ├── generate_trial_balance — Aggregate entries, verify debit == credit
    └── close_period          — Lock period (human approval ALWAYS required)
    │
    ▼
In-Memory State (pilot) → PostgreSQL (production)
Neo4j Graph (job hierarchy + constraints)
```

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| No UI | Primary user is AI Agent, not human |
| Explicit escalation model | Agent MUST stop on ambiguity — never self-decides |
| Double-entry bookkeeping | Every adjustment has debit + credit (zero tolerance for imbalance) |
| Threshold-based approval | Auto-post < $500, human approval >= $500 |
| Period locking | Human must always confirm close — no exceptions |
| Full audit trail | Every operation returns who/what/when |

**Constraint model (T-3 DSL):**

12 constraints across three patterns:
- **Pattern A (time):** Ingestion ≤ 5 min, reconciliation ≤ 10 min, trial balance ≤ 30 sec, close ≤ 2 min, total ≤ 30 min
- **Pattern B (likelihood):** Zero duplicate ingestion, zero false matches, zero unbalanced entries, zero unapproved posts, zero post-close modifications
- **Pattern C (cost):** Total token usage ≤ 50k per monthly close

**File structure:**

```
pilots/erp-opc/
├── hierarchy.json        — Job hierarchy (T-1/T-2/T-3) + agent capabilities + crosswalk
├── constraints.json      — 12 T-3 DSL constraints (machine-parseable)
├── AGENT_GUIDE.md        — Complete agent instructions (the "user manual" for the AI)
├── service.py            — Business logic (FinancialCloseService class)
├── routes.py             — 11 FastAPI endpoints
├── seed_pilot.py         — Neo4j graph seeder (24 entities + edges)
├── test_e2e.py           — 12 pytest tests (all passing)
└── fixtures/
    ├── bank_statement_2026_04.csv  — 16 sample transactions
    └── ledger_2026_04.json         — 14 pre-existing ledger entries
```

**How to run:**

```bash
cd C:\my-codes\jobos-4
pip install -e .                             # Install dependencies
python -m pytest pilots/erp-opc/test_e2e.py -v  # Run tests (no DB needed)
python pilots/erp-opc/seed_pilot.py          # Seed Neo4j (requires connection)
uvicorn jobos.api.app:create_app --factory --port 8000  # Start API server
```

**Technology stack:** Python 3.13, FastAPI, Pydantic v2, Neo4j (graph), pytest

---

## Part 3: Non-Technical Summary

### ERP for OPC — What Is This and Why Does It Matter?

**The problem:**

A one-person company (freelancer, solo consultant, indie developer) still needs to do monthly financial closing — matching bank statements against records, making corrections, generating reports, and locking the books. Traditional ERPs assume a team of accountants operating through screens. AI Agents can do this work now — but only if the ERP is designed for machines, not humans.

**Our solution:**

We built a financial close system with no user interface at all. Instead, it exposes a clean API that an AI Agent can call. The agent reads a guidance document (like a procedure manual), follows the steps, and executes the entire monthly close autonomously. The human owner only needs to:
1. Approve large transactions (over a configurable threshold)
2. Confirm the final period close

**The 5-step process:**

1. **Import** — Agent loads bank statement data into the system
2. **Reconcile** — Agent matches bank transactions against the company's records
3. **Adjust** — Agent creates correction entries for discrepancies
4. **Balance** — Agent generates a trial balance to confirm everything adds up
5. **Close** — Agent prepares the close; human gives final approval

**Key principles:**

- **The agent must stop when unsure.** It cannot make judgment calls or silently skip problems.
- **Everything is traceable.** Every action records who did it, when, and what changed.
- **Human stays in control.** The agent does the work; the human approves the result.

**Success metric:** Agent completes its part in ≤ 30 minutes. Human review takes ≤ 15 minutes. Total monthly close: under 45 minutes.

**What this is NOT:**
- Not payment processing, invoicing, payroll, inventory, or tax filing (those are future phases)
- Not a replacement for an accountant's judgment — it's a replacement for an accountant's repetitive labor

**Why this matters for our team:**

This pilot validates that JobOS.ai's job hierarchy model works end-to-end: we can take a business process, decompose it into structured jobs, set measurable constraints, and have an AI Agent execute it autonomously with proper governance. If it works for financial close, the same pattern applies to any structured business process.

---

## Part 4: Demo Guide — Step by Step

### Before the Meeting

1. **Ensure Python 3.13 is installed** and the jobos-4 virtualenv is activated
2. **Run tests once** to confirm everything works:
   ```powershell
   cd C:\my-codes\jobos-4
   python -m pytest pilots/erp-opc/test_e2e.py -v
   ```
3. **Have these files open in VS Code:**
   - `pilots/erp-opc/AGENT_GUIDE.md` (the star of the show)
   - `pilots/erp-opc/hierarchy.json`
   - `pilots/erp-opc/fixtures/bank_statement_2026_04.csv`

4. **Optional:** Start the FastAPI server to show live API calls:
   ```powershell
   cd C:\my-codes\jobos-4
   uvicorn jobos.api.app:create_app --factory --port 8000
   ```

---

### Demo Script (15-20 minutes)

#### Slide 0: Context (2 min)

> "We're building an ERP for one-person companies — but here's the twist: the primary user isn't a human. It's an AI Agent. There's no UI. The system only speaks API, and the human only steps in to approve things."

Show the PRD briefly (the Chinese version is fine — team knows it).

---

#### Act 1: The Agent's Playbook (3 min)

Open `AGENT_GUIDE.md` in VS Code or browser.

> "This is the complete instruction manual for the agent. A model that knows nothing about accounting can read this document and execute a full monthly close. Let me walk through the 5 steps."

Scroll through Steps 1-5. Highlight:
- Clear input/output contracts for each step
- Explicit escalation triggers ("if match rate < 80%, STOP and ask human")
- The chart of accounts in the appendix

---

#### Act 2: The Constraint Model (2 min)

Open `hierarchy.json` briefly, then `constraints.json`.

> "Every step has measurable constraints. For example: ingestion must complete in under 5 minutes, reconciliation must have less than 1% false matches, and zero unbalanced entries can ever be posted. These aren't wishes — they're machine-parseable rules that we can validate automatically."

---

#### Act 3: Live API Demo (5 min)

If the server is running, use curl or the Swagger UI at `http://localhost:8000/docs`:

**Step 1 — Ingest:**
```bash
curl -X POST http://localhost:8000/api/pilot/erp-opc/ingest \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"date":"2026-04-01","amount":1500,"description":"Client payment","reference":"INV-001"},{"date":"2026-04-03","amount":-49.99,"description":"Adobe subscription","reference":"SUB-01"}]}'
```

Show the response: `{"status": "success", "ingested": 2, ...}`

**Step 2 — Reconcile:**
```bash
curl -X POST http://localhost:8000/api/pilot/erp-opc/reconcile \
  -H "Content-Type: application/json" -d '{"tolerance_amount": 0.01}'
```

Show the escalation: `{"status": "escalated", "report": {"match_rate": 0.0}, ...}`

> "See? The agent can't proceed autonomously — it escalated because there's nothing to match against. This is exactly the behavior we want."

**Step 3 — Adjustment with approval:**
```bash
curl -X POST http://localhost:8000/api/pilot/erp-opc/adjustments \
  -H "Content-Type: application/json" \
  -d '{"adjustments": [{"debit_account":"6400","credit_account":"1000","amount":750,"description":"Large consulting fee","date":"2026-04-15"}]}'
```

Show: `{"status": "escalated", "pending_approval": [{"id": "..."}]}`

> "Amount exceeds $500 threshold — the agent can't post it. A human must approve."

---

#### Act 4: Tests as Proof (3 min)

Run tests live:
```powershell
python -m pytest pilots/erp-opc/test_e2e.py -v --tb=short
```

> "12 tests, all green. These cover the full workflow including edge cases: what happens when the balance doesn't add up, when close prerequisites aren't met, when large amounts need approval."

---

#### Act 5: The Graph (2 min, optional)

If Neo4j browser is available (`http://localhost:7474`):

```cypher
MATCH (n) WHERE n.scope_id = 'pilot_erp_opc_v1'
RETURN n LIMIT 30
```

Show the visual graph with hierarchy relationships.

> "This is the same hierarchy represented as a knowledge graph. T-1 at the top, T-2 steps below, T-3 constraints attached to each step, and the agent capabilities mapped via crosswalk edges."

---

#### Closing (2 min)

> "This is one design — one of seven independent approaches our team is producing. The PRD says diverge, not converge. My contribution focuses on the constraint model and agent governance: the agent must be able to do the work, but it must also know when to stop. Happy to hear your thoughts."

---

### Backup: If Something Breaks During Demo

- **Server won't start:** Skip live API, show test results instead (tests don't need the server)
- **Tests fail:** Show the code and explain the architecture from files
- **Neo4j unavailable:** Skip the graph visualization, focus on hierarchy.json
- **No time for live demo:** Walk through AGENT_GUIDE.md + show test output screenshot

---

### Meeting Prep Checklist

- [ ] Push branch to GitHub: `git push origin pilot/erp-opc`
- [ ] Share GitHub link + non-technical summary in team chat before the meeting
- [ ] Run tests once to confirm green
- [ ] Have VS Code open with the 3 key files
- [ ] Optional: start FastAPI server + open Swagger UI
- [ ] Optional: open Neo4j browser with pilot query ready
