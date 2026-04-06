"""
Momento — Classification Engine
Layer 02: Maps merchant names to categories.
Understands nuance — Woolworths Food ≠ Woolworths Clothing.
"""

import re
from typing import Optional


# ─── Category definitions ──────────────────────────────────────────────────────
# Order matters — more specific rules are listed first.

CATEGORY_RULES = [

    # ── Groceries ──────────────────────────────────────────────────────────────
    ("Groceries", [
        r"woolworths food", r"woolworths\s+food",
        r"pick\s*n\s*pay", r"pnp",
        r"checkers", r"shoprite",
        r"spar\b", r"superspar", r"kwikspar",
        r"food\s+lover", r"fruit\s+&?\s*veg",
        r"cambridge food",
        r"boxer\s+superstore", r"boxer\s+cash",
        r"esselen", r"pretoria\s+za",
    ]),

    # ── Transport & fuel ───────────────────────────────────────────────────────
    ("Transport", [
        r"engen", r"shell\b", r"sasol\b", r"caltex", r"bp\b",
        r"total\s+garage", r"astron",
        r"uber\b", r"bolt\b", r"taxify",
        r"gautrain", r"prasa",
        r"e-toll", r"sanral",
    ]),

    # ── Eating out ─────────────────────────────────────────────────────────────
    ("Eating out", [
        r"mcdonalds", r"mcdonald", r"kfc\b",
        r"steers\b", r"nando", r"wimpy\b",
        r"ocean basket", r"spur\b",
        r"vida\s+e\s+caff", r"vida\s+caffe", r"vida\b",
        r"starbucks", r"bootlegger",
        r"the\s+local",
        r"mugg\s*&?\s*bean",
        r"restaurant", r"bistro", r"kitchen\b", r"cafe\b", r"caf[eé]\b",
        r"pizza", r"burger", r"sushi", r"grill\b",
    ]),

    # ── Subscriptions ──────────────────────────────────────────────────────────
    ("Subscriptions", [
        r"netflix", r"spotify", r"apple\.com", r"apple\s+music",
        r"dstv", r"showmax",
        r"amazon\s+prime", r"amazon\.com",
        r"microsoft", r"google\s+one", r"google\s+play",
        r"adobe", r"canva",
        r"youtube\s+premium",
        r"hbo", r"disney\s*\+",
    ]),

    # ── Shopping & retail ──────────────────────────────────────────────────────
    ("Shopping", [
        r"woolworths\b",           # catches plain Woolworths (not Food)
        r"mr\s*price", r"mrp\b",
        r"jet\s+stores", r"\bjet\b",
        r"pep\s+stores", r"\bpep\b",
        r"truworths", r"foschini", r"tfg\b",
        r"zara\b", r"h&m\b", r"cotton\s+on",
        r"sportscene", r"totalsports",
        r"takealot", r"makro\b", r"game\s+stores",
        r"builders\s+warehouse", r"incredible\s+connection",
    ]),

    # ── Health & pharmacy ──────────────────────────────────────────────────────
    ("Health", [
        r"clicks\b", r"dischem", r"dis-chem",
        r"medirite", r"alphapharm",
        r"life\s+healthcare", r"netcare", r"mediclinic",
        r"pharmacy", r"chemist", r"clinic", r"hospital",
        r"gym\b", r"virgin\s+active", r"planet\s+fitness",
        r"wellness",
    ]),

    # ── Banking & finance ──────────────────────────────────────────────────────
    ("Finance", [
        r"fnb\b", r"absa\b", r"nedbank", r"standard\s+bank",
        r"capitec", r"investec", r"discovery\s+bank",
        r"african\s+bank",
        r"atm\b", r"cash\s+withdrawal",
        r"insurance", r"assurance", r"sanlam", r"old\s+mutual",
        r"momentum\b",
    ]),

    # ── Entertainment & lifestyle ──────────────────────────────────────────────
    ("Lifestyle", [
        r"ster\s*kinekor", r"nu\s*metro", r"cinema",
        r"computicket", r"ticketpro",
        r"bar\b", r"lounge\b", r"club\b",
        r"salon\b", r"hair\b", r"nails\b", r"spa\b",
        r"hotel\b", r"airbnb", r"booking\.com",
    ]),

    # ── Utilities & home ──────────────────────────────────────────────────────
    ("Utilities", [
        r"eskom", r"city\s+power",
        r"rand\s+water", r"city\s+of\s+johannesburg",
        r"telkom", r"mtn\b", r"vodacom", r"cell\s*c\b",
        r"rain\b",
        r"internet",
    ]),

    # ── Education ─────────────────────────────────────────────────────────────
    ("Education", [
        r"university", r"unisa", r"varsity",
        r"school\b", r"college\b",
        r"udemy", r"coursera", r"skillshare",
        r"textbook", r"bookshop",
    ]),

    # ── Cash & withdrawals ────────────────────────────────────────────────────
    ("Withdrawal", [
        r"atm\b", r"atm\s+withdrawal", r"cash\s+withdrawal",
        r"atm\s+cash", r"cash\s+advance",
        r"absa\s+atm", r"fnb\s+atm",
        r"nedbank\s+atm", r"capitec\s+atm", r"standard\s+bank\s+atm",
        r"withdrawal", r"cash\s+out", r"cash\s+at\s+till",
    ]),

    # ── Transfers & payments out ───────────────────────────────────────────────
    ("Transfer", [
        r"eft\b", r"instant\s+payment", r"interbank",
        r"transferred\s+to", r"payment\s+to",
        r"send\s+money", r"snapscan", r"zapper",
        r"ozow", r"peach\s+payments",
        r"bank\s+transfer", r"debit\s+order",
    ]),

    # ── Miscellaneous ──────────────────────────────────────────────────────────
    ("Miscellaneous", [
        r"fee\b", r"bank\s+fee", r"service\s+fee", r"monthly\s+fee",
        r"charge\b", r"admin\s+fee", r"penalty",
        r"interest\b", r"finance\s+charge",
        r"foreign\s+transaction", r"currency\s+conversion",
        r"reversal", r"refund", r"cashback",
    ]),
]


def classify_merchant(merchant: str) -> str:
    """
    Takes a cleaned merchant name string.
    Returns the best-matching category, or 'Other' if no match.
    """
    m = merchant.lower().strip()

    for category, patterns in CATEGORY_RULES:
        for pattern in patterns:
            if re.search(pattern, m, re.IGNORECASE):
                return category

    return "Other"


def classify_with_confidence(merchant: str) -> tuple[str, float]:
    """
    Returns (category, confidence).
    Exact pattern match = high confidence.
    Fallback = lower confidence.
    """
    m = merchant.lower().strip()

    for category, patterns in CATEGORY_RULES:
        for pattern in patterns:
            if re.search(pattern, m, re.IGNORECASE):
                return category, 0.92

    return "Other", 0.40
