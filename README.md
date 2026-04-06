# Momento

> *Your money, remembered.*

A quiet intelligence layer that sits between people and their money — invisible, automatic, and honest.

## What it does

Every time you use your card, your bank sends an SMS. Momento intercepts it, understands it, and builds a living picture of your financial life. No manual entry. No friction. No noise.

## The three engines

| Engine | Role |
|---|---|
| **Parser** | Reads raw bank SMS text from FNB, Absa, Nedbank, Standard Bank, Capitec |
| **Classifier** | Maps merchants to categories — understands Woolworths Food ≠ Woolworths Clothing |
| **Behaviour** | Tracks patterns, detects anomalies, whispers insights at the right moment |

## API

### Run locally

```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API.

### Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/` | Status |
| GET | `/health` | Health check |
| POST | `/v1/parse` | Parse a single SMS |
| POST | `/v1/parse/batch` | Parse up to 50 SMS |
| GET | `/v1/summary` | Monthly spending summary |
| POST | `/v1/reset` | Clear session |

### Example

```bash
curl -X POST https://your-url/v1/parse \
  -H "Content-Type: application/json" \
  -d '{"sms": "FNB: R450.00 spent at WOOLWORTHS FOOD 14:23. Avail bal: R12,340.00"}'
```

```json
{
  "success": true,
  "transaction": {
    "bank": "FNB",
    "amount": 450.0,
    "merchant": "Woolworths Food",
    "category": "Groceries",
    "time": "14:23",
    "balance_after": 12340.0
  },
  "confidence": {
    "parse": 0.95,
    "classify": 0.92
  },
  "whispers": []
}
```

## Structure

```
momento/
├── api.py              # FastAPI routes
├── pipeline.py         # Wires the three engines together
├── requirements.txt
├── Procfile            # Railway deployment
└── engine/
    ├── parser.py       # Layer 01 — reads bank SMS formats
    ├── classifier.py   # Layer 02 — merchant categorisation
    └── behaviour.py    # Layer 03 — patterns and whispers
```

## Supported banks (v1)

- FNB
- Absa
- Nedbank
- Standard Bank
- Capitec
