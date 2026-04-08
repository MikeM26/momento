"""
Momento — Production Parser v2
Zero-tolerance accuracy. Every valid bank message becomes a clean transaction.
"""

import re
import hashlib
from dataclasses import dataclass
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
    confidence: float
    txn_type: str
    currency: str
    txn_hash: str
    is_reversal: bool
    original_merchant: str


# ─── Currency ─────────────────────────────────────────────────────────────────

def _detect_currency(sms: str) -> str:
    if re.search(r'\$\s?[\d]|USD', sms): return 'USD'
    if re.search(r'EUR|€\s?[\d]', sms):  return 'EUR'
    if re.search(r'GBP|£\s?[\d]', sms):  return 'GBP'
    return 'ZAR'

# ─── Transaction type ─────────────────────────────────────────────────────────

REVERSAL_RE = re.compile(r'\b(reversal|reversed|refund|returned|cancelled|void)\b', re.IGNORECASE)
CREDIT_RE   = re.compile(r'\b(credit|deposit|received|transfer in|salary|cashback)\b', re.IGNORECASE)

def _detect_txn_type(sms: str):
    if REVERSAL_RE.search(sms): return 'reversal', True
    if CREDIT_RE.search(sms):   return 'credit', False
    return 'debit', False

# ─── Merchant normalisation ───────────────────────────────────────────────────

MERCHANT_MAP = [
    # Fuel
    (r'engen',             'Engen'),
    (r'shell\b',           'Shell'),
    (r'sasol\b',           'Sasol'),
    (r'caltex',            'Caltex'),
    (r'\bbp\b',            'BP'),
    (r'total\s+garage',    'Total Garage'),
    (r'astron',            'Astron Energy'),
    # Groceries
    (r'woolworths\s+food', 'Woolworths Food'),
    (r'woolworths',        'Woolworths'),
    (r'pick\s*n\s*pay|pnp\b', 'Pick n Pay'),
    (r'checkers\s+hyper',  'Checkers Hyper'),
    (r'checkers',          'Checkers'),
    (r'shoprite',          'Shoprite'),
    (r'spar\b',            'Spar'),
    (r'food\s+lover',      "Food Lover's Market"),
    (r'boxer',             'Boxer'),
    # Food & drink
    (r'mcdonalds|mcdonald', "McDonald's"),
    (r'\bkfc\b',           'KFC'),
    (r'steers\b',          'Steers'),
    (r'nandos',            "Nando's"),
    (r'wimpy\b',           'Wimpy'),
    (r'vida\s*e\s*caff',   'Vida e Caffè'),
    (r'starbucks',         'Starbucks'),
    (r'ocean\s+basket',    'Ocean Basket'),
    (r'spur\b',            'Spur'),
    (r'mugg.*bean',        'Mugg & Bean'),
    (r'uber.*eats',        'Uber Eats'),
    (r'mr\s+delivery',     'Mr D Food'),
    # Subscriptions
    (r'netflix',           'Netflix'),
    (r'spotify',           'Spotify'),
    (r'showmax',           'Showmax'),
    (r'dstv',              'DStv'),
    (r'apple\.com',        'Apple'),
    (r'google\s+play',     'Google Play'),
    (r'amazon\s+prime',    'Amazon Prime'),
    (r'youtube\s+premium', 'YouTube Premium'),
    (r'microsoft',         'Microsoft'),
    (r'adobe',             'Adobe'),
    # Retail
    (r'takealot',          'Takealot'),
    (r'mr\s*price',        'Mr Price'),
    (r'truworths',         'Truworths'),
    (r'foschini',          'Foschini'),
    (r'\bzara\b',          'Zara'),
    (r'h\s*&\s*m',         'H&M'),
    (r'cotton\s+on',       'Cotton On'),
    # Health
    (r'dis[-\s]*chem',     'Dis-Chem'),
    (r'\bclicks\b',        'Clicks'),
    (r'virgin\s+active',   'Virgin Active'),
    (r'planet\s+fitness',  'Planet Fitness'),
    # Transport
    (r'\buber\b',          'Uber'),
    (r'\bbolt\b',          'Bolt'),
    (r'gautrain',          'Gautrain'),
    # Telecoms
    (r'vodacom',           'Vodacom'),
    (r'\bmtn\b',           'MTN'),
    (r'cell\s*c\b',        'Cell C'),
    (r'telkom',            'Telkom'),
    (r'\brain\b',          'Rain'),
]

NOISE_RE = re.compile(
    r'(\*+\d+|#\d+|\b(pty|ltd|pty\s+ltd|cc)\b|\b(rsa|za)\b|\d{6,}|\s{2,})',
    re.IGNORECASE
)

