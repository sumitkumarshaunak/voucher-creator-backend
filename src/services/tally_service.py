import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from xml.sax.saxutils import escape


DEFAULT_TALLY_URL = "http://127.0.0.1:9000"
DEFAULT_TALLY_TIMEOUT_SECONDS = 30
DEFAULT_TALLY_VOUCHER_BATCH_SIZE = 25
DEFAULT_TALLY_LOOKUP_BATCH_SIZE = 25
DEFAULT_TALLY_MASTER_BATCH_SIZE = 10
_selected_company = ContextVar("selected_tally_company", default=None)


@dataclass
class LedgerEntry:
    ledger_name: str
    amount: float
    is_debit: bool
    is_party: bool = False
    is_bank: bool = False


@dataclass
class InventoryEntry:
    item_name: str
    ledger_name: str
    amount: float
    is_debit: bool
    quantity: str = ""
    rate: str = ""


def post_to_tally(payload):
    document_type = payload.get("document_type")
    source = payload.get("source")
    data = payload.get("data") or {}
    company_name = _clean_text(payload.get("company_name"))

    with _tally_company(company_name):
        return _post_to_tally(document_type, source, data)


def list_tally_companies():
    return {"companies": sorted(_fetch_companies())}


def _post_to_tally(document_type, source, data):

    if document_type == "bank_statement":
        vouchers = _bank_statement_vouchers(data)
    elif document_type == "invoice":
        vouchers = _invoice_vouchers(source, data)
    else:
        raise ValueError("Unsupported document type for Tally posting.")

    if not vouchers:
        raise ValueError("No vouchers found to post to Tally.")

    _ensure_tally_company()
    unique_vouchers, duplicate_count = _unique_vouchers(vouchers)
    existing_voucher_keys = _fetch_existing_voucher_keys(unique_vouchers)
    vouchers_to_post = [
        voucher
        for voucher in unique_vouchers
        if _voucher_key(voucher) not in existing_voucher_keys
    ]
    skipped = duplicate_count + len(unique_vouchers) - len(vouchers_to_post)

    if not vouchers_to_post:
        return {
            "posted": 0,
            "skipped": skipped,
            "tally": _empty_tally_summary(),
        }

    _ensure_tally_masters(vouchers_to_post)

    response_summary = _post_vouchers_in_batches(vouchers_to_post)

    return {
        "posted": len(vouchers_to_post),
        "skipped": skipped,
        "tally": response_summary,
    }


def _env(name, default):
    return os.environ.get(name, default)


@contextmanager
def _tally_company(company_name):
    token = _selected_company.set(company_name or None)
    try:
        yield
    finally:
        _selected_company.reset(token)


def _company_name():
    return _selected_company.get() or os.environ.get("TALLY_COMPANY_NAME")


def _post_vouchers_in_batches(vouchers):
    batches = list(_chunks(vouchers, _tally_voucher_batch_size()))
    summary = _empty_tally_summary()
    summary["batches"] = len(batches)

    for index, batch in enumerate(batches, start=1):
        print(
            "posting tally voucher batch:",
            f"batch={index}/{len(batches)}",
            f"vouchers={len(batch)}",
            flush=True,
        )
        tally_xml = _build_envelope(batch)
        response_text = _send_to_tally(tally_xml)
        batch_summary = _parse_tally_response(response_text)
        summary["created"] += batch_summary["created"]
        summary["altered"] += batch_summary["altered"]
        summary["errors"] += batch_summary["errors"]
        summary["line_errors"].extend(batch_summary["line_errors"])
        summary["raw_batches"].append(batch_summary.get("raw", ""))

    return summary


def _empty_tally_summary():
    return {
        "created": 0,
        "altered": 0,
        "errors": 0,
        "line_errors": [],
        "raw_batches": [],
        "batches": 0,
    }


def _tally_voucher_batch_size():
    return max(1, int(_number(os.environ.get("TALLY_VOUCHER_BATCH_SIZE")) or DEFAULT_TALLY_VOUCHER_BATCH_SIZE))


def _tally_lookup_batch_size():
    return max(1, int(_number(os.environ.get("TALLY_LOOKUP_BATCH_SIZE")) or DEFAULT_TALLY_LOOKUP_BATCH_SIZE))


def _tally_master_batch_size():
    return max(1, int(_number(os.environ.get("TALLY_MASTER_BATCH_SIZE")) or DEFAULT_TALLY_MASTER_BATCH_SIZE))


def _chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _bank_voucher_number(statement, transaction, tally_date, amount, direction, bank_ledger):
    parts = [
        bank_ledger,
        statement.get("account_number") or "NoAccount",
        tally_date,
        transaction.get("reference") or "NoRef",
        direction,
        f"{amount:.2f}",
    ]
    return "/".join(_voucher_number_part(part) for part in parts)


def _voucher_number_part(value):
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    cleaned = cleaned.replace("/", "-").replace("|", "-")
    return cleaned or "NA"


def _unique_vouchers(vouchers):
    unique_vouchers = []
    seen_keys = set()
    duplicate_count = 0

    for voucher in vouchers:
        voucher_key = _voucher_key(voucher)
        if voucher_key in seen_keys:
            duplicate_count += 1
            continue
        seen_keys.add(voucher_key)
        unique_vouchers.append(voucher)

    return unique_vouchers, duplicate_count


