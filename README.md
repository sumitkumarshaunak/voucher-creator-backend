# Voucher Creator Backend

FastAPI backend that extracts voucher JSON from invoices and bank statements.

Invoices use LlamaCloud for markdown extraction, then OpenAI for schema JSON.
Bank statements use OpenAI directly.

## Setup

Create/update `.env`:

```env
LLAMA_CLOUD_API_KEY=your_real_key_here
OPENAI_API_KEY=your_real_key_here
```

Install dependencies:

```bash
cd voucher-creator
.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
cd voucher-creator
.venv/bin/python -m uvicorn server:app --app-dir src --host 0.0.0.0 --port 8000
```

`server:app` is kept as a compatibility entrypoint. The app is created in `src/app.py`.
You can also run `python src/server.py`; it uses `BACKEND_HOST` and `BACKEND_PORT`
from `.env`, defaulting to `0.0.0.0:8000`.

## Check

```bash
curl http://127.0.0.1:8000/health
```

From another device on the same network, use this computer's LAN IP instead, for example:

```bash
curl http://192.168.1.25:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The frontend running on another device must use this computer's LAN IP for
`VITE_API_BASE_URL`, for example `http://192.168.1.25:8000`.

## Backend API

All document parsing starts with:

```http
POST /extract
```

The request must be `multipart/form-data` with one file and a `document_type`.
Invoices also need `source` so the backend can separate sales and purchase
invoice results.

### Bank Statement

Use this for `.xls`, `.xlsx`, or `.pdf` bank statements:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/bank-statement.xlsx" \
  -F "document_type=bank_statement" \
  -F "source=bank-statement"
```

For spreadsheet bank statements, optional row controls are supported:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/bank-statement.xlsx" \
  -F "document_type=bank_statement" \
  -F "source=bank-statement" \
  -F "heading_row=5" \
  -F "row_from=6" \
  -F "row_to=120"
```

Completed results are copied to MongoDB collection `bank_statements`.

### Sales Invoice

Use this for a sales invoice PDF or image:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/sales-invoice.pdf" \
  -F "document_type=invoice" \
  -F "source=sales-invoice"
```

Completed results are copied to MongoDB collection `sales_invoices`.

### Purchase Invoice

Use this for a purchase invoice PDF or image:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/purchase-invoice.pdf" \
  -F "document_type=invoice" \
  -F "source=purchase-invoice"
```

Completed results are copied to MongoDB collection `purchase_invoices`.

### Multi-Image Invoice

For an invoice split across multiple image files, send repeated `files` fields:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "files=@/path/to/page-1.jpg" \
  -F "files=@/path/to/page-2.jpg" \
  -F "document_type=invoice" \
  -F "source=purchase-invoice" \
  -F "client_file_count=2"
```

### Invoice Options

Invoices support optional fields:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/invoice.pdf" \
  -F "document_type=invoice" \
  -F "source=sales-invoice" \
  -F "expected_line_item_count=12"
```

### Sales Report

Use this for the Excel sales report workflow:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -F "file=@/path/to/sales-report.xlsx" \
  -F "document_type=sales_report" \
  -F "source=sales-report" \
  -F "heading_row=1" \
  -F 'header_mappings={"0":"invoice_date","1":"invoice_no","2":"party_name","3":"gst","4":"sale","5":"invoice_total"}'
```

Sales report results stay in `extraction_jobs`; they are not copied to a
separate business collection.

### Poll Job Status

`POST /extract` returns immediately with a queued job:

```json
{
  "job_id": "6a361127a25623cf6fa0a7dc",
  "status": "queued",
  "status_url": "/extract/6a361127a25623cf6fa0a7dc"
}
```

Poll the status URL until `status` is `completed` or `failed`:

```bash
curl http://127.0.0.1:8000/extract/6a361127a25623cf6fa0a7dc
```

When completed, the parsed document is in `result`:

```json
{
  "id": "6a361127a25623cf6fa0a7dc",
  "status": "completed",
  "document_type": "invoice",
  "saved_collection": "sales_invoices",
  "result": {
    "invoice_no": "SSFPL/2627/H0269"
  }
}
```

The uploaded source file is temporary and is deleted after processing. The
parsed JSON remains in MongoDB.

### MongoDB Collections

Configure collection names in `.env`:

```env
MONGO_DB=voucher-creator
MONGO_EXTRACTION_JOBS_COLLECTION=extraction_jobs
MONGO_SALES_INVOICES_COLLECTION=sales_invoices
MONGO_PURCHASE_INVOICES_COLLECTION=purchase_invoices
MONGO_BANK_STATEMENTS_COLLECTION=bank_statements
```

`extraction_jobs` is the source of truth for job status. The business
collections are copies of completed parsed results for easier lookup in Compass.

## Tally Posting

Keep Tally running with HTTP access on port `9000`, then use the frontend's
`Post to Tally` button after parsing and reviewing a voucher.

The backend posts Tally XML to:

```env
TALLY_URL=http://127.0.0.1:9000
```

Voucher mapping:

- Bank statement credit rows become Receipt vouchers.
- Bank statement debit rows become Payment vouchers.
- Cash deposit/movement credit rows become Payment vouchers so Cash is credited
  and the bank ledger is debited.
- Sales invoice uploads become Sales vouchers.
- Purchase invoice uploads become Purchase vouchers.

Bank statement voucher numbers are generated from bank, account number, value
date, reference, direction, and amount. Before posting, the backend checks Tally
for the same voucher type and voucher number, then skips already-posted entries.
Tally lookup/export calls are batched with `TALLY_LOOKUP_BATCH_SIZE`, missing
master creation uses `TALLY_MASTER_BATCH_SIZE`, and voucher imports are sent in
batches controlled by `TALLY_VOUCHER_BATCH_SIZE`.

The first version expects the target ledgers to already exist in Tally. Configure
ledger names in `.env` using the keys shown in `.env.example`.