def _normalise_merchant(raw: str) -> str:
    cleaned = NOISE_RE.sub(' ', raw).strip().rstrip('.,;:')
    lower   = cleaned.lower()
    for pattern, name in MERCHANT_MAP:
        if re.search(pattern, lower, re.IGNORECASE):
            return name
    words = cleaned.split()
    if not words:
        return 'Unknown'
    return ' '.join(w.capitalize() for w in words[:5])

# ─── Amount ───────────────────────────────────────────────────────────────────

def _clean_amount(raw: str) -> float:
    c = raw.strip().replace(' ', '')
    if ',' in c and '.' in c:
        c = c.replace(',', '')
    elif ',' in c:
        comma_pos = c.rfind(',')
        if len(c) - comma_pos - 1 <= 2:
            c = c.replace(',', '.')
        else:
            c = c.replace(',', '')
    try:
        return abs(float(c))
    except ValueError:
        return 0.0

# ─── Dedup ────────────────────────────────────────────────────────────────────

def _make_hash(bank, amount, merchant, time, date) -> str:
    key = f"{bank}|{amount:.2f}|{merchant.lower()}|{time or ''}|{date or ''}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

# ─── Bank detection ───────────────────────────────────────────────────────────

def _detect_bank(sms: str) -> Optional[str]:
    u = sms.upper()
    if re.search(r'\bFNB\b', u):                             return 'FNB'
    if re.search(r'\bABSA\b', u):                            return 'Absa'
    if re.search(r'\bNEDBANK\b', u):                         return 'Nedbank'
    if re.search(r'\bSTANDARD\s+BANK\b|\bSTDBANK\b', u):    return 'Standard Bank'
    if re.search(r'\bCAPITEC\b', u):                         return 'Capitec'
    if re.search(r'\bINVESTEC\b', u):                        return 'Investec'
    if re.search(r'\bDISCOVERY\b', u):                       return 'Discovery Bank'
    if re.search(r'\bTYMEBANK\b', u):                        return 'TymeBank'
    return None

# ─── Non-transaction filter ───────────────────────────────────────────────────

NON_TXN_RE = re.compile(
    r'\b(otp|one.time|verify|verification|fraud.alert|security.alert|'
    r'do not share|never share|your.pin|passcode|service message|'
    r'system notification|maintenance|login|sign.in)\b',
    re.IGNORECASE
)

def _is_non_transaction(sms: str) -> bool:
    return bool(NON_TXN_RE.search(sms))

# ─── Bank patterns ────────────────────────────────────────────────────────────