def _bank_statement_vouchers(statement):
    bank_ledger = _bank_ledger(statement)
    transactions = statement.get("transactions") or []
    party_ledgers_by_identifier = _bank_statement_party_ledgers(transactions)
    vouchers = []

    for index, transaction in enumerate(transactions, start=1):
        amount = _number(transaction.get("amount"))
        if amount <= 0:
            continue

        direction = str(transaction.get("direction") or "").lower()
        party_identifier = _party_identifier(transaction)
        party_ledger = party_ledgers_by_identifier.get(party_identifier) or _party_ledger(transaction)
        date = _tally_date(transaction.get("value_date") or transaction.get("txn_date"), field_name="transaction date")
        narration = _join_narration(
            transaction.get("description"),
            _prefixed("Reference", transaction.get("reference")),
            _prefixed("Mode", transaction.get("mode")),
        )

        if direction == "credit" and _is_cash_movement(transaction):
            voucher_type = "Payment"
            entries = [
                LedgerEntry(bank_ledger, amount, True, is_bank=True),
                LedgerEntry(party_ledger, amount, False, is_party=True),
            ]
        elif direction == "credit":
            voucher_type = "Receipt"
            entries = [
                LedgerEntry(bank_ledger, amount, True, is_bank=True),
                LedgerEntry(party_ledger, amount, False, is_party=True),
            ]
        elif direction == "debit":
            voucher_type = "Payment"
            entries = [
                LedgerEntry(party_ledger, amount, True, is_party=True),
                LedgerEntry(bank_ledger, amount, False, is_bank=True),
            ]
        else:
            raise ValueError(f"Transaction {index} has an unsupported direction.")

        vouchers.append(
            {
                "date": date,
                "voucher_type": voucher_type,
                "voucher_number": _bank_voucher_number(statement, transaction, date, amount, direction, bank_ledger),
                "party_ledger": party_ledger,
                "narration": narration,
                "entries": entries,
            }
        )

    return vouchers


def _bank_ledger(statement):
    configured_ledger = _clean_text(os.environ.get("TALLY_BANK_LEDGER"))
    statement_bank = _clean_text(statement.get("bank"))
    bank_ledger = configured_ledger or statement_bank

    if not bank_ledger or bank_ledger.lower() == "bank":
        raise ValueError(
            "Bank statement needs a real bank ledger before posting. "
            "Set the Statement Bank field to the Tally bank ledger, for example 'ICICI Bank'."
        )

    return bank_ledger


def _invoice_vouchers(source, invoice):
    voucher_type = "Purchase" if source == "purchase-invoice" else "Sales"
    is_purchase = voucher_type == "Purchase"
    totals = invoice.get("totals") or {}

    party = invoice.get("seller") if is_purchase else invoice.get("buyer")
    party_ledger = (party or {}).get("name") or _env("TALLY_DEFAULT_PARTY_LEDGER", "Suspense")
    base_ledger = _env("TALLY_PURCHASE_LEDGER", "Purchase") if is_purchase else _env("TALLY_SALES_LEDGER", "Sales")
    date = _tally_date(invoice.get("invoice_date"), field_name="invoice_date")
    _validate_invoice_financial_year(invoice.get("invoice_no"), date)
    grand_total = _number(totals.get("grand_total"))
    taxable_amount = _number(totals.get("taxable_amount"))
    base_amount = taxable_amount or grand_total

    if grand_total <= 0:
        raise ValueError("Invoice grand_total must be greater than zero.")

    inventory_entries = _invoice_inventory_entries(
        invoice,
        base_ledger,
        is_debit=is_purchase,
        fallback_amount=base_amount,
    )
    base_entries = [] if inventory_entries else [LedgerEntry(base_ledger, base_amount, is_purchase)]

    if is_purchase:
        entries = [
            *base_entries,
            *_tax_entries(totals, input_tax=True),
            *_invoice_charge_entries(invoice, is_debit=True),
        ]
    else:
        entries = [
            *base_entries,
            *_tax_entries(totals, input_tax=False),
            *_invoice_charge_entries(invoice, is_debit=False),
        ]

    entries = [entry for entry in entries if abs(entry.amount) > 0]
    entries.insert(0, _counterparty_entry(party_ledger, entries, inventory_entries))

    return [
        {
            "date": date,
            "voucher_type": voucher_type,
            "voucher_number": invoice.get("invoice_no") or "",
            "party_ledger": party_ledger,
            "narration": _join_narration(
                _prefixed("Invoice", invoice.get("invoice_no")),
                _prefixed("IRN", invoice.get("irn")),
                _prefixed("Ack", invoice.get("ack_no")),
            ),
            "entries": entries,
            "inventory_entries": inventory_entries,
        }
    ]


def _tax_entries(totals, input_tax):
    prefix = "INPUT" if input_tax else "OUTPUT"
    is_debit = input_tax
    tax_fields = [
        ("cgst_amount", _env(f"TALLY_{prefix}_CGST_LEDGER", "Input CGST" if input_tax else "Output CGST")),
        ("sgst_amount", _env(f"TALLY_{prefix}_SGST_LEDGER", "Input SGST" if input_tax else "Output SGST")),
        ("igst_amount", _env(f"TALLY_{prefix}_IGST_LEDGER", "Input IGST" if input_tax else "Output IGST")),
    ]

    return [
        LedgerEntry(ledger_name, _number(totals.get(field)), is_debit)
        for field, ledger_name in tax_fields
        if _number(totals.get(field)) > 0
    ]


def _invoice_inventory_entries(invoice, ledger_name, is_debit, fallback_amount):
    items = invoice.get("items") or []
    inventory_entries = []

    for item in items:
        item_name = _clean_text(item.get("description")) or _env("TALLY_DEFAULT_STOCK_ITEM", "Item")
        amount = _number(item.get("line_total")) or _number(item.get("taxable_amount"))
        if amount == 0 and len(items) == 1:
            amount = fallback_amount
        if amount == 0:
            continue

        inventory_entries.append(
            InventoryEntry(
                item_name=item_name,
                ledger_name=ledger_name,
                amount=abs(amount),
                is_debit=is_debit if amount > 0 else not is_debit,
                quantity=_clean_text(item.get("quantity")),
                rate=_inventory_rate(item.get("rate"), item.get("quantity")),
            )
        )

    return inventory_entries


