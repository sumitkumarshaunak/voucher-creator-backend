import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import load_backend_env
from prompts import BANK_STATEMENT_DATA_SCHEMA, BANK_STATEMENT_SYSTEM_PROMPT
from services.llm_service import build_json_instructions, call_llm, get_openai_client
from utils.files import file_data_uri
from utils.pdf import pdf_page_batches
from utils.spreadsheets import excel_batches


load_backend_env()

SPREADSHEET_EXTENSIONS = {".xls", ".xlsx"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_BANK_STATEMENT_EXTENSIONS = SPREADSHEET_EXTENSIONS | PDF_EXTENSIONS
EXCEL_ROWS_PER_BATCH = 100
PDF_PAGES_PER_BATCH = 5
SUPPORTED_DOCUMENT_TYPES = {"bank_statement"}
BANK_STATEMENT_MODEL = "gpt-4o"
BANK_STATEMENT_BATCH_WORKERS = int(os.environ.get("BANK_STATEMENT_BATCH_WORKERS", "4"))
BANK_STATEMENT_LLM_RETRIES = 2
BANK_STATEMENT_RETRY_BACKOFF_SECONDS = 1


def infer_document_type(file_path):
    return "bank_statement"


def _merge_results(batch_results):
    merged = {
        "bank": None,
        "account_number": None,
        "statement_period": None,
        "transactions": [],
    }

    transactions = []
    for result in batch_results:
        for field in ("bank", "account_number", "statement_period"):
            if not merged[field] and result.get(field):
                merged[field] = result.get(field)
        transactions.extend(result.get("transactions") or [])
    merged["transactions"] = transactions
    return merged


def _call_with_retry(batch_label, callback):
    for attempt in range(BANK_STATEMENT_LLM_RETRIES + 1):
        try:
            return callback()
        except Exception as error:
            if attempt >= BANK_STATEMENT_LLM_RETRIES:
                print(
                    "bank statement LLM failed:",
                    f"batch={batch_label}",
                    f"attempts={attempt + 1}",
                    f"error={error}",
                    flush=True,
                )
                raise

            print(
                "bank statement LLM retry:",
                f"batch={batch_label}",
                f"retry={attempt + 1}/{BANK_STATEMENT_LLM_RETRIES}",
                f"error={error}",
                flush=True,
            )
            time.sleep(BANK_STATEMENT_RETRY_BACKOFF_SECONDS * (attempt + 1))


def _run_batches_in_parallel(batch_jobs):
    results = [None] * len(batch_jobs)
    max_workers = max(1, min(BANK_STATEMENT_BATCH_WORKERS, len(batch_jobs)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_call_with_retry, batch_label, callback): index
            for index, batch_label, callback in batch_jobs
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    return results


def _extract_batch(client, system_prompt, batch_label, content, header_context=None):
    header_text = f"\nColumn header context:\n{header_context}\n" if header_context else ""
    return call_llm(
        model=BANK_STATEMENT_MODEL,
        instructions=system_prompt,
        input_content=(
            f"Extract bank statement transactions from this batch: {batch_label}.\n"
            "The first CSV column is the original spreadsheet row number. "
            "Extract only transaction rows present in this batch. "
            "Do not include rows from the header context unless they also appear in this batch. "
            f"{header_text}\nBatch CSV:\n{content}\n\nReturn only JSON."
        ),
        client=client,
        error_context=f"extracting bank statement batch {batch_label}",
    )


def _extract_excel_file(client, system_prompt, file_path):
    batches = excel_batches(file_path, rows_per_batch=EXCEL_ROWS_PER_BATCH)
    if not batches:
        raise RuntimeError("Could not read any rows from the spreadsheet.")

    batch_jobs = [
        (
            index,
            batch["label"],
            lambda batch=batch: _extract_batch(
                client,
                system_prompt,
                batch["label"],
                batch["content"],
                header_context=batch["header_context"],
            ),
        )
        for index, batch in enumerate(batches)
    ]

    return _merge_results(_run_batches_in_parallel(batch_jobs))


def _extract_pdf_file(client, system_prompt, file_path):
    batch_results = []
    temp_files = []
    try:
        pdf_batches = pdf_page_batches(file_path, pages_per_batch=PDF_PAGES_PER_BATCH)
        temp_files.extend(batch_file for _, batch_file in pdf_batches)
        batch_jobs = []
        for index, (batch_label, batch_file) in enumerate(pdf_batches):
            batch_jobs.append(
                (
                    index,
                    batch_label,
                    lambda batch_label=batch_label, batch_file=batch_file: call_llm(
                        model=BANK_STATEMENT_MODEL,
                        instructions=system_prompt,
                        input_content=[
                            {
                                "type": "input_file",
                                "filename": f"{file_path.stem}-{batch_label}.pdf",
                                "file_data": file_data_uri(batch_file),
                            },
                            {
                                "type": "input_text",
                                "text": (
                                    f"This PDF batch contains bank statement {batch_label}. "
                                    "Extract only transaction rows from these pages. "
                                    "Ignore opening balance, closing balance, summaries, legends, and totals. "
                                    "Return only JSON."
                                ),
                            },
                        ],
                        client=client,
                        error_context=f"extracting bank statement PDF {batch_label}",
                    ),
                )
            )

        batch_results = _run_batches_in_parallel(batch_jobs)
    finally:
        for temp_file in temp_files:
            temp_file.unlink(missing_ok=True)

    return _merge_results(batch_results)


def extract_file(file_path, document_type=None, api_key=None):
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_BANK_STATEMENT_EXTENSIONS:
        raise RuntimeError("Bank statements must be uploaded as .xls, .xlsx, or .pdf files.")

    selected_document_type = document_type or infer_document_type(file_path)
    if selected_document_type != "bank_statement":
        raise RuntimeError("bank_statement_extractor.py supports bank statements only.")

    client = get_openai_client(api_key=api_key)
    system_prompt = build_json_instructions(BANK_STATEMENT_SYSTEM_PROMPT, BANK_STATEMENT_DATA_SCHEMA)

    if suffix in SPREADSHEET_EXTENSIONS:
        result = _extract_excel_file(client, system_prompt, file_path)
    else:
        result = _extract_pdf_file(client, system_prompt, file_path)

    return {
        "document_type": selected_document_type,
        "result": result,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Extract bank statement data with OpenAI.")
    parser.add_argument("file", help="Path to the bank statement file.")
    parser.add_argument(
        "--document-type",
        choices=sorted(SUPPORTED_DOCUMENT_TYPES),
        help="Override automatic config selection.",
    )
    parser.add_argument(
        "--output",
        default="extracted.json",
        help="Where to write the extracted JSON result.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    extraction = extract_file(
        Path(args.file),
        document_type=args.document_type,
    )
    output_path = Path(args.output)
    output_path.write_text(json.dumps(extraction["result"], indent=2), encoding="utf-8")
    print(json.dumps(extraction["result"], indent=2))


if __name__ == "__main__":
    main()