BANK_PATTERNS = {
    "FNB": [
        re.compile(r"FNB[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+ATM\s+withdrawal\s+at\s+(.+?)\s+(\d{1,2}:\d{2}).*?bal[:\s]*R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"FNB[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+spent at\s+(.+?)\s+(\d{1,2}:\d{2}).*?bal[:\s]*R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"FNB[:\s].*?[Pp]urch.*?-?R\s?([\d,\s]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"FNB[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+(?:paid|transferred)\s+(?:to|from)\s+(.+?)\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
    ],
    "Absa": [
        re.compile(r"Absa[:\s].*?[Pp][Oo][Ss]\s+[Pp]urchase\s+-?R\s?([\d,\s]+\.?\d*)\s+@\s+(.+?)\s+on\s+([\d-]+).*?[Bb]al[:\s]*R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"ABSA[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+purchased at\s+(.+?)\s+on\s+(\d{4}/\d{2}/\d{2}).*?[Bb]alance[:\s]*R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Absa[:\s].*?[Ss]wipe\s+-?R\s?([\d,\s]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
    ],
    "Nedbank": [
        re.compile(r"Nedbank[:\s].*?[Cc]ard purchase\s+-?R\s?([\d,\s]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2}).*?Available\s+R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"[Nn]ed[Bb]ank[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+deducted\s+(.+?)\s+(\d{1,2}:\d{2}).*?[Bb]al\s+R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Nedbank[:\s].*?Transaction\s+-?R\s?([\d,\s]+\.?\d*).*?at\s+(.+?)\s+on\s+(\d{2}/\d{2}/\d{2}).*?Available\s+R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
    ],
    "Standard Bank": [
        re.compile(r"Standard Bank[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+paid from\s+Acc\.+\d+\s+to\s+(.+?)\s+@\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"(?:Standard Bank|StdBank)[:\s].*?[Pp]urchase\s+-?R\s?([\d,\s]+\.?\d*)\s+at\s+(.+?)\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
    ],
    "Capitec": [
        re.compile(r"Capitec[:\s].*?-?R\s?([\d,\s]+\.?\d*).*?[Rr]ef\s+(.+?);", re.IGNORECASE),
        re.compile(r"Capitec[:\s].*?-?R\s?([\d,\s]+\.?\d*)\s+paid to\s+(.+?)[.\s]+(\d{1,2}:\d{2}).*?[Bb]alance\s+R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Capitec[:\s].*?[Pp]urchase\s+-?R\s?([\d,\s]+\.?\d*)\s+(.+?)\s+(\d{1,2}:\d{2}).*?R\s?([\d,\s]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Capitec[:\s].*?Payment\s+-?R\s?([\d,\s]+\.?\d*)\s+to\s+(.+?)\s+\(Card\s+(\d{4})\)", re.IGNORECASE),
    ],
}

GENERIC_AMOUNT = re.compile(r'-?R\s?([\d,\s]+\.?\d{0,2})', re.IGNORECASE)
GENERIC_TIME   = re.compile(r'\b(\d{1,2}:\d{2})\b')
GENERIC_DATE   = re.compile(r'\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{2,4})\b')

def _extract_merchant_generic(sms: str, bank: str) -> str:
    text = re.sub(rf'\b{re.escape(bank)}\b[:\s]*', '', sms, flags=re.IGNORECASE)
    text = re.sub(r'-?R\s?[\d,\s]+\.?\d*', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d{1,2}:\d{2}\b', ' ', text)
    text = re.sub(r'\b\d{2,4}[-/]\d{2}[-/]\d{2,4}\b', ' ', text)
    text = re.sub(r'\b(spent|at|avail|bal|balance|available|card|account|acc|from|to|purch|purchase|payment|ref|trn)\b', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'[.,;:\*#\-_/\\]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    words = [w for w in text.split() if len(w) > 2 and not w.isdigit()]
    return ' '.join(words[:4]) if words else 'Unknown'

# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_sms(sms: str) -> Optional[RawTransaction]:
    sms  = sms.strip()
    if _is_non_transaction(sms):
        return None

    bank     = _detect_bank(sms)
    currency = _detect_currency(sms)
    today    = datetime.today().strftime('%Y-%m-%d')

    if bank and bank in BANK_PATTERNS:
        for pattern in BANK_PATTERNS[bank]:
            match = pattern.search(sms)
            if not match:
                continue
            groups = match.groups()
            try:
                amount = _clean_amount(groups[0])
                if amount <= 0:
                    continue

                merchant_raw  = groups[1] if len(groups) > 1 else ''
                time_str      = groups[2] if len(groups) > 2 else None
                balance_raw   = groups[-1] if len(groups) > 3 else None
                balance_after = _clean_amount(balance_raw) if balance_raw else None
                if balance_after == 0:
                    balance_after = None

                card_match = re.search(r'[Cc]ard\s+(\d{4})', sms)
                card_last4 = card_match.group(1) if card_match else None

                original = merchant_raw.strip()
                merchant = _normalise_merchant(original)

                txn_type, is_reversal = _detect_txn_type(sms)

                date_match = GENERIC_DATE.search(sms)
                txn_date   = date_match.group(1) if date_match else today

                # Fix time if it captured date instead
                if time_str and re.match(r'\d{4}[/-]', time_str):
                    times = GENERIC_TIME.findall(sms)
                    time_str = times[0] if times else None

                return RawTransaction(
                    bank=bank, amount=amount, merchant=merchant,
                    time=time_str, date=txn_date,
                    balance_after=balance_after, card_last4=card_last4,
                    raw=sms, confidence=0.95,
                    txn_type=txn_type, currency=currency,
                    txn_hash=_make_hash(bank, amount, merchant, time_str, txn_date),
                    is_reversal=is_reversal, original_merchant=original,
                )
            except (IndexError, ValueError):
                continue

    # Fallback
    if bank:
        amounts = GENERIC_AMOUNT.findall(sms)
        times   = GENERIC_TIME.findall(sms)
        dates   = GENERIC_DATE.findall(sms)
        if amounts:
            amount = _clean_amount(amounts[0])
            if amount <= 0:
                return None
            balance_after = _clean_amount(amounts[-1]) if len(amounts) > 1 else None
            merchant_raw  = _extract_merchant_generic(sms, bank)
            merchant      = _normalise_merchant(merchant_raw)
            time_str      = times[0] if times else None
            txn_date      = dates[0] if dates else today
            txn_type, is_reversal = _detect_txn_type(sms)
            return RawTransaction(
                bank=bank, amount=amount, merchant=merchant,
                time=time_str, date=txn_date,
                balance_after=balance_after, card_last4=None,
                raw=sms, confidence=0.65,
                txn_type=txn_type, currency=currency,
                txn_hash=_make_hash(bank, amount, merchant, time_str, txn_date),
                is_reversal=is_reversal, original_merchant=merchant_raw,
            )

    return None
