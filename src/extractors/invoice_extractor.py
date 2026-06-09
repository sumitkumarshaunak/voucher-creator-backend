import argparse
import json
import os
from pathlib import Path

from config import load_backend_env
from prompts import INVOICE_DATA_SCHEMA, INVOICE_SYSTEM_PROMPT
from services.llama_parse_service import parse_document
from services.llm_service import build_json_instructions, call_llm

load_backend_env()

INVOICE_JSON_MODEL = os.environ.get("INVOICE_JSON_MODEL", "gpt-4o-mini")

BANK_STATEMENT_EXTENSIONS = {".xls", ".xlsx"}
SUPPORTED_DOCUMENT_TYPES = {"invoice"}


def infer_document_type(file_path):
    if file_path.suffix.lower() in BANK_STATEMENT_EXTENSIONS:
        return "bank_statement"

    return "invoice"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract voucher data with LlamaCloud.")
    parser.add_argument("file", help="Path to the invoice or bank statement file.")
    parser.add_argument(
        "--document-type",
        choices=sorted(SUPPORTED_DOCUMENT_TYPES),
        help="Override automatic config selection. This parser supports invoices only.",
    )
    parser.add_argument(
        "--output",
        default="extracted.json",
        help="Where to write the extracted JSON result.",
    )

    return parser.parse_args()


def _extract_invoice_json(markdown, text, api_key=None):
    source_text = markdown or text
    if not source_text:
        raise RuntimeError("LlamaCloud did not return markdown or text for this invoice.")

    return call_llm(
        model=INVOICE_JSON_MODEL,
        instructions=build_json_instructions(INVOICE_SYSTEM_PROMPT, INVOICE_DATA_SCHEMA),
        input_content=(
            "Extract the invoice JSON from this LlamaCloud markdown. "
            "Use the markdown tables as the primary source. "
            "Return only JSON.\n\n"
            f"{source_text}"
        ),
        api_key=api_key,
        error_context="extracting invoice JSON",
    )


def extract_file(file_path, document_type=None, api_key=None, openai_api_key=None):
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    selected_document_type = document_type or infer_document_type(file_path)
    if selected_document_type != "invoice":
        raise RuntimeError("Use the bank statement extractor for bank statements. Invoice extractor supports invoices only.")

    parsed = parse_document(file_path, api_key=api_key)

    return {
        "document_type": selected_document_type,
        "result": _extract_invoice_json(
            parsed["markdown"],
            parsed["text"],
            api_key=openai_api_key,
        ),
        "metadata": {
            "markdown_chars": len(parsed["markdown"]),
            "text_chars": len(parsed["text"]),
            "json_model": INVOICE_JSON_MODEL,
        },
    }


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