def _invoice_charge_entries(invoice, is_debit):
    entries = []
    round_off_amount = _number((invoice.get("totals") or {}).get("round_off_amount"))

    for line in invoice.get("invoice_lines") or []:
        if round_off_amount and _is_round_off_line(line):
            continue

        amount = _number(line.get("amount"))
        if amount == 0:
            continue
        ledger_name = _charge_ledger(line.get("line_type"), line.get("description"))
        entries.append(LedgerEntry(ledger_name, abs(amount), is_debit if amount > 0 else not is_debit))

    if round_off_amount:
        entries.append(
            LedgerEntry(
                _env("TALLY_ROUND_OFF_LEDGER", "Round Off"),
                abs(round_off_amount),
                is_debit if round_off_amount > 0 else not is_debit,
            )
        )

    return entries


def _charge_ledger(line_type, description):
    key = f"{line_type or ''} {description or ''}".lower()

    if "freight" in key or "transport" in key:
        return _env("TALLY_FREIGHT_LEDGER", "Freight")
    if "round" in key:
        return _env("TALLY_ROUND_OFF_LEDGER", "Round Off")
    if "pack" in key:
        return _env("TALLY_PACKING_LEDGER", "Packing Charges")
    if "insur" in key:
        return _env("TALLY_INSURANCE_LEDGER", "Insurance")

    return _env("TALLY_OTHER_CHARGES_LEDGER", "Other Charges")


def _ensure_tally_masters(vouchers):
    ledger_specs = _ledger_specs_for_vouchers(vouchers)
    ledgers = {}
    if ledger_specs:
        ledger_names = sorted(ledger_specs)
        ledgers = _fetch_ledgers(ledger_names)
        missing_ledgers = [ledger_name for ledger_name in ledger_names if ledger_name not in ledgers]
        if missing_ledgers:
            _create_ledgers({ledger_name: ledger_specs[ledger_name] for ledger_name in missing_ledgers})
            ledgers = _fetch_ledgers(ledger_names)
            missing_ledgers = [ledger_name for ledger_name in ledger_names if ledger_name not in ledgers]
        if missing_ledgers:
            _create_ledgers_individually({ledger_name: ledger_specs[ledger_name] for ledger_name in missing_ledgers})
            ledgers = _fetch_ledgers(ledger_names)
            missing_ledgers = [ledger_name for ledger_name in ledger_names if ledger_name not in ledgers]

        if missing_ledgers:
            raise ValueError(
                "Could not create these Tally ledgers: "
                + ", ".join(_missing_ledger_detail(ledger_name, ledger_specs) for ledger_name in missing_ledgers)
                + "."
            )

    stock_item_specs = _stock_item_specs_for_vouchers(vouchers)
    if stock_item_specs:
        _ensure_units({spec["unit"] for spec in stock_item_specs.values() if spec.get("unit")})
        stock_item_names = sorted(stock_item_specs)
        stock_items = _fetch_stock_items(stock_item_names)
        missing_stock_items = [item_name for item_name in stock_item_names if item_name not in stock_items]
        if missing_stock_items:
            _create_stock_items({item_name: stock_item_specs[item_name] for item_name in missing_stock_items})
            stock_items = _fetch_stock_items(stock_item_names)
            missing_stock_items = [item_name for item_name in stock_item_names if item_name not in stock_items]

        if missing_stock_items:
            raise ValueError(f"Could not create these Tally stock items: {', '.join(missing_stock_items)}.")

    for voucher in vouchers:
        voucher_type = voucher["voucher_type"]
        party_ledger = voucher.get("party_ledger")
        if not party_ledger:
            continue

        parent = ledgers.get(party_ledger, {}).get("parent", "")
        if voucher_type == "Sales" and parent.lower() != "sundry debtors":
            raise ValueError(
                f"Sales party ledger '{party_ledger}' is under '{parent}'. "
                "Move it to 'Sundry Debtors' in Tally and retry."
            )
        if voucher_type == "Purchase" and parent.lower() != "sundry creditors":
            raise ValueError(
                f"Purchase party ledger '{party_ledger}' is under '{parent}'. "
                "Move it to 'Sundry Creditors' in Tally and retry."
            )


def _ledger_specs_for_vouchers(vouchers):
    specs = {}

    for voucher in vouchers:
        voucher_type = voucher["voucher_type"]
        for entry in voucher["entries"]:
            if not entry.ledger_name:
                continue
            specs.setdefault(
                entry.ledger_name,
                {
                    "parent": _ledger_parent(voucher_type, entry),
                    "is_billwise_on": "Yes" if entry.is_party else "No",
                },
            )
        for entry in voucher.get("inventory_entries") or []:
            if not entry.ledger_name:
                continue
            specs.setdefault(
                entry.ledger_name,
                {
                    "parent": _ledger_parent(voucher_type, entry),
                    "is_billwise_on": "No",
                },
            )

    return specs


def _missing_ledger_detail(ledger_name, ledger_specs):
    parent = (ledger_specs.get(ledger_name) or {}).get("parent")
    return f"{ledger_name} (parent: {parent})" if parent else ledger_name


def _stock_item_specs_for_vouchers(vouchers):
    specs = {}

    for voucher in vouchers:
        for entry in voucher.get("inventory_entries") or []:
            if not entry.item_name:
                continue
            specs.setdefault(
                entry.item_name,
                {
                    "parent": _env("TALLY_STOCK_ITEM_PARENT", "Primary"),
                    "unit": _stock_unit(entry.quantity),
                },
            )

    return specs


def _ledger_parent(voucher_type, entry):
    ledger_name = entry.ledger_name.lower()
    is_party = getattr(entry, "is_party", False)

    if getattr(entry, "is_bank", False):
        return "Bank Accounts"
    if is_party and voucher_type == "Sales":
        return "Sundry Debtors"
    if is_party and voucher_type == "Purchase":
        return "Sundry Creditors"
    if ledger_name == _env("TALLY_BANK_LEDGER", "Bank").lower():
        return "Bank Accounts"
    if voucher_type == "Receipt" and is_party:
        return "Sundry Debtors"
    if voucher_type == "Payment" and is_party:
        return "Sundry Creditors"
    if ledger_name == _env("TALLY_SALES_LEDGER", "Sales").lower():
        return "Sales Accounts"
    if ledger_name == _env("TALLY_PURCHASE_LEDGER", "Purchase").lower():
        return "Purchase Accounts"
    if any(tax_name in ledger_name for tax_name in ("cgst", "sgst", "igst", "gst")):
        return "Duties & Taxes"

    return "Indirect Expenses"


