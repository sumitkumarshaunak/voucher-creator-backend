import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.extraction_service import SUPPORTED_DOCUMENT_TYPES, extract_document, infer_document_type
from services.tally_service import (
    create_tally_account,
    list_tally_accounts,
    list_tally_bank_accounts,
    list_tally_companies,
    post_to_tally,
)


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/tally/companies")
def tally_companies():
    try:
        return list_tally_companies()
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/tally/accounts")
def tally_accounts(company_name: str | None = None):
    try:
        return list_tally_accounts(company_name)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/tally/bank-accounts")
def tally_bank_accounts(company_name: str | None = None):
    try:
        return list_tally_bank_accounts(company_name)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/tally/accounts")
async def tally_account(payload: dict):
    try:
        return create_tally_account(
            payload.get("name"),
            payload.get("parent") or "Sundry Creditors",
            payload.get("company_name"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
    heading_row: int | None = Form(default=None),
    row_from: int | None = Form(default=None),
    row_to: int | None = Form(default=None),
):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        file_path = Path(temporary_directory) / file.filename
        file_path.write_bytes(await file.read())

        selected_document_type = document_type or infer_document_type(file_path)

        if selected_document_type not in SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported document type.")

        row_options = _spreadsheet_row_options(heading_row, row_from, row_to)

        try:
            return extract_document(
                file_path,
                document_type=selected_document_type,
                row_options=row_options,
            )
        except TimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail="Document extraction timed out. Try a smaller file or retry the request.",
            ) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/post-to-tally")
async def post_voucher_to_tally(payload: dict):
    try:
        return post_to_tally(payload)
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="Posting to Tally timed out.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def _spreadsheet_row_options(heading_row, row_from, row_to):
    options = {
        "heading_row": heading_row,
        "row_from": row_from,
        "row_to": row_to,
    }

    for label, value in options.items():
        if value is not None and value < 1:
            raise HTTPException(status_code=400, detail=f"{label} must be greater than zero.")

    if row_from and row_to and row_from > row_to:
        raise HTTPException(status_code=400, detail="row_from cannot be greater than row_to.")

    return options
