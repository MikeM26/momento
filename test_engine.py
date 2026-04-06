"""
Momento — Test Suite
Real SA bank SMS formats. Run this to see the engine in action.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import process_sms, get_summary, reset

# ─── Real-world SA bank SMS samples ───────────────────────────────────────────

TEST_SMS = [
    # FNB
    "FNB: R450.00 spent at WOOLWORTHS FOOD 14:23. Avail bal: R12,340.00",
    "FNB: R680.00 spent at ENGEN SANDTON 11:08. Avail bal: R11,660.00",
    "FNB: R52.00 spent at VIDA E CAFFE 08:41. Avail bal: R11,608.00",
    "FNB: R52.00 spent at VIDA E CAFFE 09:15. Avail bal: R11,556.00",
    "FNB: R52.00 spent at VIDA E CAFFE 08:30. Avail bal: R11,504.00",

    # Absa
    "ABSA: R199.00 purchased at NETFLIX on 2026/04/06 at 00:00. Balance: R8,200.00",
    "ABSA: R320.00 purchased at CHECKERS HYPER on 2026/04/06 at 16:44. Balance: R7,880.00",

    # Nedbank
    "Nedbank: Card purchase R89.00 SPOTIFY 00:00 2026-04-06. Available R5,400.00",
    "Nedbank: Card purchase R1200.00 VIRGIN ACTIVE 07:00 2026-04-06. Available R4,200.00",

    # Standard Bank
    "Standard Bank: Purchase R95.00 at NANDOS SANDTON 19:30. Available R3,100.00",

    # Capitec
    "Capitec: R299.00 paid to TAKEALOT. 13:22. Balance R2,840.00",
    "Capitec: Purchase R450 PICK N PAY 17:10 Avail Bal R2,390.00",
]


def run_tests():
    reset()

    print("\n" + "─" * 60)
    print("  MOMENTO — PARSING ENGINE TEST")
    print("─" * 60)

    passed = 0
    failed = 0

    for sms in TEST_SMS:
        result = process_sms(sms)
        print(f"\n  SMS: {sms[:55]}{'...' if len(sms) > 55 else ''}")

        if result["success"]:
            t = result["transaction"]
            print(f"  ✓  {t['bank']} | {t['merchant']} | R {t['amount']:,.2f} | {t['category']}")
            if t["time"]:
                print(f"     Time: {t['time']}  |  Balance after: R {t['balance_after']:,.2f}" if t["balance_after"] else f"     Time: {t['time']}")
            conf = result["confidence"]
            print(f"     Parse confidence: {conf['parse']:.0%}  |  Classify confidence: {conf['classify']:.0%}")
            if result["whispers"]:
                for w in result["whispers"]:
                    print(f"     💬 {w['message']}")
            passed += 1
        else:
            print(f"  ✗  FAILED — {result['error']}")
            failed += 1

    # ── Monthly summary ────────────────────────────────────────────────────
    summary = get_summary()
    print("\n" + "─" * 60)
    print("  MONTHLY SUMMARY")
    print("─" * 60)
    print(f"  Total spend:       R {summary['total']:,.2f}")
    print(f"  Transactions:      {summary['transaction_count']}")
    print(f"  Largest category:  {summary['largest_category']}")
    print("\n  Category breakdown:")
    for cat, total in summary["category_breakdown"].items():
        pct = (total / summary["total"] * 100) if summary["total"] else 0
        bar = "█" * int(pct / 4)
        print(f"    {cat:<18} R {total:>8,.2f}  {bar} {pct:.0f}%")

    print("\n  Top merchants:")
    for merchant, count, total in summary["top_merchants"]:
        print(f"    {merchant:<22} {count}×   R {total:,.2f}")

    print("\n" + "─" * 60)
    print(f"  Tests passed: {passed}/{passed + failed}")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    run_tests()