def _create_ledgers(ledger_specs):
    batches = list(_chunks(sorted(ledger_specs.items()), _tally_master_batch_size()))
    for index, batch in enumerate(batches, start=1):
        print(
            "creating missing tally ledgers:",
            f"batch={index}/{len(batches)}",
            ", ".join(ledger_name for ledger_name, _ in batch),
            flush=True,
        )
        ledger_messages = "".join(
            _ledger_master_xml(ledger_name, spec)
            for ledger_name, spec in batch
        )
        response_text = _post_xml_to_tally(_master_import_envelope(ledger_messages))
        _raise_for_tally_line_errors(response_text, f"creating missing ledgers batch {index}/{len(batches)}")


def _create_ledgers_individually(ledger_specs):
    for ledger_name, spec in sorted(ledger_specs.items()):
        print(
            "retrying missing tally ledger individually:",
            ledger_name,
            f"parent={spec.get('parent')}",
            flush=True,
        )
        response_text = _post_xml_to_tally(_master_import_envelope(_ledger_master_xml(ledger_name, spec)))
        _raise_for_tally_line_errors(response_text, f"creating missing ledger '{ledger_name}'")


def _ledger_master_xml(ledger_name, spec):
    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<LEDGER NAME="{_xml(ledger_name)}" ACTION="Create">'
        f"<NAME>{_xml(ledger_name)}</NAME>"
        f"<PARENT>{_xml(spec['parent'])}</PARENT>"
        f"<ISBILLWISEON>{_xml(spec['is_billwise_on'])}</ISBILLWISEON>"
        "</LEDGER>"
        "</TALLYMESSAGE>"
    )


def _master_import_envelope(master_messages):
    company_name = _company_name()
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
    return (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Import</TALLYREQUEST>"
        "<TYPE>Data</TYPE>"
        "<ID>All Masters</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>"
        f"{company_variable}"
        "</STATICVARIABLES>"
        "</DESC>"
        f"<DATA>{master_messages}</DATA>"
        "</BODY>"
        "</ENVELOPE>"
    )


def _ensure_units(unit_names):
    unit_names = sorted({unit_name for unit_name in unit_names if unit_name})
    if not unit_names:
        return

    units = _fetch_units(unit_names)
    missing_units = [unit_name for unit_name in unit_names if unit_name not in units]
    if not missing_units:
        return

    _create_units(missing_units)
    units = _fetch_units(unit_names)
    missing_units = [unit_name for unit_name in unit_names if unit_name not in units]
    if missing_units:
        raise ValueError(f"Could not create these Tally units: {', '.join(missing_units)}.")


def _fetch_units(unit_names):
    units = set()
    for batch in _chunks(sorted(unit_names), _tally_lookup_batch_size()):
        units.update(_fetch_units_batch(batch))
    return units


def _fetch_units_batch(unit_names):
    formula = " OR ".join(f'$Name = "{_xml(unit_name)}"' for unit_name in unit_names)
    company_name = _company_name()
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        "<ID>Units</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        f"{company_variable}"
        "</STATICVARIABLES>"
        "<TDL>"
        "<TDLMESSAGE>"
        '<COLLECTION NAME="Units">'
        "<TYPE>Unit</TYPE>"
        "<FETCH>Name</FETCH>"
        "<FILTERS>TargetUnits</FILTERS>"
        "</COLLECTION>"
        f'<SYSTEM TYPE="Formulae" NAME="TargetUnits">{formula}</SYSTEM>'
        "</TDLMESSAGE>"
        "</TDL>"
        "</DESC>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    root = ElementTree.fromstring(response_text)
    return {
        (unit.attrib.get("NAME") or unit.findtext("NAME") or "").strip()
        for unit in root.findall(".//UNIT")
        if (unit.attrib.get("NAME") or unit.findtext("NAME") or "").strip()
    }


def _create_units(unit_names):
    batches = list(_chunks(sorted(unit_names), _tally_master_batch_size()))
    for index, batch in enumerate(batches, start=1):
        print(
            "creating missing tally units:",
            f"batch={index}/{len(batches)}",
            ", ".join(batch),
            flush=True,
        )
        unit_messages = "".join(_unit_master_xml(unit_name) for unit_name in batch)
        response_text = _post_xml_to_tally(_master_import_envelope(unit_messages))
        _raise_for_tally_line_errors(response_text, f"creating missing units batch {index}/{len(batches)}")


def _unit_master_xml(unit_name):
    formal_name = _unit_formal_name(unit_name)
    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<UNIT NAME="{_xml(unit_name)}" ACTION="Create">'
        f"<NAME>{_xml(unit_name)}</NAME>"
        f"<ORIGINALNAME>{_xml(unit_name)}</ORIGINALNAME>"
        "<ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>"
        f"<SYMBOL>{_xml(unit_name)}</SYMBOL>"
        f"<FORMALNAME>{_xml(formal_name)}</FORMALNAME>"
        "<NUMBEROFDECIMALPLACES>3</NUMBEROFDECIMALPLACES>"
        "</UNIT>"
        "</TALLYMESSAGE>"
    )


def _fetch_stock_items(item_names):
    stock_items = set()
    for batch in _chunks(sorted(item_names), _tally_lookup_batch_size()):
        stock_items.update(_fetch_stock_items_batch(batch))
    return stock_items


def _fetch_stock_items_batch(item_names):
    formula = " OR ".join(f'$Name = "{_xml(item_name)}"' for item_name in item_names)
    company_name = _company_name()
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        "<ID>StockItems</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        f"{company_variable}"
        "</STATICVARIABLES>"
        "<TDL>"
        "<TDLMESSAGE>"
        '<COLLECTION NAME="StockItems">'
        "<TYPE>StockItem</TYPE>"
        "<FETCH>Name</FETCH>"
        "<FILTERS>TargetStockItems</FILTERS>"
        "</COLLECTION>"
        f'<SYSTEM TYPE="Formulae" NAME="TargetStockItems">{formula}</SYSTEM>'
        "</TDLMESSAGE>"
        "</TDL>"
        "</DESC>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    root = ElementTree.fromstring(response_text)
    return {
        (item.attrib.get("NAME") or item.findtext("NAME") or "").strip()
        for item in root.findall(".//STOCKITEM")
        if (item.attrib.get("NAME") or item.findtext("NAME") or "").strip()
    }


