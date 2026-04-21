# Fullerton OCR Service

A single-endpoint FastAPI service that accepts a medical document (PDF / JPG / PNG),
classifies it as one of `referral_letter`, `medical_certificate`, or `receipt`,
extracts structured fields, and returns a JSON envelope ready for downstream
claim adjudication.

## Pipeline

```
Upload (PDF/image)
   |
   v
Normalise         pdf2image / PyMuPDF -> PIL image + raw embedded text
   |
   v
Classify          Keyword rules over raw text -> Gemini vision fallback
   |
   v
Extract           Gemini 2.5 Flash-Lite, temp=0, structured output (JSON schema)
   |
   v
Postprocess       Amounts -> int, dates -> DD/MM/YYYY, strip "Fullerton Health"
   |
   v
Validate          Pydantic + required-field check + cross-check vs raw text
   |
   v
Retry once?       If validation fails: build repair prompt with failure summary
   |              + raw-text hint, re-extract, keep the better attempt.
   v
Persist failures  Write JSON record (and original doc on hard failure) to
   |              failed_extractions/ for human review.
   v
Response          Envelope with finalJson, low_confidence flag, review_id.
```

## Setup

Requires Python 3.11+ and (for PDF rendering of scanned PDFs) Poppler.

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils
```

```bash
git clone <repo>
cd fullerton_takehome
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env and set GEMINI_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs at <http://localhost:8000/docs>.

## Sample requests

```bash
# Working examples:
# Upload a PDF
curl -X POST http://localhost:8000/ocr \
  -F "file=@referral_letter.pdf"

Potential tests:
# Upload an image
curl -X POST http://localhost:8000/ocr \
  -F "file=@image.png"
```

### Sample success response

```json
{
  "message": "Processing completed.",
  "result": {
    "document_type": "receipt",
    "total_time": 2.41,
    "finalJson": {
      "claimant_name": "Jane Doe",
      "claimant_address": "1 Main St",
      "claimant_date_of_birth": "01/01/1990",
      "provider_name": "Raffles Medical",
      "tax_amount": 7000,
      "total_amount": 107000
    },
    "attempts": 1,
    "low_confidence": false,
    "failed_fields": [],
    "review_id": null,
    "stage_timings": {
      "normalize": 0.08,
      "classify": 0.01,
      "extract_attempt_1": 2.31
    }
  }
}
```

### Error responses

| Status | Condition                                  | Body                                       |
|--------|--------------------------------------------|--------------------------------------------|
| 400    | No file uploaded or unsupported MIME type  | `{"error": "file_missing"}`                |
| 422    | Document type not in supported list        | `{"error": "unsupported_document_type"}`   |
| 500    | Unhandled exception                        | `{"error": "internal_server_error"}`       |

## Tests

```bash
pytest                # unit + integration (Gemini mocked)
pytest -m slow        # opt-in: hits the live Gemini API
```

## Extending to a new document type

The pipeline is registry-driven, so adding a type (e.g. `discharge_summary`)
takes four small changes and zero edits to the orchestrator:

1. **Schema**: create `app/schemas/discharge_summary.py` with:
   - a Pydantic model `DischargeSummaryFields`
   - `DISCHARGE_SUMMARY_REQUIRED_FIELDS: list[str]`
   - `DISCHARGE_SUMMARY_GEMINI_SCHEMA: dict` (passed to `response_schema`)

2. **Prompt**: create `app/prompts/discharge_summary.py` describing each field
   and call `build_extraction_prompt()`.

3. **Register**: in `app/schemas/__init__.py` add an entry to `DOC_TYPE_REGISTRY`,
   and in `app/prompts/__init__.py` add to `EXTRACTION_PROMPTS`. Add the new
   value to `DocumentType` in `app/schemas/base.py`.

4. **Classifier hint**;:in `app/pipeline/classify.py` add a list of distinctive
   keywords under `KEYWORD_RULES`. The Gemini classifier fallback also needs
   the new label added to `CLASSIFY_PROMPT` in `app/prompts/base.py`.

