# Document Intelligence Platform

AI-powered financial document extraction, validation, persistence, and dashboard platform built for the AI Engineer Internship technical case study.

## Live Application

- Frontend: https://document-intelligence-fchk.onrender.com/
- Backend API: https://document-intelligence-fchk.onrender.com
- Swagger / OpenAPI: https://document-intelligence-fchk.onrender.com/docs
- Health Check: https://document-intelligence-fchk.onrender.com/api/v1/health
- GitHub: https://github.com/Ananthi0207/document-intelligence

## Solution Overview

The application accepts one of four supported financial document types:

- Invoice
- Balance Sheet
- Profit & Loss
- Cash Flow Statement

The user selects the document type and uploads a PDF, JPG, or PNG file. The system validates the upload, extracts text using native parsing and/or OCR, sends the extracted text to Gemini for structured field/table extraction, performs deterministic financial validation in Python, stores the complete processing result in a persistent database, and exposes the result through a dashboard and REST API.

### Processing Flow

```text
Document Upload
      |
      v
File Validation
(PDF/JPG/PNG, readable, max 3 pages)
      |
      v
Text Extraction / OCR
      |
      v
Gemini Structured Extraction
(Pydantic / JSON schema)
      |
      v
Deterministic Financial Validation
      |
      v
Persistent Database
      |
      v
Dashboard + REST API + Raw JSON
```

Architecture diagram: [docs/architecture.png](docs/architecture.png)

Solution presentation: [docs/solution_presentation.pdf](docs/solution_presentation.pdf)

## Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Async API support, validation, automatic OpenAPI/Swagger documentation |
| Structured schemas | Pydantic | Consistent machine-readable extraction and API models |
| LLM extraction | Gemini (`gemini-3.5-flash-lite`) | Structured extraction with schema-constrained JSON output |
| OCR | OCR.Space | Handles scanned/image-based documents using a lightweight hosted OCR API |
| Native document parsing | PDF text extraction before or alongside OCR where applicable | Avoids relying only on OCR for digital documents |
| Database | SQLite locally, PostgreSQL on Render | Simple local development with persistent production deployment |
| ORM / persistence | SQLAlchemy | Separates database access from API and processing logic |
| Frontend | HTML, CSS, JavaScript | Lightweight deployed UI without a separate frontend framework |
| Deployment | Render | Public frontend/backend deployment and managed PostgreSQL |
| Dependency management | uv | Fast, reproducible Python environment and lock file |

## Architecture and Separation of Concerns

The backend is split into dedicated layers:

```text
backend/app/
├── api/routes/                  # REST endpoints
├── core/                        # configuration and database setup
├── models/                      # persistence models
├── repositories/                # database access
├── schemas/                     # Pydantic request/extraction schemas
├── services/
│   ├── document_validation_service.py
│   ├── ocr_service.py
│   ├── extraction_service.py
│   └── financial_validation_service.py
└── main.py                      # FastAPI application
```

This keeps upload validation, OCR/text extraction, AI extraction, deterministic calculations, persistence, and API responsibilities separate.

## Supported Inputs

- PDF
- JPG / JPEG
- PNG
- Native or scanned/image-based documents
- Maximum 3 pages per document

Unsupported, unreadable, corrupt, empty, or over-limit documents are rejected with controlled errors.

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Ananthi0207/document-intelligence.git
cd document-intelligence
```

### 2. Install dependencies

Install `uv`, then run:

```bash
uv sync
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and provide your own credentials.

```env
OCR_SPACE_API_KEY=your_ocr_space_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
DATABASE_URL=sqlite:///./document_intelligence.db
```

Never commit the real `.env` file or API keys.

### 4. Run locally

```bash
uv run python -m uvicorn backend.app.main:app --reload
```

Open:

- Application: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/v1/health

## Environment Variables