def _create_stock_items(stock_item_specs):
    batches = list(_chunks(sorted(stock_item_specs.items()), _tally_master_batch_size()))
    for index, batch in enumerate(batches, start=1):
        print(
            "creating missing tally stock items:",
            f"batch={index}/{len(batches)}",
            ", ".join(item_name for item_name, _ in batch),
            flush=True,
        )
        stock_item_messages = "".join(
            _stock_item_master_xml(item_name, spec)
            for item_name, spec in batch
        )
        response_text = _post_xml_to_tally(_master_import_envelope(stock_item_messages))
        _raise_for_tally_line_errors(response_text, f"creating missing stock items batch {index}/{len(batches)}")


def _stock_item_master_xml(item_name, spec):
    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<STOCKITEM NAME="{_xml(item_name)}" ACTION="Create">'
        f"<NAME>{_xml(item_name)}</NAME>"
        f"<PARENT>{_xml(spec['parent'])}</PARENT>"
        f"<BASEUNITS>{_xml(spec['unit'])}</BASEUNITS>"
        "</STOCKITEM>"
        "</TALLYMESSAGE>"
    )


def _ensure_tally_company():
    company_name = _company_name()
    if not company_name:
        return

    companies = _fetch_companies()
    if company_name in companies:
        return

    if _selected_company.get():
        raise ValueError(f"Tally company '{company_name}' is not loaded or does not exist.")

    _create_company(company_name)
    companies = _fetch_companies()
    if company_name not in companies:
        raise ValueError(f"Could not create or load Tally company '{company_name}'.")


def _fetch_companies():
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        "<ID>Companies</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        "</STATICVARIABLES>"
        "<TDL>"
        "<TDLMESSAGE>"
        '<COLLECTION NAME="Companies">'
        "<TYPE>Company</TYPE>"
        "<FETCH>Name</FETCH>"
        "</COLLECTION>"
        "</TDLMESSAGE>"
        "</TDL>"
        "</DESC>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    root = ElementTree.fromstring(response_text)
    return {
        element.text.strip()
        for element in root.findall(".//COMPANY/NAME")
        if element.text and element.text.strip()
    }


def _create_company(company_name):
    start_date = os.environ.get("TALLY_COMPANY_START_DATE", "20260401")
    print("creating missing tally company:", company_name, flush=True)
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Import</TALLYREQUEST>"
        "<TYPE>Data</TYPE>"
        "<ID>All Masters</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>"
        "</STATICVARIABLES>"
        "</DESC>"
        "<DATA>"
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<COMPANY NAME="{_xml(company_name)}" ACTION="Create">'
        f"<NAME>{_xml(company_name)}</NAME>"
        f"<MAILINGNAME>{_xml(company_name)}</MAILINGNAME>"
        f"<STARTINGFROM>{_xml(start_date)}</STARTINGFROM>"
        f"<BOOKSFROM>{_xml(start_date)}</BOOKSFROM>"
        "</COMPANY>"
        "</TALLYMESSAGE>"
        "</DATA>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    _raise_for_tally_line_errors(response_text, f"creating company '{company_name}'")


def _fetch_ledgers(ledger_names):
    ledgers = {}
    for batch in _chunks(sorted(ledger_names), _tally_lookup_batch_size()):
        ledgers.update(_fetch_ledgers_batch(batch))
    return ledgers


def _fetch_ledgers_batch(ledger_names):
    requested_names_by_lower = {ledger_name.lower(): ledger_name for ledger_name in ledger_names}
    formula = " OR ".join(f'$Name = "{_xml(ledger_name)}"' for ledger_name in ledger_names)
    company_name = _company_name()
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        "<ID>Ledgers</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        f"{company_variable}"
        "</STATICVARIABLES>"
        "<TDL>"
        "<TDLMESSAGE>"
        '<COLLECTION NAME="Ledgers">'
        "<TYPE>Ledger</TYPE>"
        "<FETCH>Name,Parent</FETCH>"
        "<FILTERS>TargetLedgers</FILTERS>"
        "</COLLECTION>"
        f'<SYSTEM TYPE="Formulae" NAME="TargetLedgers">{formula}</SYSTEM>'
        "</TDLMESSAGE>"
        "</TDL>"
        "</DESC>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    root = ElementTree.fromstring(response_text)
    ledgers = {}
    for ledger in root.findall(".//LEDGER"):
        name = (ledger.attrib.get("NAME") or "").strip()
        parent = ledger.findtext("PARENT") or ""
        if name:
            spec = {"parent": parent.strip()}
            ledgers[name] = spec
            requested_name = requested_names_by_lower.get(name.lower())
            if requested_name:
                ledgers[requested_name] = spec
            for alias in _ledger_aliases(ledger):
                ledgers[alias] = spec
                requested_alias = requested_names_by_lower.get(alias.lower())
                if requested_alias:
                    ledgers[requested_alias] = spec

    return ledgers


def _ledger_aliases(ledger):
    return {
        alias.text.strip()
        for alias in ledger.findall(".//NAME.LIST/NAME")
        if alias.text and alias.text.strip()
    }


def _fetch_existing_voucher_keys(vouchers):
    voucher_keys = {
        _voucher_key(voucher)
        for voucher in vouchers
        if voucher.get("voucher_type") and voucher.get("voucher_number")
    }
    if not voucher_keys:
        return set()

    existing_keys = set()
    for batch in _chunks(sorted(voucher_keys), _tally_lookup_batch_size()):
        existing_keys.update(_fetch_existing_voucher_keys_batch(batch))

    return existing_keys


