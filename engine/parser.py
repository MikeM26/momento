"""
Momento — Parsing Engine
Layer 01: Reads raw SMS text, identifies the bank,
extracts amount, merchant, time, card, and balance.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RawTransaction:
    bank: str
    amount: float
    merchant: str
    time: Optional[str]
    date: Optional[str]
    balance_after: Optional[float]
    card_last4: Optional[str]
    raw: str
    confidence: float  # 0.0 - 1.0


# ─── Bank SMS patterns ─────────────────────────────────────────────────────────

BANK_PATTERNS = {

    "FNB": [
        # "FNB: R450.00 spent at WOOLWORTHS FOOD 14:23. Avail bal: R12,340.00"
        re.compile(
            r"FNB[:\s].*?R\s?([\d,]+\.?\d*)\s+spent at\s+(.+?)\s+(\d{1,2}:\d{2})"
            r".*?bal[:\s]*R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
        # "FNB: Purch. R450.00 WOOLWORTHS FOOD 14:23 Card 4821 Avail R12,340.00"
        re.compile(
            r"FNB[:\s].*?[Pp]urch.*?R\s?([\d,]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2})"
            r".*?Card\s+(\d{4}).*?R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
    ],

    "Absa": [
        # "ABSA: R680.00 purchased at ENGEN GARAGE on 2026/04/06 at 11:08. Balance: R8,200.00"
        re.compile(
            r"ABSA[:\s].*?R\s?([\d,]+\.?\d*)\s+purchased at\s+(.+?)\s+on\s+"
            r"(\d{4}/\d{2}/\d{2})\s+at\s+(\d{1,2}:\d{2}).*?[Bb]alance[:\s]*R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
        # "Absa: Swipe R680.00 ENGEN GARAGE 11:08 Avail R8,200.00"
        re.compile(
            r"Absa[:\s].*?[Ss]wipe\s+R\s?([\d,]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2})"
            r".*?Avail\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
    ],

    "Nedbank": [
        # "Nedbank: Card purchase R199.00 NETFLIX.COM 00:00 2026-04-06. Available R5,400.00"
        re.compile(
            r"Nedbank[:\s].*?[Cc]ard purchase\s+R\s?([\d,]+\.?\d*)\s+(.+?)\s+"
            r"(\d{1,2}:\d{2}).*?Available\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
        # "NedBank: R199.00 deducted NETFLIX 00:00. Bal R5,400.00"
        re.compile(
            r"[Nn]ed[Bb]ank[:\s].*?R\s?([\d,]+\.?\d*)\s+deducted\s+(.+?)\s+"
            r"(\d{1,2}:\d{2}).*?[Bb]al\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
    ],

    "Standard Bank": [
        # "Standard Bank: R52.00 debited to acc. VIDA E CAFFE at 08:41. Bal R3,100.00"
        re.compile(
            r"Standard Bank[:\s].*?R\s?([\d,]+\.?\d*)\s+debited.*?IBAN\s+(.+?)\s+at\s+"
            r"(\d{1,2}:\d{2}).*?[Bb]al\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
        # "StdBank: Purchase R52.00 at VIDA E CAFFE 08:41. Available R3,100.00"
        re.compile(
            r"(?:Standard Bank|StdBank)[:\s].*?[Pp]urchase\s+R\s?([\d,]+\.?\d*)\s+at\s+"
            r"(.+?)\s+(\d{1,2}:\d{2}).*?Available\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
    ],

    "Capitec": [
        # "Capitec: Cashback Purchase -R1483.24 from SAVINGS ACCOUNT; Ref Shoprite Esselen Stree PRETORIA ZA; Avail..."
        re.compile(
            r"Capitec[:\s].*?-?R\s?([\d,]+\.?\d*).*?[Rr]ef\s+(.+?);",
            re.IGNORECASE
        ),
        # "Capitec: R199.00 paid to NETFLIX. 00:00. Balance R2,840.00"
        re.compile(
            r"Capitec[:\s].*?R\s?([\d,]+\.?\d*)\s+paid to\s+(.+?)[.\s]+(\d{1,2}:\d{2})"
            r".*?[Bb]alance\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
        # "Capitec: Purchase R199 NETFLIX 00:00 Avail Bal R2,840.00"
        re.compile(
            r"Capitec[:\s].*?[Pp]urchase\s+R\s?([\d,]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2})"
            r".*?(?:Avail(?:able)?(?:\s+Bal)?)\s+R\s?([\d,]+\.?\d*)",
            re.IGNORECASE
        ),
    ],
}


# ─── Generic fallback ──────────────────────────────────────────────────────────

GENERIC_AMOUNT = re.compile(r"R\s?([\d,]+\.?\d*)", re.IGNORECASE)
GENERIC_TIME   = re.compile(r"\b(\d{1,2}:\d{2})\b")
GENERIC_CARD   = re.compile(r"\b(\d{4})\b")


def _clean_amount(raw: str) -> float:
    return float(raw.replace(",", ""))


def _clean_merchant(raw: str) -> str:
    cleaned = raw.strip().rstrip(".")
    return " ".join(word.capitalize() for word in cleaned.split())


def _detect_bank(sms: str) -> Optional[str]:
    sms_upper = sms.upper()
    if "FNB" in sms_upper:
        return "FNB"
    if "ABSA" in sms_upper:
        return "Absa"
    if "NEDBANK" in sms_upper or "NED BANK" in sms_upper:
        return "Nedbank"
    if "STANDARD BANK" in sms_upper or "STDBANK" in sms_upper:
        return "Standard Bank"
    if "CAPITEC" in sms_upper:
        return "Capitec"
    return None


# ─── Main parse function ───────────────────────────────────────────────────────

def parse_sms(sms: str) -> Optional[RawTransaction]:
    """
    Takes a raw bank SMS string.
    Returns a RawTransaction dataclass or None if unparseable.
    """
    sms = sms.strip()
    bank = _detect_bank(sms)

    if bank and bank in BANK_PATTERNS:
        for pattern in BANK_PATTERNS[bank]:
            match = pattern.search(sms)
            if match:
                groups = match.groups()

                # Different patterns yield different group orders
                # We extract by what we can find
                try:
                    amount        = _clean_amount(groups[0])
                    merchant      = _clean_merchant(groups[1])
                    time_str      = groups[2] if len(groups) > 2 else None
                    balance_raw   = groups[-1] if len(groups) > 3 else None
                    balance_after = _clean_amount(balance_raw) if balance_raw else None

                    # Card number: look for 4-digit sequence near "Card" keyword
                    card_match = re.search(r"[Cc]ard\s+(\d{4})", sms)
                    card_last4 = card_match.group(1) if card_match else None

                    return RawTransaction(
                        bank=bank,
                        amount=amount,
                        merchant=merchant,
                        time=time_str,
                        date=datetime.today().strftime("%Y-%m-%d"),
                        balance_after=balance_after,
                        card_last4=card_last4,
                        raw=sms,
                        confidence=0.95,
                    )
                except (IndexError, ValueError):
                    continue

    # ── Fallback: generic extraction if bank detected but pattern missed ──
    if bank:
        amounts = GENERIC_AMOUNT.findall(sms)
        times   = GENERIC_TIME.findall(sms)

        if len(amounts) >= 1:
            amount = _clean_amount(amounts[0])
            balance_after = _clean_amount(amounts[-1]) if len(amounts) > 1 else None

            # Rough merchant: text between first amount and time
            merchant_raw = re.sub(r"R\s?[\d,]+\.?\d*", "", sms)
            merchant_raw = re.sub(r"\d{1,2}:\d{2}", "", merchant_raw)
            merchant_raw = re.sub(r"(FNB|ABSA|NEDBANK|STANDARD BANK|CAPITEC)[:\s]?", "", merchant_raw, flags=re.IGNORECASE)
            merchant_raw = re.sub(r"(spent at|purchased at|paid to|purchase|swipe|purch\.?|deducted|debited|card|avail|balance|bal)", "", merchant_raw, flags=re.IGNORECASE)
            merchant_raw = re.sub(r"[^a-zA-Z\s]", " ", merchant_raw).strip()
            merchant_parts = [w for w in merchant_raw.split() if len(w) > 2]
            merchant = _clean_merchant(" ".join(merchant_parts[:4])) if merchant_parts else "Unknown"

            return RawTransaction(
                bank=bank,
                amount=amount,
                merchant=merchant,
                time=times[0] if times else None,
                date=datetime.today().strftime("%Y-%m-%d"),
                balance_after=balance_after,
                card_last4=None,
                raw=sms,
                confidence=0.60,
            )

    return None