If a new field type needs custom normalisation (e.g. phone numbers, NRIC),
add a normaliser to `app/pipeline/postprocess.py` and reference it via the
relevant `*_FIELDS` set.

## Retry policy

Failed validations trigger up to **1 retry** (configurable via
`MAX_EXTRACTION_RETRIES`) with a *repair prompt* built from the failure report.
The repair prompt includes:

- a per-field summary of what failed and why
- targeted excerpts from the PDF's raw embedded text (for native PDFs)

The orchestrator keeps the better of the two attempts (fewer errors wins) so a
worse retry never replaces a passing first attempt. Outcomes are categorised:

| Outcome                | Status                | Stored?          | Doc bytes saved? |
|------------------------|-----------------------|------------------|------------------|
| Pass on first attempt  | success               | no               | no               |
| Recovered on retry     | `recovered_on_retry`  | metadata only    | no               |
| Retry still fails, no required field missing | `degraded` | metadata only | no |
| Retry still fails, required field missing    | `failed`   | metadata + doc | yes |

Failed records are written to `failed_extractions/` as `<timestamp>_<uuid>.json`.
For `failed` status the original document is also persisted alongside.

## Scalability notes (out of scope for this demo)

- **Synchronous LLM call in request path** — at scale move to a job queue
  (Celery / RQ + SQS), return `job_id`, deliver result via webhook or polling.
- **Rate limiting / backpressure** — a global semaphore around Gemini calls
  plus exponential backoff on 429 prevents quota cascades.
- **PDF rendering** — Poppler is CPU-bound and memory-heavy; cap pages and DPI
  (already enforced via `MAX_PDF_PAGES` / `PDF_RENDER_DPI`), and run rendering
  in a thread pool to keep the event loop free.
- **Idempotency** — hash uploaded bytes and cache extraction results in
  Redis with a TTL to avoid re-paying for duplicate submissions.
- **Failure store -> production** — swap the local-disk implementation for
  S3 (encrypted at rest) + a Postgres `extraction_failures` table + an SQS
  topic for the review queue. Public interface in `app/storage/failure_store.py`
  stays the same.
- **Alerting** — alert on aggregate failure rate over a rolling window, never
  per-failure (alert fatigue).

## Privacy / PDPA

Uploaded documents contain personal data (claimant name, DOB, address,
diagnosis, ICD code). Production deployments must add:

- Encryption at rest for `failed_extractions/` (or its S3 replacement)
- Access controls + audit logging on reads
- A retention policy with automatic purge
- A no-retention agreement with the LLM provider (Gemini supports this on
  the paid tier)
- Scrub PHI from logs (current logger does not log raw extracted values, only
  field counts and validation status)

## Known follow-ups

- The `google-generativeai` SDK is deprecated in favour of `google-genai`.
  Migration is a small change in `app/clients/gemini.py`.
- Only the first page of multi-page PDFs is sent to the vision model. For
  longer documents (e.g. discharge summaries) consider page-by-page extraction
  with field-level merging.
- Signature detection is delegated entirely to the LLM and is unreliable for
  printed names / stamps. A dedicated signature-block CV check would be more
  robust.

## Layout

```
app/
  api/            FastAPI routes, error responses
  pipeline/       normalize, classify, extract, postprocess, validate, orchestrator
  schemas/        Pydantic models + per-type registry
  prompts/        Per-doc-type extraction prompts + base/repair templates
  clients/        Gemini SDK wrapper (timeouts, retries, logging)
  storage/        FailureStore (local-disk demo impl)
  utils/          logging, hashing, timing
tests/
  unit/           pure-logic tests
  integration/    full pipeline + API tests, Gemini mocked
  e2e/            opt-in tests against live Gemini (pytest -m slow)
docs/             architecture diagram + summary report deliverables
failed_extractions/  runtime-created review queue
```
