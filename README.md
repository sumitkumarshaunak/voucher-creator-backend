# Voucher Creator Backend

Small FastAPI backend that uploads a document to LlamaCloud and returns parsed voucher JSON.

## Setup

Create/update `.env`:

```env
LLAMA_CLOUD_API_KEY=your_real_key_here
```

Install dependencies:

```bash
cd /Users/amanjain/Desktop/voucher/voucher-creator
.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
cd /Users/amanjain/Desktop/voucher/voucher-creator
.venv/bin/python -m uvicorn server:app --app-dir src --host 127.0.0.1 --port 8001
```

## Check

```bash
curl http://127.0.0.1:8001/health
```

Expected response:

```json
{"status":"ok"}
```

The frontend is configured to call `http://127.0.0.1:8001`.
