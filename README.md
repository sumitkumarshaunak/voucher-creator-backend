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
