"""
Momento — Pipeline
The quiet layer that wires all three engines together.

Input:  raw SMS string
Output: structured Transaction + whispers
"""

from engine.parser import parse_sms
from engine.classifier import classify_with_confidence
from engine.behaviour import BehaviourEngine, Transaction


# One shared behaviour engine instance (in-memory for now)
_engine = BehaviourEngine()


def process_sms(sms: str) -> dict:
    """
    Full pipeline: raw SMS → structured transaction → whispers.
    Returns a clean result dict ready for the interface.
    """

    # ── Layer 01: Parse ────────────────────────────────────────────────────
    raw = parse_sms(sms)

    if raw is None:
        return {
            "success": False,
            "error": "Could not parse this SMS. Bank format may not be supported yet.",
            "raw": sms,
        }

    # ── Layer 02: Classify ─────────────────────────────────────────────────
    category, cat_confidence = classify_with_confidence(raw.merchant)

    # ── Assemble transaction ───────────────────────────────────────────────
    txn = Transaction(
        bank=raw.bank,
        amount=raw.amount,
        merchant=raw.merchant,
        category=category,
        time=raw.time,
        date=raw.date,
        balance_after=raw.balance_after,
        card_last4=raw.card_last4,
    )

    # ── Layer 03: Behaviour ────────────────────────────────────────────────
    _engine.add(txn)
    whispers = _engine.whispers(txn)

    return {
        "success": True,
        "transaction": {
            "bank":          txn.bank,
            "amount":        txn.amount,
            "merchant":      txn.merchant,
            "category":      txn.category,
            "time":          txn.time,
            "date":          txn.date,
            "balance_after": txn.balance_after,
            "card_last4":    txn.card_last4,
        },
        "confidence": {
            "parse":    raw.confidence,
            "classify": cat_confidence,
        },
        "whispers": [
            {"message": w.message, "severity": w.severity}
            for w in whispers
        ],
    }


def get_summary() -> dict:
    return _engine.monthly_summary()


def reset():
    """Clear the in-memory engine — useful for testing."""
    global _engine
    _engine = BehaviourEngine()
