import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from env import load_backend_env
from llamaparser import EXTRACT_CONFIGS, extract_file, infer_document_type


load_backend_env()

app = FastAPI(title="Voucher Creator API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
):
    with tempfile.TemporaryDirectory() as temporary_directory:
        file_path = Path(temporary_directory) / file.filename
        file_path.write_bytes(await file.read())

        selected_document_type = document_type or infer_document_type(file_path)

        if selected_document_type not in EXTRACT_CONFIGS:
            raise HTTPException(status_code=400, detail="Unsupported document type.")

        try:
            return extract_file(file_path, document_type=selected_document_type)
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
