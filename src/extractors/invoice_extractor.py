import argparse
import json
import os
from pathlib import Path

from config import load_backend_env
from prompts import get_invoice_data_schema, get_invoice_system_prompt
from services.llama_parse_service import parse_document
from services.llm_service import build_json_instructions, call_llm
from utils.pdf import pdf_page_batches

load_backend_env()

INVOICE_JSON_MODEL = os.environ.get("INVOICE_JSON_MODEL", "gpt-4o-mini")
INVOICE_MARKDOWN_DEBUG_FILE = os.environ.get("INVOICE_MARKDOWN_DEBUG_FILE", "last-invoice-markdown.md")
INVOICE_PAGE_JSON_DEBUG_FILE = os.environ.get("INVOICE_PAGE_JSON_DEBUG_FILE", "last-invoice-page-json.json")
PAGE_META_DELIMITER = "---PAGE_META---"

BANK_STATEMENT_EXTENSIONS = {".xls", ".xlsx"}
PDF_EXTENSIONS = {".pdf"}
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


def _write_text_debug_file(file_path, content):
    debug_path = Path(file_path)
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(content or "", encoding="utf-8")


def _write_json_debug_file(file_path, data):
    debug_path = Path(file_path)
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _reset_page_json_debug_file():
    _write_json_debug_file(INVOICE_PAGE_JSON_DEBUG_FILE, [])


def _unwrap_schema_shaped_result(result):
    if not isinstance(result, dict):
        return result

    properties = result.get("properties")
    if not isinstance(properties, dict):
        return result

    invoice_keys = {
        "page_number",
        "voucher_type",
        "invoice_no",
        "invoice_date",
        "supplier",
        "buyer",
        "invoice_header",
        "invoice_footer",
        "line_items",
        "other_charges",
        "totals",
        "transport",
        "page_audit",
    }
    if invoice_keys.intersection(properties):
        return properties

    return result


