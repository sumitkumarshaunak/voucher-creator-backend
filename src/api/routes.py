import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from services.extraction_service import SUPPORTED_DOCUMENT_TYPES, extract_document, extract_documents, infer_document_type
from services.tally_service import (
    create_tally_account,
    get_tally_account_totals,
    list_tally_accounts,
    list_tally_bank_accounts,
    list_tally_companies,
    list_tally_stock_items,
    post_to_tally,
)


router = APIRouter()
UPLOAD_DEBUG_FILE = Path(__file__).resolve().parents[2] / "last-upload-debug.json"


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


@router.get("/tally/stock-items")
def tally_stock_items(company_name: str | None = None):
    try:
        return list_tally_stock_items(company_name)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/tally/account-totals")
def tally_account_totals(
    company_name: str | None = None,
    account_name: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    skip_voucher_types: str | None = None,
):
    try:
        return get_tally_account_totals(company_name, account_name, from_date, to_date, skip_voucher_types)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
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
async def extract(request: Request):
    form = await request.form()
    document_type = _optional_form_str(form, "document_type")
    heading_row = _optional_form_int(form, "heading_row")
    row_from = _optional_form_int(form, "row_from")
    row_to = _optional_form_int(form, "row_to")
    expected_line_item_count = _optional_form_int(form, "expected_line_item_count")
    medical_invoice = _optional_form_bool(form, "medical_invoice")
    header_mappings = _optional_form_str(form, "header_mappings")
    client_file_count = _optional_form_int(form, "client_file_count")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
        file_field_uploads = _form_upload_files(form, "file")
        files_field_uploads = _form_upload_files(form, "files")
        upload_files = [*file_field_uploads, *files_field_uploads]

        if not upload_files:
            raise HTTPException(status_code=400, detail="Upload at least one file.")

        file_paths = []
        for index, upload_file in enumerate(upload_files, start=1):
            file_path = Path(temporary_directory) / f"{index}-{Path(upload_file.filename).name}"
            file_path.write_bytes(await upload_file.read())
            file_paths.append(file_path)

        selected_document_type = document_type or infer_document_type(file_paths[0])
        _write_upload_debug(
            upload_files,
            file_paths,
            selected_document_type,
            file_field_count=len(file_field_uploads),
            files_field_count=len(files_field_uploads),
            client_file_count=client_file_count,
        )

        if client_file_count is not None and client_file_count != len(upload_files):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Frontend sent {client_file_count} file(s), but backend received "
                    f"{len(upload_files)} file(s)."
                ),
            )

        if selected_document_type not in SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported document type.")

        row_options = _extract_options(
            heading_row,
            row_from,
            row_to,
            expected_line_item_count,
            medical_invoice,
            header_mappings,
        )

        try:
            if len(file_paths) > 1:
                return extract_documents(
                    file_paths,
                    document_type=selected_document_type,
                    row_options=row_options,
                )

            return extract_document(
                file_paths[0],
                document_type=selected_document_type,
                row_options=row_options,
            )
        except TimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail="Document extraction timed out. Try a smaller file or retry the request.",
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
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


def _extract_options(
    heading_row,
    row_from,
    row_to,
    expected_line_item_count=None,
    medical_invoice=False,
    header_mappings=None,
):
    options = {
        "heading_row": heading_row,
        "row_from": row_from,
        "row_to": row_to,
        "expected_line_item_count": expected_line_item_count,
        "medical_invoice": medical_invoice,
    }

    for label, value in options.items():
        if isinstance(value, bool):
            continue
        if value is not None and value < 1:
            raise HTTPException(status_code=400, detail=f"{label} must be greater than zero.")

    if row_from and row_to and row_from > row_to:
        raise HTTPException(status_code=400, detail="row_from cannot be greater than row_to.")

    if header_mappings:
        try:
            parsed_header_mappings = json.loads(header_mappings)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="header_mappings must be valid JSON.") from error

        if not isinstance(parsed_header_mappings, dict):
            raise HTTPException(status_code=400, detail="header_mappings must be an object.")

        options["header_mappings"] = parsed_header_mappings

    return options


def _form_upload_files(form, field_name):
    uploads = []
    for value in form.getlist(field_name):
        if getattr(value, "filename", None) and hasattr(value, "read"):
            uploads.append(value)
    return uploads


def _optional_form_str(form, field_name):
    value = form.get(field_name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _optional_form_int(form, field_name):
    value = _optional_form_str(form, field_name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid number.") from error


def _optional_form_bool(form, field_name):
    value = _optional_form_str(form, field_name)
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _write_upload_debug(
    upload_files,
    file_paths,
    document_type,
    file_field_count=0,
    files_field_count=0,
    client_file_count=None,
):
    UPLOAD_DEBUG_FILE.write_text(
        json.dumps(
            {
                "document_type": document_type,
                "file_field_count": file_field_count,
                "files_field_count": files_field_count,
                "client_file_count": client_file_count,
                "total_upload_files": len(upload_files),
                "upload_filenames": [upload_file.filename for upload_file in upload_files],
                "saved_filenames": [file_path.name for file_path in file_paths],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
