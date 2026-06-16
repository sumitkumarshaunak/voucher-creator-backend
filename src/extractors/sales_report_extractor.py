import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from utils.spreadsheets import _spreadsheet_rows, format_cell_value


SPREADSHEET_EXTENSIONS = {".xls", ".xlsx"}
SUPPORTED_DOCUMENT_TYPES = {"sales_report"}
SELLER_GST_STATE_CODE = "06"

DEFAULT_HEADER_MAPPINGS = {
    "0": "invoice_date",
    "1": "invoice_no",
    "2": "party_name",
    "3": "gst",
    "4": "sale",
    "5": "invoice_total",
}
SUPPORTED_COLUMNS = set(DEFAULT_HEADER_MAPPINGS.values())
REQUIRED_COLUMNS = {"invoice_date", "invoice_no", "party_name", "invoice_total"}

SALE_REPORT_COLUMNS = {
    "invoice_date": ["date"],
    "invoice_no": ["invoice no"],
    "party_name": ["party name"],
    "gstin": ["gstin"],
    "transaction_type": ["transaction type"],
    "invoice_total": ["total amount"],
    "payment_type": ["payment type"],
    "received_amount": ["received/paid amount"],
    "balance_due": ["balance due"],
}

ITEM_COLUMNS = {
    "invoice_date": ["date"],
    "invoice_no": ["invoice no./txn no.", "invoice no", "txn no"],
    "party_name": ["party name"],
    "item_name": ["item name"],
    "item_code": ["item code"],
    "hsn": ["hsn/sac", "hsn"],
    "category": ["category"],
    "lot_number": ["lot number"],
    "expiry_date": ["exp. date", "expiry date"],
    "units": ["units"],
    "packing_size": ["packing size/ bags", "packing size", "bags"],
    "quantity": ["quantity"],
    "unit": ["unit"],
    "rate": ["unitprice", "unit price"],
    "discount_percent": ["discount percent"],
    "discount_amount": ["discount"],
    "gst_rate": ["tax percent"],
    "tax_amount": ["tax"],
    "transaction_type": ["transaction type"],
    "line_total": ["amount"],
}


def _normalize_key(value):
    return re.sub(r"[^a-z0-9]+", " ", format_cell_value(value).lower()).strip()


def _normalize_header_mappings(row_options):
    raw_mappings = (row_options or {}).get("header_mappings") or DEFAULT_HEADER_MAPPINGS
    normalized = {}

    for column_index, field_name in raw_mappings.items():
        if field_name not in SUPPORTED_COLUMNS:
            continue
        try:
            normalized[int(column_index)] = field_name
        except (TypeError, ValueError):
            continue

    missing_columns = REQUIRED_COLUMNS - set(normalized.values())
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Sales report mapping is missing: {missing}.")

    return normalized