def _append_page_json_debug(page, result, normalized_result=None):
    debug_path = Path(INVOICE_PAGE_JSON_DEBUG_FILE)
    existing = []
    if debug_path.exists():
        try:
            existing = json.loads(debug_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []

    if not isinstance(existing, list):
        existing = []

    existing.append(
        {
            "page_number": (page.get("meta") or {}).get("page_number"),
            "page_meta": page.get("meta") or {},
            "result": result,
            "normalized_result": normalized_result,
        }
    )
    _write_json_debug_file(debug_path, existing)


def _split_markdown_page_blocks(markdown):
    if not markdown or PAGE_META_DELIMITER not in markdown:
        return []

    pages = []
    cursor = 0
    decoder = json.JSONDecoder()

    while True:
        delimiter_index = markdown.find(PAGE_META_DELIMITER, cursor)
        if delimiter_index == -1:
            break

        page_markdown = markdown[cursor:delimiter_index].strip()
        meta_start = delimiter_index + len(PAGE_META_DELIMITER)

        while meta_start < len(markdown) and markdown[meta_start].isspace():
            meta_start += 1

        try:
            page_meta, meta_length = decoder.raw_decode(markdown[meta_start:])
        except json.JSONDecodeError:
            return []

        meta_end = meta_start + meta_length
        pages.append({"markdown": page_markdown, "meta": page_meta})
        cursor = meta_end

    return pages


def _patched_page_markdown(page_markdown, page_meta=None, page_number=1, page_count=1):
    meta = dict(page_meta or {})
    meta["page_number"] = page_number
    meta["page_count"] = page_count
    meta["is_first_page"] = page_number == 1
    meta["is_last_page"] = page_number == page_count

    return (
        f"{page_markdown.strip()}\n\n"
        f"{PAGE_META_DELIMITER}\n"
        f"{json.dumps(meta, ensure_ascii=False)}"
    )


def _markdown_pages_from_full_markdown(markdown):
    pages = _split_markdown_page_blocks(markdown)
    page_count = len(pages)
    return [
        {
            "markdown": _patched_page_markdown(
                page["markdown"],
                page_meta=page["meta"],
                page_number=index,
                page_count=page_count,
            ),
            "meta": {**page["meta"], "page_number": index, "page_count": page_count},
        }
        for index, page in enumerate(pages, start=1)
    ]


def _markdown_pages_from_pdf_pages(file_path, api_key=None):
    page_batches = pdf_page_batches(file_path, pages_per_batch=1)
    page_count = len(page_batches)
    pages = []

    try:
        for index, (_, page_path) in enumerate(page_batches, start=1):
            parsed = parse_document(page_path, api_key=api_key)
            raw_markdown = parsed["markdown"] or parsed["text"]
            page_blocks = _split_markdown_page_blocks(raw_markdown)

            if page_blocks:
                page_markdown = page_blocks[0]["markdown"]
                page_meta = page_blocks[0]["meta"]
            else:
                page_markdown = raw_markdown
                page_meta = {}

            pages.append(
                {
                    "raw_markdown": raw_markdown,
                    "markdown": _patched_page_markdown(
                        page_markdown,
                        page_meta=page_meta,
                        page_number=index,
                        page_count=page_count,
                    ),
                    "meta": {**page_meta, "page_number": index, "page_count": page_count},
                }
            )
    finally:
        for _, page_path in page_batches:
            page_path.unlink(missing_ok=True)

    return pages


def _extract_invoice_json(
    markdown,
    text,
    api_key=None,
    expected_line_item_count=None,
    medical_invoice=False,
    page_mode=False,
):
    source_text = markdown or text
    if not source_text:
        raise RuntimeError("LlamaCloud did not return markdown or text for this invoice.")

    system_prompt = get_invoice_system_prompt(
        expected_line_item_count,
        medical_invoice=medical_invoice,
        page_mode=page_mode,
    )
    data_schema = get_invoice_data_schema(
        expected_line_item_count,
        medical_invoice=medical_invoice,
        page_mode=page_mode,
    )

    return call_llm(
        model=INVOICE_JSON_MODEL,
        instructions=build_json_instructions(system_prompt, data_schema),
        input_content=(
            "Extract the invoice JSON from this LlamaCloud markdown. "
            "Use the markdown tables as the primary source. "
            "Return only JSON.\n\n"
            f"{source_text}"
        ),
        api_key=api_key,
        error_context="extracting invoice JSON",
    )


def _filled(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _first_filled(page_results, key, default=None):
    for result in page_results:
        value = result.get(key)
        if _filled(value):
            return value
    return default


def _last_filled(page_results, key, default=None):
    for result in reversed(page_results):
        value = result.get(key)
        if _filled(value):
            return value
    return default


def _merge_dict_values(page_results, key):
    merged = {}
    for result in page_results:
        value = result.get(key)
        if isinstance(value, dict):
            merged.update({field: field_value for field, field_value in value.items() if _filled(field_value)})
    return merged


def _party_from_header(header, prefix):
    return {
        "name": header.get(f"{prefix}_name") or "",
        "gstin": header.get(f"{prefix}_gstin") or "",
        "pan": header.get(f"{prefix}_pan"),
        "mobile": header.get(f"{prefix}_mobile"),
    }


def _normalize_page_result(result):
    result = _unwrap_schema_shaped_result(result)
    normalized = dict(result)
    header = normalized.get("invoice_header") or {}
    footer = normalized.get("invoice_footer") or {}

    if header:
        normalized.setdefault("invoice_no", header.get("invoice_no") or "")
        normalized.setdefault("invoice_date", header.get("invoice_date") or "")
        normalized.setdefault("supplier", _party_from_header(header, "supplier"))
        normalized.setdefault("buyer", _party_from_header(header, "buyer"))

    if footer:
        footer_totals = {key: value for key, value in footer.items() if key != "transport"}
        normalized.setdefault("totals", footer_totals)
        normalized.setdefault("transport", footer.get("transport") or {})

    return normalized


def _merge_page_invoice_jsons(page_results, expected_line_item_count=None):
    normalized_results = [_normalize_page_result(result) for result in page_results]
    line_items = []
    other_charges = []

    for result in normalized_results:
        for item in result.get("line_items") or result.get("items") or []:
            next_item = dict(item)
            next_item["sl_no"] = len(line_items) + 1
            line_items.append(next_item)
        other_charges.extend(result.get("other_charges") or [])

    merged = {
        "page_number": 1,
        "voucher_type": _first_filled(normalized_results, "voucher_type", "Sales"),
        "invoice_no": _first_filled(normalized_results, "invoice_no", ""),
        "invoice_date": _first_filled(normalized_results, "invoice_date", ""),
        "supplier": _first_filled(normalized_results, "supplier", {"name": "", "gstin": "", "pan": None}),
        "buyer": _first_filled(normalized_results, "buyer", {"name": "", "gstin": "", "pan": None}),
        "line_items": line_items,
        "other_charges": other_charges,
        "totals": _last_filled(normalized_results, "totals", {}),
        "transport": _last_filled(normalized_results, "transport", {}),
        "tax_ledgers": _merge_dict_values(normalized_results, "tax_ledgers"),
        "charge_ledgers": _merge_dict_values(normalized_results, "charge_ledgers"),
    }

    if expected_line_item_count:
        merged["expected_line_item_count"] = expected_line_item_count
        merged["extracted_line_item_count"] = len(line_items)

    return merged


def _validate_page_result(page, result):
    result = _unwrap_schema_shaped_result(result)
    page_meta = page.get("meta") or {}
    expected_count = page_meta.get("item_count_this_page")
    if expected_count in (None, ""):
        return

    line_items = result.get("line_items") or result.get("items") or []
    if int(expected_count or 0) != len(line_items):
        page_number = page_meta.get("page_number") or "unknown"
        raise RuntimeError(
            f"Invoice page {page_number} expected {expected_count} line item(s), "
            f"but the LLM returned {len(line_items)}."
        )


def _extract_invoice_from_pages(pages, api_key=None, expected_line_item_count=None, medical_invoice=False):
    page_results = []
    for page in pages:
        page_result = _extract_invoice_json(
            page["markdown"],
            "",
            api_key=api_key,
            expected_line_item_count=None,
            medical_invoice=medical_invoice,
            page_mode=True,
        )
        normalized_page_result = _unwrap_schema_shaped_result(page_result)
        _append_page_json_debug(page, page_result, normalized_result=normalized_page_result)
        _validate_page_result(page, normalized_page_result)
        page_results.append(normalized_page_result)

    return _merge_page_invoice_jsons(page_results, expected_line_item_count=expected_line_item_count), {
        "page_llm_calls": len(page_results),
        "page_meta": [page["meta"] for page in pages],
    }


def extract_file(file_path, document_type=None, api_key=None, openai_api_key=None, row_options=None):
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    selected_document_type = document_type or infer_document_type(file_path)
    if selected_document_type != "invoice":
        raise RuntimeError("Use the bank statement extractor for bank statements. Invoice extractor supports invoices only.")

    row_options = row_options or {}
    expected_line_item_count = row_options.get("expected_line_item_count")
    medical_invoice = bool(row_options.get("medical_invoice"))

    parsed = parse_document(file_path, api_key=api_key)
    _reset_page_json_debug_file()
    if file_path.suffix.lower() in PDF_EXTENSIONS:
        pages = _markdown_pages_from_pdf_pages(file_path, api_key=api_key)
        _write_text_debug_file(
            INVOICE_MARKDOWN_DEBUG_FILE,
            "".join(page.get("raw_markdown", "") for page in pages),
        )
    else:
        _write_text_debug_file(INVOICE_MARKDOWN_DEBUG_FILE, parsed["markdown"])
        pages = _markdown_pages_from_full_markdown(parsed["markdown"])

    if pages:
        result, page_metadata = _extract_invoice_from_pages(
            pages,
            api_key=openai_api_key,
            expected_line_item_count=expected_line_item_count,
            medical_invoice=medical_invoice,
        )
    else:
        result = _unwrap_schema_shaped_result(_extract_invoice_json(
            parsed["markdown"],
            parsed["text"],
            api_key=openai_api_key,
            expected_line_item_count=expected_line_item_count,
            medical_invoice=medical_invoice,
        ))
        page_metadata = {"page_llm_calls": 0, "page_meta": []}

    return {
        "document_type": selected_document_type,
        "result": result,
        "metadata": {
            "markdown_chars": len(parsed["markdown"]),
            "text_chars": len(parsed["text"]),
            "json_model": INVOICE_JSON_MODEL,
            "expected_line_item_count": expected_line_item_count,
            "medical_invoice": medical_invoice,
            **page_metadata,
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
