"""ERP-for-OPC — Financial Close Service.

Agent-first financial close engine for one-person companies.
No UI. System exposes API endpoints consumed by AI Agents.
Human intervenes only for approval and final review.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EntryStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    SUGGESTED = "suggested"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"


class PeriodStatus(str, Enum):
    OPEN = "open"
    RECONCILED = "reconciled"
    ADJUSTED = "adjusted"
    BALANCED = "balanced"
    CLOSED = "closed"


class EscalationReason(str, Enum):
    AMOUNT_ABOVE_THRESHOLD = "amount_above_threshold"
    LOW_CONFIDENCE_MATCH = "low_confidence_match"
    NOVEL_ACCOUNT = "novel_account"
    IMBALANCED_ENTRY = "imbalanced_entry"
    PARSE_ERROR = "parse_error"
    PERIOD_CLOSE_APPROVAL = "period_close_approval"


class Escalation(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    reason: EscalationReason
    description: str
    context: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: str | None = None


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    date: date
    amount: float
    description: str
    reference: str = ""
    account: str = ""
    status: EntryStatus = EntryStatus.PENDING
    source: str = "bank"


class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    date: date
    debit_account: str
    credit_account: str
    amount: float
    description: str
    status: EntryStatus = EntryStatus.PENDING
    approved_by: str | None = None
    posted_at: datetime | None = None


class MatchResult(BaseModel):
    bank_transaction_id: str
    ledger_entry_id: str
    confidence: float
    method: str


class ReconciliationReport(BaseModel):
    period: str
    total_bank: int
    total_ledger: int
    matched: int
    unmatched_bank: int
    unmatched_ledger: int
    suggestions: int
    match_rate: float


class TrialBalance(BaseModel):
    period: str
    generated_at: datetime
    accounts: list[dict[str, Any]]
    total_debits: float
    total_credits: float
    balanced: bool


class PeriodState(BaseModel):
    period_id: str
    year: int
    month: int
    status: PeriodStatus = PeriodStatus.OPEN
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None
    closed_by: str | None = None


class FinancialCloseService:
    """In-memory financial close engine for the pilot.

    Production would use PostgreSQL. This implementation validates the
    hierarchy and constraint model without external DB dependencies.
    """

    def __init__(self, approval_threshold: float = 500.0, match_confidence_threshold: float = 0.7):
        self.approval_threshold = approval_threshold
        self.match_confidence_threshold = match_confidence_threshold
        self.transactions: list[Transaction] = []
        self.ledger_entries: list[JournalEntry] = []
        self.matches: list[MatchResult] = []
        self.escalations: list[Escalation] = []
        self.periods: dict[str, PeriodState] = {}
        self.chart_of_accounts: dict[str, str] = {
            "1000": "Cash",
            "1100": "Accounts Receivable",
            "1200": "Prepaid Expenses",
            "2000": "Accounts Payable",
            "2100": "Accrued Liabilities",
            "3000": "Owner Equity",
            "4000": "Revenue",
            "5000": "Cost of Goods Sold",
            "6000": "Operating Expenses",
            "6100": "Office Expenses",
            "6200": "Software Subscriptions",
            "6300": "Professional Services",
            "6400": "Bank Fees",
            "7000": "Other Income",
            "8000": "Other Expenses",
        }

    def _period_key(self, year: int, month: int) -> str:
        return f"{year}-{month:02d}"

    def get_or_create_period(self, year: int, month: int) -> PeriodState:
        key = self._period_key(year, month)
        if key not in self.periods:
            self.periods[key] = PeriodState(period_id=key, year=year, month=month)
        return self.periods[key]

    # ── CAP-01: ingest_bank_data ───────────────────────────────────────────

    def ingest_bank_data(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse and import bank statement rows into the transaction ledger.

        Each row must have: date, amount, description. Optional: reference.
        Returns: ingested count, duplicates skipped, errors.
        """
        ingested = 0
        duplicates = 0
        errors: list[str] = []
        escalation_needed = False

        existing_refs = {t.reference for t in self.transactions if t.reference}

        for i, row in enumerate(rows):
            try:
                txn_date = row.get("date")
                if isinstance(txn_date, str):
                    txn_date = date.fromisoformat(txn_date)

                amount = float(row["amount"])
                description = str(row.get("description", ""))
                reference = str(row.get("reference", ""))

                if not description:
                    errors.append(f"Row {i}: missing description")
                    continue

                if reference and reference in existing_refs:
                    duplicates += 1
                    continue

                txn = Transaction(
                    date=txn_date,
                    amount=amount,
                    description=description,
                    reference=reference,
                )
                self.transactions.append(txn)
                existing_refs.add(reference)
                ingested += 1

            except (KeyError, ValueError, TypeError) as e:
                errors.append(f"Row {i}: {e}")

        error_rate = len(errors) / max(len(rows), 1)
        if error_rate > 0.05:
            escalation_needed = True
            self.escalations.append(Escalation(
                reason=EscalationReason.PARSE_ERROR,
                description=f"Parse error rate {error_rate:.1%} exceeds 5% threshold",
                context={"errors": errors[:10], "total_errors": len(errors)},
            ))

        return {
            "status": "escalated" if escalation_needed else "success",
            "ingested": ingested,
            "duplicates_skipped": duplicates,
            "errors": errors,
            "error_rate": error_rate,
            "escalation": self.escalations[-1].model_dump() if escalation_needed else None,
        }

    # ── CAP-02: reconcile_entries ──────────────────────────────────────────

    def reconcile_entries(self, tolerance_amount: float = 0.01) -> dict[str, Any]:
        """Match bank transactions against ledger entries.

        Returns: reconciliation report + suggestions for unmatched items.
        """
        unmatched_bank: list[Transaction] = []
        unmatched_ledger: list[JournalEntry] = []
        suggestions: list[dict[str, Any]] = []
        matched_count = 0

        ledger_pool = [e for e in self.ledger_entries if e.status != EntryStatus.MATCHED]
        bank_pool = [t for t in self.transactions if t.status == EntryStatus.PENDING]

        for txn in bank_pool:
            best_match: JournalEntry | None = None
            best_confidence = 0.0
            match_method = ""

            for entry in ledger_pool:
                confidence = 0.0
                method_parts = []

                # Amount match (bank uses negative for outflows, ledger uses positive)
                if abs(abs(txn.amount) - entry.amount) <= tolerance_amount:
                    confidence += 0.5
                    method_parts.append("amount")

                # Date match (same day or +/- 1 day)
                if entry.date == txn.date:
                    confidence += 0.3
                    method_parts.append("date_exact")
                elif abs((entry.date - txn.date).days) <= 1:
                    confidence += 0.15
                    method_parts.append("date_near")

                # Reference match
                if txn.reference and txn.reference in entry.description:
                    confidence += 0.2
                    method_parts.append("reference")

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = entry
                    match_method = "+".join(method_parts)

            if best_match and best_confidence >= self.match_confidence_threshold:
                txn.status = EntryStatus.MATCHED
                best_match.status = EntryStatus.MATCHED
                ledger_pool.remove(best_match)
                self.matches.append(MatchResult(
                    bank_transaction_id=txn.id,
                    ledger_entry_id=best_match.id,
                    confidence=best_confidence,
                    method=match_method,
                ))
                matched_count += 1
            elif best_match and best_confidence >= 0.3:
                txn.status = EntryStatus.SUGGESTED
                suggestions.append({
                    "bank_transaction_id": txn.id,
                    "suggested_ledger_id": best_match.id,
                    "confidence": best_confidence,
                    "method": match_method,
                    "bank_desc": txn.description,
                    "ledger_desc": best_match.description,
                    "amount_diff": abs(txn.amount - best_match.amount),
                })
            else:
                txn.status = EntryStatus.UNMATCHED
                unmatched_bank.append(txn)

        unmatched_ledger = [e for e in ledger_pool if e.status != EntryStatus.MATCHED]

        total_items = len(bank_pool)
        match_rate = matched_count / max(total_items, 1)

        escalation_needed = match_rate < 0.8
        if escalation_needed:
            self.escalations.append(Escalation(
                reason=EscalationReason.LOW_CONFIDENCE_MATCH,
                description=f"Match rate {match_rate:.1%} is below 80% threshold",
                context={"match_rate": match_rate, "unmatched_count": len(unmatched_bank)},
            ))

        report = ReconciliationReport(
            period="current",
            total_bank=len(bank_pool),
            total_ledger=len(self.ledger_entries),
            matched=matched_count,
            unmatched_bank=len(unmatched_bank),
            unmatched_ledger=len(unmatched_ledger),
            suggestions=len(suggestions),
            match_rate=match_rate,
        )

        return {
            "status": "escalated" if escalation_needed else "success",
            "report": report.model_dump(),
            "suggestions": suggestions,
            "unmatched_bank": [t.model_dump() for t in unmatched_bank[:20]],
            "escalation": self.escalations[-1].model_dump() if escalation_needed else None,
        }

    # ── CAP-03: draft_adjustments ──────────────────────────────────────────

    def draft_adjustments(self, adjustments: list[dict[str, Any]]) -> dict[str, Any]:
        """Create draft adjustment entries. Posts immediately if below threshold,
        otherwise escalates for human approval.

        Each adjustment: {debit_account, credit_account, amount, description, date}
        """
        posted = 0
        pending_approval: list[JournalEntry] = []
        errors: list[str] = []

        for i, adj in enumerate(adjustments):
            try:
                amount = float(adj["amount"])
                debit = str(adj["debit_account"])
                credit = str(adj["credit_account"])
                desc = str(adj.get("description", f"Adjustment {i+1}"))
                entry_date = adj.get("date", date.today().isoformat())
                if isinstance(entry_date, str):
                    entry_date = date.fromisoformat(entry_date)

                if debit == credit:
                    errors.append(f"Adjustment {i}: debit and credit accounts cannot be the same")
                    continue

                if amount <= 0:
                    errors.append(f"Adjustment {i}: amount must be positive")
                    continue

                entry = JournalEntry(
                    date=entry_date,
                    debit_account=debit,
                    credit_account=credit,
                    amount=amount,
                    description=desc,
                )

                if amount > self.approval_threshold:
                    entry.status = EntryStatus.PENDING
                    pending_approval.append(entry)
                    self.escalations.append(Escalation(
                        reason=EscalationReason.AMOUNT_ABOVE_THRESHOLD,
                        description=f"Adjustment of {amount} exceeds threshold {self.approval_threshold}",
                        context={"entry_id": entry.id, "amount": amount, "description": desc},
                    ))
                else:
                    entry.status = EntryStatus.POSTED
                    entry.posted_at = datetime.utcnow()
                    entry.approved_by = "auto"
                    posted += 1

                self.ledger_entries.append(entry)

            except (KeyError, ValueError, TypeError) as e:
                errors.append(f"Adjustment {i}: {e}")

        return {
            "status": "escalated" if pending_approval else "success",
            "posted": posted,
            "pending_approval": [e.model_dump() for e in pending_approval],
            "errors": errors,
        }

    def approve_adjustment(self, entry_id: str, approved_by: str) -> dict[str, Any]:
        """Human approves a pending adjustment entry."""
        for entry in self.ledger_entries:
            if entry.id == entry_id and entry.status == EntryStatus.PENDING:
                entry.status = EntryStatus.POSTED
                entry.approved_by = approved_by
                entry.posted_at = datetime.utcnow()
                return {"status": "approved", "entry_id": entry_id}
        return {"status": "error", "message": f"Entry {entry_id} not found or not pending"}

    def reject_adjustment(self, entry_id: str, reason: str) -> dict[str, Any]:
        """Human rejects a pending adjustment entry."""
        for entry in self.ledger_entries:
            if entry.id == entry_id and entry.status == EntryStatus.PENDING:
                entry.status = EntryStatus.REJECTED
                return {"status": "rejected", "entry_id": entry_id, "reason": reason}
        return {"status": "error", "message": f"Entry {entry_id} not found or not pending"}

    # ── CAP-04: generate_trial_balance ─────────────────────────────────────

    def generate_trial_balance(self, year: int, month: int) -> dict[str, Any]:
        """Generate trial balance for the period."""
        period_key = self._period_key(year, month)
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)

        balances: dict[str, float] = {}

        for entry in self.ledger_entries:
            if entry.status != EntryStatus.POSTED:
                continue
            if not (period_start <= entry.date < period_end):
                continue

            balances.setdefault(entry.debit_account, 0.0)
            balances.setdefault(entry.credit_account, 0.0)
            balances[entry.debit_account] += entry.amount
            balances[entry.credit_account] -= entry.amount

        accounts = []
        total_debits = 0.0
        total_credits = 0.0

        for acct, balance in sorted(balances.items()):
            acct_name = self.chart_of_accounts.get(acct, acct)
            debit = balance if balance > 0 else 0.0
            credit = -balance if balance < 0 else 0.0
            total_debits += debit
            total_credits += credit
            accounts.append({
                "account_code": acct,
                "account_name": acct_name,
                "debit": round(debit, 2),
                "credit": round(credit, 2),
            })

        balanced = abs(total_debits - total_credits) < 0.01

        tb = TrialBalance(
            period=period_key,
            generated_at=datetime.utcnow(),
            accounts=accounts,
            total_debits=round(total_debits, 2),
            total_credits=round(total_credits, 2),
            balanced=balanced,
        )

        if not balanced:
            self.escalations.append(Escalation(
                reason=EscalationReason.IMBALANCED_ENTRY,
                description=f"Trial balance imbalanced: debits={total_debits:.2f} credits={total_credits:.2f}",
                context={"difference": round(total_debits - total_credits, 2)},
            ))

        return {
            "status": "escalated" if not balanced else "success",
            "trial_balance": tb.model_dump(),
            "escalation": self.escalations[-1].model_dump() if not balanced else None,
        }

    # ── CAP-05: close_period ───────────────────────────────────────────────

    def request_period_close(self, year: int, month: int) -> dict[str, Any]:
        """Prepare period for closing. Always escalates — human must approve."""
        period = self.get_or_create_period(year, month)
        period_key = self._period_key(year, month)

        # Check prerequisites
        blockers: list[str] = []

        pending_entries = [e for e in self.ledger_entries if e.status == EntryStatus.PENDING]
        if pending_entries:
            blockers.append(f"{len(pending_entries)} unapproved entries")

        unmatched = [t for t in self.transactions if t.status == EntryStatus.UNMATCHED]
        if unmatched:
            blockers.append(f"{len(unmatched)} unreconciled transactions")

        # Check trial balance
        tb_result = self.generate_trial_balance(year, month)
        if not tb_result["trial_balance"]["balanced"]:
            blockers.append("Trial balance is not balanced")

        if blockers:
            return {
                "status": "blocked",
                "blockers": blockers,
                "message": "Cannot close period — resolve blockers first",
            }

        self.escalations.append(Escalation(
            reason=EscalationReason.PERIOD_CLOSE_APPROVAL,
            description=f"Period {period_key} ready for close — human approval required",
            context={"period": period_key, "year": year, "month": month},
        ))

        return {
            "status": "awaiting_approval",
            "period": period_key,
            "escalation": self.escalations[-1].model_dump(),
            "summary": {
                "total_transactions": len([t for t in self.transactions]),
                "total_entries": len([e for e in self.ledger_entries if e.status == EntryStatus.POSTED]),
                "trial_balance_balanced": True,
            },
        }

    def confirm_period_close(self, year: int, month: int, approved_by: str) -> dict[str, Any]:
        """Human confirms period close."""
        period = self.get_or_create_period(year, month)

        if period.status == PeriodStatus.CLOSED:
            return {"status": "error", "message": "Period already closed"}

        period.status = PeriodStatus.CLOSED
        period.closed_at = datetime.utcnow()
        period.closed_by = approved_by

        return {
            "status": "closed",
            "period": self._period_key(year, month),
            "closed_at": period.closed_at.isoformat(),
            "closed_by": approved_by,
        }

    # ── Query helpers ──────────────────────────────────────────────────────

    def get_escalations(self, unresolved_only: bool = True) -> list[dict[str, Any]]:
        if unresolved_only:
            return [e.model_dump() for e in self.escalations if not e.resolved]
        return [e.model_dump() for e in self.escalations]

    def get_period_status(self, year: int, month: int) -> dict[str, Any]:
        period = self.get_or_create_period(year, month)
        return period.model_dump()