def _fetch_existing_voucher_keys_batch(voucher_keys):
    filters = " OR ".join(
        (
            "("
            f'$VoucherTypeName = "{_xml(voucher_type)}"'
            " AND "
            f'$VoucherNumber = "{_xml(voucher_number)}"'
            ")"
        )
        for voucher_type, voucher_number in voucher_keys
    )
    company_name = _company_name()
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
    request_xml = (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        "<ID>ExistingVouchers</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        f"{company_variable}"
        "</STATICVARIABLES>"
        "<TDL>"
        "<TDLMESSAGE>"
        '<COLLECTION NAME="ExistingVouchers">'
        "<TYPE>Voucher</TYPE>"
        "<FETCH>VoucherTypeName,VoucherNumber</FETCH>"
        "<FILTERS>TargetVouchers</FILTERS>"
        "</COLLECTION>"
        f'<SYSTEM TYPE="Formulae" NAME="TargetVouchers">{filters}</SYSTEM>'
        "</TDLMESSAGE>"
        "</TDL>"
        "</DESC>"
        "</BODY>"
        "</ENVELOPE>"
    )

    response_text = _post_xml_to_tally(request_xml)
    root = ElementTree.fromstring(response_text)
    existing_keys = set()
    for voucher in root.findall(".//VOUCHER"):
        voucher_type = (voucher.findtext("VOUCHERTYPENAME") or "").strip()
        voucher_number = (voucher.findtext("VOUCHERNUMBER") or "").strip()
        if voucher_type and voucher_number:
            existing_keys.add((voucher_type, voucher_number))

    return existing_keys


def _voucher_key(voucher):
    return (voucher.get("voucher_type") or "", voucher.get("voucher_number") or "")


def _counterparty_entry(party_ledger, entries, inventory_entries=None):
    balance = sum(_signed_amount(entry) for entry in entries)
    balance += sum(_signed_inventory_amount(entry) for entry in inventory_entries or [])
    if balance == 0:
        raise ValueError("Invoice voucher has no ledger amount to balance.")

    return LedgerEntry(party_ledger, abs(balance), balance < 0, is_party=True)


def _signed_amount(entry):
    return abs(entry.amount) if entry.is_debit else -abs(entry.amount)


def _signed_inventory_amount(entry):
    return abs(entry.amount) if entry.is_debit else -abs(entry.amount)


def _is_round_off_line(line):
    key = f"{line.get('line_type') or ''} {line.get('description') or ''}".lower()
    return "round" in key or "r/off" in key


def _validate_invoice_financial_year(invoice_no, tally_date):
    if not invoice_no or not tally_date:
        return

    match = re.search(r"(?<!\d)(\d{2})(\d{2})(?!\d)", str(invoice_no))
    if not match:
        return

    start_year = 2000 + int(match.group(1))
    end_year = 2000 + int(match.group(2))
    if end_year != start_year + 1:
        return

    voucher_date = datetime.strptime(tally_date, "%Y%m%d")
    financial_year_start = datetime(start_year, 4, 1)
    financial_year_end = datetime(end_year, 3, 31)

    if financial_year_start <= voucher_date <= financial_year_end:
        return

    raise ValueError(
        f"Invoice number '{invoice_no}' indicates FY {start_year}-{str(end_year)[-2:]}, "
        f"but invoice date is {voucher_date.strftime('%d-%b-%Y')}. "
        f"Use a date from {financial_year_start.strftime('%d-%b-%Y')} to "
        f"{financial_year_end.strftime('%d-%b-%Y')}."
    )


def _build_envelope(vouchers):
    company_name = _company_name()
    import_id = os.environ.get("TALLY_IMPORT_ID", "Vouchers")
    static_variables = "<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>"
    if company_name:
        static_variables += f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"

    voucher_messages = "".join(_voucher_xml(voucher) for voucher in vouchers)

    return (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Import</TALLYREQUEST>"
        "<TYPE>Data</TYPE>"
        f"<ID>{_xml(import_id)}</ID>"
        "</HEADER>"
        "<BODY>"
        "<DESC>"
        f"<STATICVARIABLES>{static_variables}</STATICVARIABLES>"
        "</DESC>"
        f"<DATA>{voucher_messages}</DATA>"
        "</BODY>"
        "</ENVELOPE>"
    )


def _voucher_xml(voucher):
    entries = "".join(_ledger_entry_xml(entry) for entry in voucher["entries"])
    inventory_entries = "".join(
        _inventory_entry_xml(entry)
        for entry in voucher.get("inventory_entries") or []
    )
    voucher_date = _xml(voucher["date"])
    narration = _xml(voucher.get("narration") or "")
    narration_xml = f"<NARRATION>{narration}</NARRATION>" if narration else ""
    voucher_number = _xml(voucher.get("voucher_number") or "")
    voucher_number_xml = f"<VOUCHERNUMBER>{voucher_number}</VOUCHERNUMBER>" if voucher_number else ""
    voucher_view = _voucher_view(voucher)
    voucher_view_xml = (
        f"<PERSISTEDVIEW>{_xml(voucher_view)}</PERSISTEDVIEW>"
        f"<OBJVIEW>{_xml(voucher_view)}</OBJVIEW>"
    )

    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<VOUCHER VCHTYPE="{_xml(voucher["voucher_type"])}" ACTION="Create">'
        f"<DATE>{voucher_date}</DATE>"
        f"<EFFECTIVEDATE>{voucher_date}</EFFECTIVEDATE>"
        f"<VOUCHERTYPENAME>{_xml(voucher['voucher_type'])}</VOUCHERTYPENAME>"
        f"{voucher_view_xml}"
        f"{voucher_number_xml}"
        f"{narration_xml}"
        f"<PARTYLEDGERNAME>{_xml(voucher.get('party_ledger') or '')}</PARTYLEDGERNAME>"
        f"<ISINVOICE>{_is_invoice_voucher(voucher)}</ISINVOICE>"
        f"{entries}"
        f"{inventory_entries}"
        "</VOUCHER>"
        "</TALLYMESSAGE>"
    )


