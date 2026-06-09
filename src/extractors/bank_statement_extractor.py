import argparse
import json
from pathlib import Path

from config import load_backend_env
from prompts.bank_statement_prompt import BANK_STATEMENT_SYSTEM_PROMPT
from schemas.bank_statement_schema import BANK_STATEMENT_DATA_SCHEMA
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


def _extract_batch(client, system_prompt, batch_label, content, header_context=None):
    header_text = f"\nColumn header context:\n{header_context}\n" if header_context else ""
    result = call_llm(
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
    return result


def _extract_excel_file(client, system_prompt, file_path):
    batches = excel_batches(file_path, rows_per_batch=EXCEL_ROWS_PER_BATCH)
    if not batches:
        raise RuntimeError("Could not read any rows from the spreadsheet.")

    return _merge_results(
        _extract_batch(
            client,
            system_prompt,
            batch["label"],
            batch["content"],
            header_context=batch["header_context"],
        )
        for batch in batches
    )


def _extract_pdf_file(client, system_prompt, file_path):
    batch_results = []
    temp_files = []
    try:
        for batch_label, batch_file in pdf_page_batches(file_path, pages_per_batch=PDF_PAGES_PER_BATCH):
            temp_files.append(batch_file)
            result = call_llm(
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
            )
            batch_results.append(result)
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