def _format_date_value(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return format_cell_value(value)


def _parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = format_cell_value(value).replace(",", "")
    if not text:
        return None

    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _round_amount(value):
    return round(float(value or 0), 2)


def _totals_match(first_amount, second_amount):
    return abs(_round_amount(first_amount) - _round_amount(second_amount)) <= 0.01


def _cell(row, column_index):
    return row[column_index] if column_index is not None and column_index < len(row) else None


def _sheet_lookup(rows_by_sheet):
    return {sheet_name.strip().lower(): rows for sheet_name, rows in rows_by_sheet}


def _column_map(header_row, aliases):
    normalized_headers = [_normalize_key(value) for value in header_row]
    mapped = {}
    for field_name, field_aliases in aliases.items():
        alias_keys = {_normalize_key(alias) for alias in field_aliases}
        for index, header in enumerate(normalized_headers):
            if header in alias_keys:
                mapped[field_name] = index
                break
    return mapped


def _find_header_row(sheet_rows, aliases, preferred_row=None):
    required_aliases = set(aliases)
    if preferred_row and preferred_row <= len(sheet_rows):
        columns = _column_map(sheet_rows[preferred_row - 1], aliases)
        if {"invoice_no", "party_name"}.issubset(columns):
            return preferred_row, columns

    for row_number, row in enumerate(sheet_rows[:50], start=1):
        columns = _column_map(row, aliases)
        if {"invoice_no", "party_name"}.issubset(columns) and len(required_aliases & set(columns)) >= 4:
            return row_number, columns

    raise ValueError("Could not find the sales report header row.")


def _normalize_flat_row(row_number, row, header_mappings):
    parsed = {"row_number": row_number}

    for column_index, field_name in header_mappings.items():
        value = _cell(row, column_index)
        if field_name == "invoice_date":
            parsed[field_name] = _format_date_value(value)
        elif field_name == "invoice_total":
            parsed[field_name] = _parse_number(value)
            parsed["invoice_total_raw"] = format_cell_value(value)
        else:
            parsed[field_name] = format_cell_value(value)

    return parsed


def _is_total_or_empty_row(parsed):
    values = [
        parsed.get("invoice_date"),
        parsed.get("invoice_no"),
        parsed.get("party_name"),
        parsed.get("gst"),
        parsed.get("sale"),
        parsed.get("invoice_total_raw"),
    ]
    if not any(format_cell_value(value) for value in values):
        return True

    if not format_cell_value(parsed.get("invoice_no")) or parsed.get("invoice_total") is None:
        return True

    row_text = " ".join(format_cell_value(value).lower() for value in values)
    return row_text in {"total", "grand total"} or row_text.startswith("total ")


def _extract_flat_rows(sheet_rows, sheet_name, row_options):
    heading_row = (row_options or {}).get("heading_row")
    if not heading_row:
        raise ValueError("Select the sales report heading row before parsing.")

    header_mappings = _normalize_header_mappings(row_options)
    row_from = (row_options or {}).get("row_from") or (heading_row + 1)
    row_to = (row_options or {}).get("row_to")
    rows = []

    for row_number, row in enumerate(sheet_rows, start=1):
        if row_number < row_from or (row_to and row_number > row_to):
            continue

        parsed = _normalize_flat_row(row_number, row, header_mappings)
        if _is_total_or_empty_row(parsed):
            continue

        parsed["sheet_name"] = sheet_name
        rows.append(parsed)

    return rows, header_mappings


def _mapped_value(row, columns, field_name):
    return _cell(row, columns.get(field_name))


def _invoice_summary(row_number, row, columns):
    return {
        "row_number": row_number,
        "invoice_date": _format_date_value(_mapped_value(row, columns, "invoice_date")),
        "invoice_no": format_cell_value(_mapped_value(row, columns, "invoice_no")),
        "party_name": format_cell_value(_mapped_value(row, columns, "party_name")),
        "gstin": format_cell_value(_mapped_value(row, columns, "gstin")),
        "transaction_type": format_cell_value(_mapped_value(row, columns, "transaction_type")),
        "invoice_total": _parse_number(_mapped_value(row, columns, "invoice_total")),
        "payment_type": format_cell_value(_mapped_value(row, columns, "payment_type")),
        "received_amount": _parse_number(_mapped_value(row, columns, "received_amount")),
        "balance_due": _parse_number(_mapped_value(row, columns, "balance_due")),
    }


def _item_detail(row_number, row, columns):
    return {
        "row_number": row_number,
        "invoice_date": _format_date_value(_mapped_value(row, columns, "invoice_date")),
        "invoice_no": format_cell_value(_mapped_value(row, columns, "invoice_no")),
        "party_name": format_cell_value(_mapped_value(row, columns, "party_name")),
        "item_name": format_cell_value(_mapped_value(row, columns, "item_name")),
        "item_code": format_cell_value(_mapped_value(row, columns, "item_code")),
        "hsn": format_cell_value(_mapped_value(row, columns, "hsn")),
        "category": format_cell_value(_mapped_value(row, columns, "category")),
        "lot_number": format_cell_value(_mapped_value(row, columns, "lot_number")),
        "expiry_date": _format_date_value(_mapped_value(row, columns, "expiry_date")),
        "units": _parse_number(_mapped_value(row, columns, "units")),
        "packing_size": format_cell_value(_mapped_value(row, columns, "packing_size")),
        "quantity": _parse_number(_mapped_value(row, columns, "quantity")),
        "unit": format_cell_value(_mapped_value(row, columns, "unit")),
        "rate": _parse_number(_mapped_value(row, columns, "rate")),
        "discount_percent": _parse_number(_mapped_value(row, columns, "discount_percent")),
        "discount_amount": _parse_number(_mapped_value(row, columns, "discount_amount")),
        "gst_rate": _parse_number(_mapped_value(row, columns, "gst_rate")),
        "tax_amount": _parse_number(_mapped_value(row, columns, "tax_amount")),
        "transaction_type": format_cell_value(_mapped_value(row, columns, "transaction_type")),
        "line_total": _parse_number(_mapped_value(row, columns, "line_total")),
    }


def _sale_report_summaries(sheet_rows, row_options):
    header_row, columns = _find_header_row(
        sheet_rows,
        SALE_REPORT_COLUMNS,
        preferred_row=(row_options or {}).get("heading_row"),
    )
    summaries = []
    for row_number, row in enumerate(sheet_rows[header_row:], start=header_row + 1):
        summary = _invoice_summary(row_number, row, columns)
        if not summary["invoice_no"] or not summary["party_name"]:
            continue
        summaries.append(summary)
    return summaries, header_row


def _item_details(sheet_rows, row_options):
    header_row, columns = _find_header_row(
        sheet_rows,
        ITEM_COLUMNS,
        preferred_row=(row_options or {}).get("heading_row"),
    )
    items = []
    for row_number, row in enumerate(sheet_rows[header_row:], start=header_row + 1):
        item = _item_detail(row_number, row, columns)
        if not item["invoice_no"] or not item["item_name"]:
            continue
        items.append(item)
    return items, header_row


def _tax_split(gstin, tax_amount):
    tax_amount = _round_amount(tax_amount)
    if tax_amount <= 0:
        return {"cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0}

    state_code = format_cell_value(gstin)[:2]
    if not state_code or state_code == SELLER_GST_STATE_CODE:
        half_tax = _round_amount(tax_amount / 2)
        return {
            "cgst_amount": half_tax,
            "sgst_amount": _round_amount(tax_amount - half_tax),
            "igst_amount": 0,
        }

    return {"cgst_amount": 0, "sgst_amount": 0, "igst_amount": tax_amount}


def _voucher_line_item(item, gstin):
    line_total = _round_amount(item.get("line_total"))
    tax_amount = _round_amount(item.get("tax_amount"))
    taxable_amount = _round_amount(line_total - tax_amount)
    tax_split = _tax_split(gstin, tax_amount)

    return {
        "description": item["item_name"],
        "stock_item_name": item["item_name"],
        "stock_item_unit": item.get("unit") or "",
        "hsn": item.get("hsn") or "",
        "hsn_code": item.get("hsn") or "",
        "category": item.get("category") or "",
        "batch_name": item.get("lot_number") or "",
        "expiry_date": item.get("expiry_date") or "",
        "quantity": item.get("quantity") or "",
        "qty": item.get("quantity") or "",
        "unit": item.get("unit") or "",
        "rate": item.get("rate") or "",
        "discount_percent": item.get("discount_percent") or 0,
        "discount_amount": item.get("discount_amount") or 0,
        "gst_rate": item.get("gst_rate") or 0,
        "taxable_amount": taxable_amount,
        "line_total": line_total,
        **tax_split,
    }


def _is_sale_transaction(summary):
    transaction_type = format_cell_value(summary.get("transaction_type")).lower()
    return transaction_type.startswith("sale")


def _sales_voucher(summary, items):
    line_items = [_voucher_line_item(item, summary.get("gstin")) for item in items]
    taxable_value = _round_amount(sum(item.get("taxable_amount") or 0 for item in line_items))
    total_cgst = _round_amount(sum(item.get("cgst_amount") or 0 for item in line_items))
    total_sgst = _round_amount(sum(item.get("sgst_amount") or 0 for item in line_items))
    total_igst = _round_amount(sum(item.get("igst_amount") or 0 for item in line_items))
    item_total = _round_amount(taxable_value + total_cgst + total_sgst + total_igst)
    sales_total = _round_amount(summary.get("invoice_total") or item_total)
    grand_total = sales_total
    total_difference = _round_amount(sales_total - item_total)

    return {
        "document_type": "Invoice",
        "voucher_type": "Sales",
        "invoice_no": summary["invoice_no"],
        "invoice_date": summary["invoice_date"],
        "party_ledger": summary["party_name"],
        "buyer": {
            "name": summary["party_name"],
            "gstin": summary.get("gstin") or "",
        },
        "supplier": {},
        "base_ledger": "",
        "transaction_type": summary.get("transaction_type") or "",
        "payment_type": summary.get("payment_type") or "",
        "line_items": line_items,
        "items": line_items,
        "totals": {
            "taxable_value": taxable_value,
            "taxable_amount": taxable_value,
            "total_cgst": total_cgst,
            "total_sgst": total_sgst,
            "total_igst": total_igst,
            "grand_total": grand_total,
            "rounding_off": total_difference,
        },
        "total_check": {
            "sales_total": sales_total,
            "item_total": item_total,
            "difference": total_difference,
            "matched": _totals_match(sales_total, item_total),
            "selected_total_source": "sale_report",
        },
        "tax_ledgers": {},
        "charge_ledgers": {},
    }


def _build_sales_vouchers(summaries, item_details):
    items_by_invoice = defaultdict(list)
    for item in item_details:
        items_by_invoice[item["invoice_no"]].append(item)

    vouchers = []
    skipped = []
    for summary in summaries:
        invoice_no = summary["invoice_no"]
        if not _is_sale_transaction(summary):
            skipped.append({"invoice_no": invoice_no, "reason": summary.get("transaction_type") or "Not a sale"})
            continue

        invoice_items = items_by_invoice.get(invoice_no, [])
        if not invoice_items:
            skipped.append({"invoice_no": invoice_no, "reason": "No item details"})
            continue

        vouchers.append(_sales_voucher(summary, invoice_items))

    return vouchers, skipped


def extract_file(file_path, document_type=None, row_options=None):
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    if file_path.suffix.lower() not in SPREADSHEET_EXTENSIONS:
        raise ValueError("Sales reports must be uploaded as .xls or .xlsx files.")

    selected_document_type = document_type or "sales_report"
    if selected_document_type != "sales_report":
        raise ValueError("sales_report_extractor.py supports sales reports only.")

    row_options = row_options or {}
    rows_by_sheet = _spreadsheet_rows(file_path)
    sheets = _sheet_lookup(rows_by_sheet)
    sale_rows = sheets.get("sale report")
    item_rows = sheets.get("item details")
    if not sale_rows or not item_rows:
        raise ValueError("Sales report workbook must contain 'Sale Report' and 'Item Details' sheets.")

    flat_rows, header_mappings = _extract_flat_rows(sale_rows, "Sale Report", row_options)
    summaries, sale_header_row = _sale_report_summaries(sale_rows, row_options)
    item_details, item_header_row = _item_details(item_rows, row_options)
    vouchers, skipped_vouchers = _build_sales_vouchers(summaries, item_details)
    mismatched_vouchers = [voucher for voucher in vouchers if not voucher.get("total_check", {}).get("matched")]
    sale_rows = [row for row in flat_rows if format_cell_value(row.get("sale")).lower().startswith("sale")]
    total_invoice_amount = sum(row.get("invoice_total") or 0 for row in sale_rows)

    return {
        "document_type": selected_document_type,
        "result": {
            "document_type": selected_document_type,
            "heading_row": row_options.get("heading_row"),
            "columns": {field_name: column_index for column_index, field_name in header_mappings.items()},
            "rows": flat_rows,
            "vouchers": vouchers,
            "item_details": item_details,
            "skipped_vouchers": skipped_vouchers,
            "summary": {
                "row_count": len(flat_rows),
                "voucher_count": len(vouchers),
                "item_count": len(item_details),
                "skipped_voucher_count": len(skipped_vouchers),
                "mismatch_count": len(mismatched_vouchers),
                "total_invoice_amount": total_invoice_amount,
                "total_voucher_amount": sum(voucher.get("totals", {}).get("grand_total") or 0 for voucher in vouchers),
                "total_mismatch_amount": sum(
                    abs(voucher.get("total_check", {}).get("difference") or 0)
                    for voucher in mismatched_vouchers
                ),
            },
            "metadata": {
                "sale_report_heading_row": sale_header_row,
                "item_details_heading_row": item_header_row,
            },
        },
    }