| Variable | Purpose |
|---|---|
| `OCR_SPACE_API_KEY` | OCR.Space API credential |
| `GEMINI_API_KEY` | Gemini API credential |
| `GEMINI_MODEL` | Gemini model name; default used by this project is `gemini-3.5-flash-lite` |
| `DATABASE_URL` | SQLAlchemy database connection URL; SQLite locally and PostgreSQL in deployment |

## REST API

### Health Check

```http
GET /api/v1/health
```

Example response:

```json
{
  "status": "healthy"
}
```

### Process a Document

```http
POST /api/v1/documents/process
Content-Type: multipart/form-data
```

Example using curl:

```bash
curl -X POST \
  "https://document-intelligence-fchk.onrender.com/api/v1/documents/process" \
  -F "document_type=balance_sheet" \
  -F "file=@Consolidated Balance Sheet 2017.pdf"
```

Supported `document_type` values:

```text
invoice
balance_sheet
profit_and_loss
cash_flow_statement
```

### Get Latest Result by Document Name

```http
GET /api/v1/documents/{document_name}
```

Example:

```bash
curl "https://document-intelligence-fchk.onrender.com/api/v1/documents/Consolidated%20Balance%20Sheet%202017.pdf"
```

### List Processed Documents

```http
GET /api/v1/documents
```

Example:

```bash
curl "https://document-intelligence-fchk.onrender.com/api/v1/documents"
```

Interactive API documentation is available at:

https://document-intelligence-fchk.onrender.com/docs

## Extraction Strategy

### OCR and Text Parsing

The service supports both native and scanned documents. Text is obtained through document parsing and OCR as required. OCR.Space is used for OCR processing. Processing metadata records whether OCR and OCR fallback were used.

### AI Structured Extraction

Gemini receives document text together with document-type-specific extraction instructions. Pydantic schemas are used to constrain the structured output.

The extraction layer follows these rules:

- Extract only values supported by source evidence.
- Do not invent or mathematically repair missing values.
- Missing/unsupported values remain `null` or are excluded where appropriate.
- Preserve reporting periods and line-item structure.
- Preserve negative financial values, including parenthesized negatives.
- Attach source text/page evidence when available.

A Balance Sheet post-normalization step handles flattened OCR comparative columns by using source-visible numeric tokens and reported totals as anchors. It does not calculate replacement values to force a PASS.

## Financial Validation

Financial validation is deterministic Python logic and is separate from the LLM extraction stage.

The implemented numerical tolerance is:

```text
0.01
```

Each validation check returns information such as:

- formula
- operands
- calculated value
- reported value
- variance
- status: `PASS`, `FAIL`, or `NOT_APPLICABLE`

### Invoice

Validations include, where the required values are available:

- `quantity x unit_price ~= line_amount`
- line totals against subtotal/total
- taxable amount + tax against total
- cash paid - total against change
- handling of tax-included or rounding-related totals where supported by the extracted source values

### Balance Sheet

Checks are performed per reporting period:

- total capital and liabilities against total assets
- sum of capital/liability components against reported capital and liabilities total
- sum of asset components against reported total assets

Off-balance-sheet rows such as contingent liabilities and bills for collection are kept separate from asset components.

### Profit & Loss

Checks are performed per reporting period where values are available, including:

- interest earned + other income against total income
- interest expended + operating expenses + provisions against total expenditure
- income - expenditure against net profit before minority interest
- minority interest / associate-profit relationships used for group profit
- appropriation relationships where present

### Cash Flow Statement

Checks are performed per reporting period where values are available, including:

- operating + investing + financing + FX adjustment against net change in cash
- opening cash + net change + explicit adjustments against closing cash

If required operands are genuinely absent, the corresponding check returns `NOT_APPLICABLE` instead of inventing values.

## Persistence

Processed results are stored using SQLAlchemy.

- Local development: SQLite
- Deployed environment: PostgreSQL on Render

Stored results include document metadata, extracted data, validation output, processing status, and processing metadata. The dashboard and GET endpoints read persisted records rather than relying only on in-memory state.