def _ledger_entry_xml(entry):
    amount = _tally_amount(entry)
    deemed_positive = "Yes" if entry.is_debit else "No"
    is_party_ledger = "Yes" if entry.is_party else "No"

    return (
        "<ALLLEDGERENTRIES.LIST>"
        f"<LEDGERNAME>{_xml(entry.ledger_name)}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>{deemed_positive}</ISDEEMEDPOSITIVE>"
        f"<ISPARTYLEDGER>{is_party_ledger}</ISPARTYLEDGER>"
        f"<AMOUNT>{amount:.2f}</AMOUNT>"
        "</ALLLEDGERENTRIES.LIST>"
    )


def _voucher_view(voucher):
    if voucher.get("voucher_type") in {"Receipt", "Payment", "Contra", "Journal"}:
        return "Accounting Voucher View"
    if voucher.get("inventory_entries"):
        return "Invoice Voucher View"
    return "Accounting Voucher View"


def _inventory_entry_xml(entry):
    amount = _tally_amount(entry)
    deemed_positive = "Yes" if entry.is_debit else "No"
    quantity_xml = ""
    if entry.quantity:
        quantity_xml = (
            f"<ACTUALQTY>{_xml(entry.quantity)}</ACTUALQTY>"
            f"<BILLEDQTY>{_xml(entry.quantity)}</BILLEDQTY>"
        )
    rate_xml = f"<RATE>{_xml(entry.rate)}</RATE>" if entry.rate else ""

    return (
        "<ALLINVENTORYENTRIES.LIST>"
        f"<STOCKITEMNAME>{_xml(entry.item_name)}</STOCKITEMNAME>"
        f"<ISDEEMEDPOSITIVE>{deemed_positive}</ISDEEMEDPOSITIVE>"
        f"{quantity_xml}"
        f"{rate_xml}"
        f"<AMOUNT>{amount:.2f}</AMOUNT>"
        "<ACCOUNTINGALLOCATIONS.LIST>"
        f"<LEDGERNAME>{_xml(entry.ledger_name)}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>{deemed_positive}</ISDEEMEDPOSITIVE>"
        f"<AMOUNT>{amount:.2f}</AMOUNT>"
        "</ACCOUNTINGALLOCATIONS.LIST>"
        "</ALLINVENTORYENTRIES.LIST>"
    )


def _tally_amount(entry):
    return -abs(entry.amount) if entry.is_debit else abs(entry.amount)


def _is_invoice_voucher(voucher):
    return "Yes" if voucher.get("voucher_type") in {"Sales", "Purchase"} else "No"


def _send_to_tally(tally_xml):
    debug_xml_path = os.environ.get("TALLY_DEBUG_XML_PATH", "last-tally-request.xml")
    if debug_xml_path:
        request_path = Path(debug_xml_path).resolve()
        request_path.write_text(tally_xml, encoding="utf-8")
        print(
            "tally request xml saved:",
            f"path={request_path}",
            f"bytes={request_path.stat().st_size}",
            flush=True,
        )

    response_text = _post_xml_to_tally(tally_xml)
    debug_response_path = os.environ.get("TALLY_DEBUG_RESPONSE_PATH", "last-tally-response.xml")
    if debug_response_path:
        response_path = Path(debug_response_path).resolve()
        response_path.write_text(response_text, encoding="utf-8")
        print(
            "tally response xml saved:",
            f"path={response_path}",
            f"bytes={response_path.stat().st_size}",
            flush=True,
        )
    return response_text


def _post_xml_to_tally(tally_xml):
    tally_url = os.environ.get("TALLY_URL", DEFAULT_TALLY_URL)
    timeout_seconds = _number(os.environ.get("TALLY_TIMEOUT_SECONDS")) or DEFAULT_TALLY_TIMEOUT_SECONDS
    _write_tally_debug_file("TALLY_DEBUG_XML_PATH", "last-tally-request.xml", tally_xml, "request")
    print(
        "posting xml to tally:",
        f"url={tally_url}",
        f"company={_company_name() or '(active company)'}",
        f"import_id={os.environ.get('TALLY_IMPORT_ID', 'Vouchers')}",
        f"timeout={timeout_seconds:g}s",
        f"bytes={len(tally_xml.encode('utf-8'))}",
        flush=True,
    )
    request = Request(
        tally_url,
        data=tally_xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8", errors="replace")
            _write_tally_debug_file("TALLY_DEBUG_RESPONSE_PATH", "last-tally-response.xml", response_text, "response")
            return response_text
    except TimeoutError as error:
        raise RuntimeError(
            f"Tally did not respond within {timeout_seconds:g} seconds at {tally_url}. "
            "Check that Tally is running, the company is open, and HTTP access is enabled."
        ) from error
    except URLError as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, TimeoutError):
            raise RuntimeError(
                f"Tally did not respond within {timeout_seconds:g} seconds at {tally_url}. "
                "Check that Tally is running, the company is open, and HTTP access is enabled."
            ) from error
        raise RuntimeError(f"Could not reach Tally at {tally_url}: {reason}") from error


def _write_tally_debug_file(env_name, default_path, content, label):
    debug_path = os.environ.get(env_name, default_path)
    if not debug_path:
        return

    path = Path(debug_path).resolve()
    path.write_text(content, encoding="utf-8")
    print(
        f"tally {label} xml saved:",
        f"path={path}",
        f"bytes={path.stat().st_size}",
        flush=True,
    )


def _parse_tally_response(response_text):
    summary = {
        "created": 0,
        "altered": 0,
        "errors": 0,
        "line_errors": [],
        "raw": response_text,
    }

    try:
        root = ElementTree.fromstring(response_text)
    except ElementTree.ParseError:
        return summary

    for key in ("CREATED", "ALTERED", "ERRORS"):
        element = root.find(f".//{key}")
        if element is not None and element.text:
            summary[key.lower()] = int(_number(element.text))

    summary["line_errors"] = [
        element.text.strip()
        for element in root.findall(".//LINEERROR")
        if element.text and element.text.strip()
    ]

    if summary["errors"] or summary["line_errors"]:
        raise RuntimeError("; ".join(summary["line_errors"]) or "Tally reported an import error.")

    return summary


