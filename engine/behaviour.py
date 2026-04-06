"""
Momento — Behaviour Engine
Layer 03: Tracks patterns, detects anomalies, generates whispers.
It watches. It never shouts.
"""

from dataclasses import dataclass
from typing import Optional
from collections import defaultdict, Counter


@dataclass
class Transaction:
    bank: str
    amount: float
    merchant: str
    category: str
    time: Optional[str]
    date: Optional[str]
    balance_after: Optional[float]
    card_last4: Optional[str]


@dataclass
class Whisper:
    """A single quiet insight. Never an alert. Never a lecture."""
    message: str
    category: Optional[str] = None
    severity: str = "info"  # info | watch | note


class BehaviourEngine:
    """
    Holds a session of transactions and surfaces insights.
    In production this would be backed by a database.
    Here it runs in memory — enough to see the intelligence work.
    """

    def __init__(self):
        self.transactions: list[Transaction] = []

    def add(self, txn: Transaction):
        self.transactions.append(txn)

    def merchant_frequency(self, merchant: str) -> int:
        """How many times has this merchant appeared this month?"""
        m = merchant.lower()
        return sum(1 for t in self.transactions if t.merchant.lower() == m)

    def category_total(self, category: str) -> float:
        """Total spend in a category across all loaded transactions."""
        return sum(t.amount for t in self.transactions if t.category == category)

    def total_spend(self) -> float:
        return sum(t.amount for t in self.transactions)

    def category_breakdown(self) -> dict[str, float]:
        breakdown = defaultdict(float)
        for t in self.transactions:
            breakdown[t.category] += t.amount
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    def top_merchants(self, n: int = 5) -> list[tuple[str, int, float]]:
        """Returns [(merchant, count, total_spend)] sorted by total spend."""
        merchant_data = defaultdict(lambda: {"count": 0, "total": 0.0})
        for t in self.transactions:
            merchant_data[t.merchant]["count"] += 1
            merchant_data[t.merchant]["total"] += t.amount
        return sorted(
            [(m, d["count"], d["total"]) for m, d in merchant_data.items()],
            key=lambda x: x[2],
            reverse=True
        )[:n]

    def whispers(self, latest_txn: Transaction) -> list[Whisper]:
        """
        Generate zero or more whispers based on the latest transaction
        and the full transaction history.
        Quiet. Precise. Never alarmist.
        """
        results = []

        # ── Merchant frequency whisper ─────────────────────────────────────
        freq = self.merchant_frequency(latest_txn.merchant)
        if freq >= 5:
            results.append(Whisper(
                message=f"You've been to {latest_txn.merchant} {freq} times this month.",
                category=latest_txn.category,
                severity="note",
            ))
        elif freq >= 3:
            results.append(Whisper(
                message=f"{latest_txn.merchant} again — {freq} visits this month.",
                category=latest_txn.category,
                severity="info",
            ))

        # ── Category spend whisper ─────────────────────────────────────────
        cat_total = self.category_total(latest_txn.category)
        total = self.total_spend()

        if total > 0:
            cat_pct = (cat_total / total) * 100
            if cat_pct > 40 and latest_txn.category not in ("Groceries", "Utilities"):
                results.append(Whisper(
                    message=f"{latest_txn.category} is {cat_pct:.0f}% of your spend this month.",
                    category=latest_txn.category,
                    severity="watch",
                ))

        # ── Large single transaction whisper ──────────────────────────────
        avg = total / len(self.transactions) if self.transactions else 0
        if avg > 0 and latest_txn.amount > avg * 3:
            results.append(Whisper(
                message=f"R {latest_txn.amount:,.0f} at {latest_txn.merchant} — "
                        f"well above your usual spend per transaction.",
                category=latest_txn.category,
                severity="watch",
            ))

        return results

    def monthly_summary(self) -> dict:
        breakdown = self.category_breakdown()
        top = self.top_merchants(3)
        total = self.total_spend()

        return {
            "total": total,
            "transaction_count": len(self.transactions),
            "category_breakdown": breakdown,
            "top_merchants": top,
            "largest_category": max(breakdown, key=breakdown.get) if breakdown else None,
        }