## Frontend and Dashboard

The deployed frontend allows evaluators to:

- select the document type
- upload and process a document
- view processed-document history
- inspect extracted fields and line items
- inspect financial validation formulas, values, variance, and status
- view missing/failed validations
- inspect the complete raw JSON response

## Testing

Run the automated tests with:

```bash
uv run pytest backend/tests -v
```

The current automated test suite covers:

- invalid/unsupported file validation
- deterministic financial calculation logic
- one end-to-end API processing flow using FastAPI `TestClient`

Representative JSON outputs are included in `sample_outputs/`:

```text
sample_outputs/
├── invoice_pass.json
├── invoice_fail.json
├── balance_sheet.json
├── profit_and_loss.json
└── cash_flow_statement.json
```

Representative verified financial-validation results include:

- Invoice PASS: 4/4 checks
- Balance Sheet PASS: 6/6 checks
- Profit & Loss PASS: 10/10 checks
- Cash Flow PASS: 4/4 checks
- Invoice failure sample included to demonstrate a genuine financial reconciliation failure

## Deployment

The application is deployed on Render.

- Web service serves both the frontend and FastAPI backend.
- PostgreSQL provides persistent deployed storage.
- Environment variables are configured through Render rather than committed to GitHub.
- The deployed application exposes Swagger/OpenAPI and the required health endpoint.

Live URLs:

- Frontend: https://document-intelligence-fchk.onrender.com/
- API: https://document-intelligence-fchk.onrender.com
- Swagger: https://document-intelligence-fchk.onrender.com/docs
- Health: https://document-intelligence-fchk.onrender.com/api/v1/health

## Known Limitations

- OCR quality and unusual table layouts can affect extraction quality.
- Comparative financial statements flattened by OCR require layout normalization; the current implementation specifically handles source-grounded Balance Sheet alignment but is not a general-purpose table reconstruction engine.
- OCR.Space and Gemini are external services, so processing depends on their availability, latency, and free-tier quotas.
- Render free-tier services can have cold-start latency.
- Financial validation covers the relationships required for this prototype and should not be interpreted as a complete accounting audit.
- The case-study input limit is intentionally restricted to three pages.

## Production Improvements

For a production deployment I would add:

- asynchronous/background document processing for long-running OCR/LLM jobs
- object storage for uploaded documents and generated artifacts
- authentication, authorization, rate limiting, and tenant isolation
- database migrations and stronger data-retention policies
- managed OCR/document-layout models for complex tables
- retry policies, circuit breakers, and provider fallbacks
- structured monitoring, metrics, tracing, and alerting
- larger regression datasets across document layouts and OCR qualities
- extraction-schema/version tracking and model-evaluation dashboards
- stronger security scanning and upload malware protection

## AI / Tool Usage Declaration

Generative AI tools were used during development as permitted by the case study.

- **Gemini** is part of the runtime application and performs structured financial-document extraction.
- **ChatGPT** was used as a development assistant for implementation guidance, debugging, test development, documentation, architecture discussion, and troubleshooting deployment/extraction issues.

All deterministic financial calculations are implemented in Python rather than delegated to the LLM. The submitted solution, architecture, prompts, validation logic, APIs, deployment configuration, and code can be explained and modified by the candidate.

## Repository Assets

```text
docs/
├── architecture.png
└── solution_presentation.pdf

sample_outputs/
├── invoice_pass.json
├── invoice_fail.json
├── balance_sheet.json
├── profit_and_loss.json
└── cash_flow_statement.json
```

## Submission Links

- Public GitHub: https://github.com/Ananthi0207/document-intelligence
- Live Frontend: https://document-intelligence-fchk.onrender.com/
- Live Backend: https://document-intelligence-fchk.onrender.com
- Swagger/OpenAPI: https://document-intelligence-fchk.onrender.com/docs
- Health: https://document-intelligence-fchk.onrender.com/api/v1/health
