"""
Momento — API Layer
The bridge between the intelligence engines and the world.
Built with FastAPI. Clean, versioned, production-ready from day one.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import process_sms, get_summary, reset


# ─── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Momento API",
    description="The quiet intelligence layer between people and their money.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response models ─────────────────────────────────────────────────

class SMSRequest(BaseModel):
    sms: str

    class Config:
        json_schema_extra = {
            "example": {
                "sms": "FNB: R450.00 spent at WOOLWORTHS FOOD 14:23. Avail bal: R12,340.00"
            }
        }


class TransactionOut(BaseModel):
    bank: str
    amount: float
    merchant: str
    category: str
    time: Optional[str]
    date: Optional[str]
    balance_after: Optional[float]
    card_last4: Optional[str]


class ConfidenceOut(BaseModel):
    parse: float
    classify: float


class WhisperOut(BaseModel):
    message: str
    severity: str


class ParseResponse(BaseModel):
    success: bool
    transaction: Optional[TransactionOut] = None
    confidence: Optional[ConfidenceOut] = None
    whispers: list[WhisperOut] = []
    error: Optional[str] = None


class CategoryBreakdown(BaseModel):
    category: str
    total: float
    percentage: float


class TopMerchant(BaseModel):
    merchant: str
    count: int
    total: float


class SummaryResponse(BaseModel):
    total_spend: float
    transaction_count: int
    largest_category: Optional[str]
    category_breakdown: list[CategoryBreakdown]
    top_merchants: list[TopMerchant]


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "product": "Momento",
        "tagline": "Your money, remembered.",
        "version": "0.1.0",
        "status": "alive",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/parse", response_model=ParseResponse)
def parse(request: SMSRequest):
    """
    Parse a raw bank SMS string.
    Returns a structured transaction, confidence scores, and any whispers.
    """
    if not request.sms or not request.sms.strip():
        raise HTTPException(status_code=400, detail="SMS text is required.")

    result = process_sms(request.sms.strip())

    if not result["success"]:
        return ParseResponse(
            success=False,
            error=result.get("error", "Unknown parse error."),
        )

    t = result["transaction"]
    c = result["confidence"]
    w = result["whispers"]

    return ParseResponse(
        success=True,
        transaction=TransactionOut(**t),
        confidence=ConfidenceOut(**c),
        whispers=[WhisperOut(**whisper) for whisper in w],
    )


@app.post("/v1/parse/batch", response_model=list[ParseResponse])
def parse_batch(requests: list[SMSRequest]):
    """
    Parse multiple SMS strings in one call.
    Maximum 50 per request.
    """
    if len(requests) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 SMS per batch request.")

    results = []
    for req in requests:
        result = process_sms(req.sms.strip())
        if not result["success"]:
            results.append(ParseResponse(success=False, error=result.get("error")))
        else:
            t = result["transaction"]
            results.append(ParseResponse(
                success=True,
                transaction=TransactionOut(**t),
                confidence=ConfidenceOut(**result["confidence"]),
                whispers=[WhisperOut(**w) for w in result["whispers"]],
            ))

    return results


@app.get("/v1/summary", response_model=SummaryResponse)
def summary():
    """
    Return the monthly spending summary across all parsed transactions.
    """
    s = get_summary()
    total = s["total"]

    breakdown = [
        CategoryBreakdown(
            category=cat,
            total=amt,
            percentage=round((amt / total * 100), 1) if total else 0,
        )
        for cat, amt in s["category_breakdown"].items()
    ]

    top = [
        TopMerchant(merchant=m, count=c, total=t)
        for m, c, t in s["top_merchants"]
    ]

    return SummaryResponse(
        total_spend=total,
        transaction_count=s["transaction_count"],
        largest_category=s["largest_category"],
        category_breakdown=breakdown,
        top_merchants=top,
    )


@app.post("/v1/reset")
def reset_session():
    """
    Clear the in-memory transaction session.
    Use between test runs or new user sessions.
    """
    reset()
    return {"status": "cleared", "message": "Session reset. Memory cleared."}
