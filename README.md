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
.venv/bin/python -m uvicorn server:app --app-dir src --host 127.0.0.1 --port 8000
```

`server:app` is kept as a compatibility entrypoint. The app is created in `src/app.py`.

## Check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The frontend is configured to call `http://127.0.0.1:8000`.
