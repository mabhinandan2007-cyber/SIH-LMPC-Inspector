# LMPC Inspector — AI Agent System Instructions

## Project Identity

This repository implements the **LMPC Label Scanner** — an automated compliance verification system for packaged commodity labels under India's *Legal Metrology (Packaged Commodities) Rules, 2011*.

Inspectors photograph product labels; the system extracts statutory declarations (MRP, Net Quantity, Manufacturer, Dates) via OCR, evaluates them against legal rules, and routes uncertain results to a human review queue.

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn | ASGI web framework |
| **Database** | SQLite via SQLAlchemy ORM | Single-file DB in `storage/sql_app.db` |
| **Primary OCR** | EasyOCR | Runs on preprocessed (CLAHE) images |
| **Secondary OCR** | docTR | Used for verification crops with adaptive padding |
| **Installed (unused)** | PaddleOCR 3.7.0 | Installed but not integrated into the pipeline |
| **Frontend** | Single-page HTML with React 18 + Tailwind CSS (CDN) | No build step |
| **PDF Reports** | Jinja2 + xhtml2pdf | Server-side HTML→PDF rendering |

## Directory Structure

```
SIH/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI entry point
│       ├── api/scans.py      # REST endpoints
│       ├── db/
│       │   ├── database.py   # Engine, session, Base
│       │   └── models.py     # ORM models
│       ├── ocr/
│       │   ├── pipeline.py   # EasyOCR + docTR extraction
│       │   └── classifier.py # Keyword → field type mapping
│       ├── rules/engine.py   # Spatial scoring rule evaluators
│       └── templates/report.html  # PDF report Jinja template
├── frontend/
│   └── index.html            # React SPA
├── storage/                   # Uploaded images + SQLite DB
└── data/                      # (empty — reserved for future datasets)
```

## Behavioural Guidelines for AI Sessions

1. **Never modify OCR engine initialisation** without explicit user approval — changing EasyOCR/docTR model parameters can cascade into test regressions.
2. **Preserve backward-compatible aliases** — `run_paddle_ocr` and `verify_price_with_doctr` are legacy names still imported by other modules.
3. **Always run benchmark tests** after modifying `engine.py` or `classifier.py` using the Soya Chips and Patanjali test images in `storage/`.
4. **Do not add external API calls** to the OCR/rule-evaluation path — the system must remain fully offline-capable.
5. **Update `continuation.md`** at the end of every session with the current project state.

## How to Parse the Codebase

1. Start with `architecture.md` for the data-flow overview.
2. Read `docs/API_AND_FUNCTIONS.md` for the function-level reference.
3. Check `history.md` for the rationale behind non-obvious design decisions.
4. Review `rules.md` for coding conventions before making changes.
