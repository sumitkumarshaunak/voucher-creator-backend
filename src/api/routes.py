import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.extraction_service import SUPPORTED_DOCUMENT_TYPES, extract_document, infer_document_type
from services.tally_service import post_to_tally


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
):
    with tempfile.TemporaryDirectory() as temporary_directory:
        file_path = Path(temporary_directory) / file.filename
        file_path.write_bytes(await file.read())

        selected_document_type = document_type or infer_document_type(file_path)

        if selected_document_type not in SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported document type.")

        try:
            return extract_document(file_path, document_type=selected_document_type)
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/post-to-tally")
async def post_voucher_to_tally(payload: dict):
    try:
        return post_to_tally(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