def _raise_for_tally_line_errors(response_text, context):
    try:
        root = ElementTree.fromstring(response_text)
    except ElementTree.ParseError as error:
        raise RuntimeError(f"Tally returned invalid XML while {context}.") from error

    line_errors = [
        element.text.strip()
        for element in root.findall(".//LINEERROR")
        if element.text and element.text.strip()
    ]
    exceptions = int(_number(root.findtext(".//EXCEPTIONS")))
    errors = int(_number(root.findtext(".//ERRORS")))

    if line_errors or exceptions or errors:
        detail = "; ".join(line_errors) or f"Tally reported {errors} errors and {exceptions} exceptions."
        raise RuntimeError(f"Tally failed while {context}: {detail}")


def _party_ledger(transaction):
    return (
        _clean_text(transaction.get("party_name"))
        or _party_identifier(transaction)
        or _clean_text(transaction.get("reference"))
        or _env("TALLY_DEFAULT_PARTY_LEDGER", "Suspense")
    )


def _is_cash_movement(transaction):
    mode = str(transaction.get("mode") or "").strip().lower()
    party_name = str(transaction.get("party_name") or "").strip().lower()
    party_identifier = str(transaction.get("party_identifier") or "").strip().lower()

    return "cash" in {mode, party_name, party_identifier}


def _bank_statement_party_ledgers(transactions):
    ledger_by_identifier = {}

    for transaction in transactions:
        party_identifier = _party_identifier(transaction)
        party_name = _clean_text(transaction.get("party_name"))
        if party_identifier and party_name and party_identifier not in ledger_by_identifier:
            ledger_by_identifier[party_identifier] = party_name

    for transaction in transactions:
        party_identifier = _party_identifier(transaction)
        if party_identifier and party_identifier not in ledger_by_identifier:
            ledger_by_identifier[party_identifier] = _party_ledger(transaction)

    return ledger_by_identifier


def _party_identifier(transaction):
    return _clean_text(transaction.get("party_identifier"))


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _quantity_unit(quantity):
    text = _clean_text(quantity)
    if not text:
        return ""

    without_numbers = re.sub(r"[-+]?\d[\d,]*(?:\.\d+)?", "", text)
    without_separators = re.sub(r"[/()]", " ", without_numbers)
    unit = re.sub(r"\s+", " ", without_separators).strip()
    return unit or ""


def _stock_unit(quantity):
    unit = _quantity_unit(quantity) or _env("TALLY_DEFAULT_STOCK_UNIT", "Nos")
    return _unit_alias(unit)


def _unit_alias(unit):
    normalized_unit = _clean_text(unit)
    aliases = _mapping_env(
        "TALLY_STOCK_UNIT_ALIASES",
        {
            "mt": "MT",
            "mts": "MT",
            "m.t.": "MT",
            "metric ton": "MT",
            "metric tons": "MT",
            "ton": "MT",
            "tons": "MT",
            "tonne": "MT",
            "tonnes": "MT",
            "nos": "Nos",
            "no": "Nos",
            "pcs": "Nos",
            "piece": "Nos",
            "pieces": "Nos",
        },
    )
    return aliases.get(normalized_unit.lower(), normalized_unit)


def _unit_formal_name(unit_name):
    formal_names = _mapping_env(
        "TALLY_STOCK_UNIT_FORMAL_NAMES",
        {
            "mt": "Metric Ton",
            "nos": "Numbers",
        },
    )
    return formal_names.get(_clean_text(unit_name).lower(), unit_name)


def _mapping_env(name, defaults):
    mapping = {str(key).lower(): value for key, value in defaults.items()}
    raw = os.environ.get(name) or ""
    for item in raw.split(","):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            mapping[key] = value
    return mapping


def _inventory_rate(rate, quantity):
    text = _clean_text(rate)
    if not text or "/" in text:
        return text

    unit = _stock_unit(quantity)
    return f"{text}/{unit}" if unit else text


def _tally_date(value, field_name="date"):
    if not value:
        raise ValueError(f"{field_name} is required before posting to Tally.")

    text = str(value).strip()
    numeric_match = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$", text)
    if numeric_match:
        month = int(numeric_match.group(2))
        year = int(numeric_match.group(3))
        if year < 100:
            year += 2000
        if 1 <= month <= 12:
            return datetime(year, month, 1).strftime("%Y%m%d")

    normalized_text = (
        text.replace(",", " ")
        .replace("'", "")
        .replace("Sept", "Sep")
    )
    normalized_text = re.sub(r"\s+", " ", normalized_text)
    candidates = [
        normalized_text,
        normalized_text.split()[0],
        normalized_text.replace(".", "-"),
        normalized_text.replace("/", "-"),
        normalized_text.replace(" ", "-"),
    ]
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d-%B-%Y",
        "%d-%B-%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d/%b/%Y",
        "%d/%b/%y",
        "%d %m %Y",
        "%d %m %y",
        "%d %b %Y",
        "%d %b %y",
        "%d %B %Y",
        "%d %B %y",
        "%b %d %Y",
        "%b %d %y",
        "%B %d %Y",
        "%B %d %y",
    ]

    for candidate in candidates:
        for date_format in formats:
            try:
                parsed_date = datetime.strptime(candidate, date_format)
                return parsed_date.replace(day=1).strftime("%Y%m%d")
            except ValueError:
                pass

    raise ValueError(f"{field_name} '{value}' is not a valid date. Use a date like 30-04-2026.")


def _number(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, int | float):
        return float(value)

    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if cleaned in {"", "-", "."}:
        return 0.0

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _join_narration(*parts):
    return " | ".join(str(part).strip() for part in parts if part)


def _prefixed(label, value):
    return f"{label}: {value}" if value else ""


def _xml(value):
    return escape(str(value), {'"': "&quot;"})
