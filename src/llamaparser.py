import argparse
import json
import os
import time
from pathlib import Path

from env import load_backend_env
from llama_cloud import LlamaCloud
from prompts import (
    BANK_STATEMENT_DATA_SCHEMA,
    BANK_STATEMENT_SYSTEM_PROMPT,
    INVOICE_DATA_SCHEMA,
    INVOICE_SYSTEM_PROMPT,
)

load_backend_env()

BASE_EXTRACT_CONFIGURATION = {
    "tier": "cost_effective",
    "extraction_target": "per_doc",
    "parse_tier": "agentic",
    "parse_config_id": None,
    "cite_sources": True,
    "confidence_scores": True,
}

EXTRACT_CONFIGS = {
    "invoice": {
        "data_schema": INVOICE_DATA_SCHEMA,
        "system_prompt": INVOICE_SYSTEM_PROMPT,
        "configuration": BASE_EXTRACT_CONFIGURATION,
    },
    "bank_statement": {
        "data_schema": BANK_STATEMENT_DATA_SCHEMA,
        "system_prompt": BANK_STATEMENT_SYSTEM_PROMPT,
        "configuration": BASE_EXTRACT_CONFIGURATION,
    },
}

BANK_STATEMENT_EXTENSIONS = {".xls", ".xlsx"}


def infer_document_type(file_path):
    if file_path.suffix.lower() in BANK_STATEMENT_EXTENSIONS:
        return "bank_statement"

    return "invoice"


def build_extract_configuration(document_type):
    extract_config = EXTRACT_CONFIGS[document_type]
    configuration = {
        **extract_config["configuration"],
        "data_schema": extract_config["data_schema"],
        "system_prompt": extract_config["system_prompt"],
    }

    if configuration["parse_config_id"] is None:
        configuration.pop("parse_config_id")

    return configuration


def parse_args():
    parser = argparse.ArgumentParser(description="Extract voucher data with LlamaCloud.")
    parser.add_argument("file", help="Path to the invoice or bank statement file.")
    parser.add_argument(
        "--document-type",
        choices=sorted(EXTRACT_CONFIGS),
        help="Override automatic config selection. XLS/XLSX files default to bank_statement; other files default to invoice.",
    )
    parser.add_argument(
        "--output",
        default="extracted.json",
        help="Where to write the extracted JSON result.",
    )

    return parser.parse_args()


def extract_file(file_path, document_type=None, api_key=None):
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    selected_document_type = document_type or infer_document_type(file_path)
    selected_api_key = api_key or os.environ.get("LLAMA_CLOUD_API_KEY")

    if not selected_api_key:
        raise RuntimeError("Set LLAMA_CLOUD_API_KEY before running the parser.")

    client = LlamaCloud(api_key=selected_api_key)
    file_obj = client.files.create(file=str(file_path), purpose="extract")

    job = client.extract.create(
        file_input=file_obj.id,
        configuration=build_extract_configuration(selected_document_type),
    )

    while job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
        time.sleep(2)
        job = client.extract.get(job.id)

    if job.status != "COMPLETED":
        raise RuntimeError(f"Extract job {job.id} ended in {job.status}: {job.error_message}")

    return {
        "document_type": selected_document_type,
        "result": job.extract_result,
        "metadata": job.extract_metadata.model_dump() if job.extract_metadata else None,
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

    field_metadata = (extraction["metadata"] or {}).get("field_metadata")
    if field_metadata:
        for field, meta in (field_metadata.get("document_metadata") or {}).items():
            print(f"{field}: {meta}")


if __name__ == "__main__":
    main()
