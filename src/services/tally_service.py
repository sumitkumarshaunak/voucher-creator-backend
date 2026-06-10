import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from xml.sax.saxutils import escape


DEFAULT_TALLY_URL = "http://127.0.0.1:9000"


@dataclass
class LedgerEntry:
    ledger_name: str
    amount: float
    is_debit: bool
    is_party: bool = False


def post_to_tally(payload):
    document_type = payload.get("document_type")
    source = payload.get("source")
    data = payload.get("data") or {}

    if document_type == "bank_statement":
        vouchers = _bank_statement_vouchers(data)
    elif document_type == "invoice":
        vouchers = _invoice_vouchers(source, data)
    else:
        raise ValueError("Unsupported document type for Tally posting.")

    if not vouchers:
        raise ValueError("No vouchers found to post to Tally.")

    _ensure_tally_company()
    _ensure_tally_masters(vouchers)

    tally_xml = _build_envelope(vouchers)
    response_text = _send_to_tally(tally_xml)
    response_summary = _parse_tally_response(response_text)

    return {
        "posted": len(vouchers),
        "tally": response_summary,
    }


def _env(name, default):
    return os.environ.get(name, default)


def _bank_statement_vouchers(statement):
    bank_ledger = _env("TALLY_BANK_LEDGER", statement.get("bank") or "Bank")
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

        if direction == "credit":
            voucher_type = "Receipt"
            entries = [
                LedgerEntry(bank_ledger, amount, True),
                LedgerEntry(party_ledger, amount, False, is_party=True),
            ]
        elif direction == "debit":
            voucher_type = "Payment"
            entries = [
                LedgerEntry(party_ledger, amount, True, is_party=True),
                LedgerEntry(bank_ledger, amount, False),
            ]
        else:
            raise ValueError(f"Transaction {index} has an unsupported direction.")

        vouchers.append(
            {
                "date": date,
                "voucher_type": voucher_type,
                "voucher_number": transaction.get("tran_id") or transaction.get("reference") or "",
                "party_ledger": party_ledger,
                "narration": narration,
                "entries": entries,
            }
        )

    return vouchers


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

    if grand_total <= 0:
        raise ValueError("Invoice grand_total must be greater than zero.")

    if is_purchase:
        entries = [
            LedgerEntry(base_ledger, taxable_amount or grand_total, True),
            *_tax_entries(totals, input_tax=True),
            *_invoice_charge_entries(invoice, is_debit=True),
        ]
    else:
        entries = [
            LedgerEntry(base_ledger, taxable_amount or grand_total, False),
            *_tax_entries(totals, input_tax=False),
            *_invoice_charge_entries(invoice, is_debit=False),
        ]

    entries = [entry for entry in entries if abs(entry.amount) > 0]
    entries.insert(0, _counterparty_entry(party_ledger, entries))

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
    if not ledger_specs:
        return

    ledger_names = sorted(ledger_specs)
    ledgers = _fetch_ledgers(ledger_names)
    missing_ledgers = [ledger_name for ledger_name in ledger_names if ledger_name not in ledgers]
    if missing_ledgers:
        _create_ledgers({ledger_name: ledger_specs[ledger_name] for ledger_name in missing_ledgers})
        ledgers = _fetch_ledgers(ledger_names)
        missing_ledgers = [ledger_name for ledger_name in ledger_names if ledger_name not in ledgers]

    if missing_ledgers:
        raise ValueError(f"Could not create these Tally ledgers: {', '.join(missing_ledgers)}.")

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

    return specs


def _ledger_parent(voucher_type, entry):
    ledger_name = entry.ledger_name.lower()

    if entry.is_party and voucher_type == "Sales":
        return "Sundry Debtors"
    if entry.is_party and voucher_type == "Purchase":
        return "Sundry Creditors"
    if ledger_name == _env("TALLY_BANK_LEDGER", "Bank").lower():
        return "Bank Accounts"
    if voucher_type == "Receipt" and entry.is_party:
        return "Sundry Debtors"
    if voucher_type == "Payment" and entry.is_party:
        return "Sundry Creditors"
    if ledger_name == _env("TALLY_SALES_LEDGER", "Sales").lower():
        return "Sales Accounts"
    if ledger_name == _env("TALLY_PURCHASE_LEDGER", "Purchase").lower():
        return "Purchase Accounts"
    if any(tax_name in ledger_name for tax_name in ("cgst", "sgst", "igst", "gst")):
        return "Duties & Taxes"

    return "Indirect Expenses"


def _create_ledgers(ledger_specs):
    print(
        "creating missing tally ledgers:",
        ", ".join(sorted(ledger_specs)),
        flush=True,
    )
    ledger_messages = "".join(
        _ledger_master_xml(ledger_name, spec)
        for ledger_name, spec in sorted(ledger_specs.items())
    )
    company_name = os.environ.get("TALLY_COMPANY_NAME")
    company_variable = (
        f"<SVCURRENTCOMPANY>{_xml(company_name)}</SVCURRENTCOMPANY>"
        if company_name
        else ""
    )
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
        f"{company_variable}"
        "</STATICVARIABLES>"
        "</DESC>"
        f"<DATA>{ledger_messages}</DATA>"
        "</BODY>"
        "</ENVELOPE>"
    )
    response_text = _post_xml_to_tally(request_xml)
    _raise_for_tally_line_errors(response_text, "creating missing ledgers")


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


def _ensure_tally_company():
    company_name = os.environ.get("TALLY_COMPANY_NAME")
    if not company_name:
        return

    companies = _fetch_companies()
    if company_name in companies:
        return

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
    formula = " OR ".join(f'$Name = "{_xml(ledger_name)}"' for ledger_name in ledger_names)
    company_name = os.environ.get("TALLY_COMPANY_NAME")
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
        name = ledger.attrib.get("NAME")
        parent = ledger.findtext("PARENT") or ""
        if name:
            ledgers[name] = {"parent": parent.strip()}

    return ledgers


def _counterparty_entry(party_ledger, entries):
    balance = sum(_signed_amount(entry) for entry in entries)
    if balance == 0:
        raise ValueError("Invoice voucher has no ledger amount to balance.")

    return LedgerEntry(party_ledger, abs(balance), balance < 0, is_party=True)


def _signed_amount(entry):
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
    company_name = os.environ.get("TALLY_COMPANY_NAME")
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
    voucher_date = _xml(voucher["date"])
    voucher_number = _xml(voucher.get("voucher_number") or "")
    voucher_number_xml = f"<VOUCHERNUMBER>{voucher_number}</VOUCHERNUMBER>" if voucher_number else ""

    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<VOUCHER VCHTYPE="{_xml(voucher["voucher_type"])}" ACTION="Create">'
        f"<DATE>{voucher_date}</DATE>"
        f"<EFFECTIVEDATE>{voucher_date}</EFFECTIVEDATE>"
        f"<VOUCHERTYPENAME>{_xml(voucher['voucher_type'])}</VOUCHERTYPENAME>"
        f"{voucher_number_xml}"
        f"<PARTYLEDGERNAME>{_xml(voucher.get('party_ledger') or '')}</PARTYLEDGERNAME>"
        f"<ISINVOICE>{_is_invoice_voucher(voucher)}</ISINVOICE>"
        f"{entries}"
        "</VOUCHER>"
        "</TALLYMESSAGE>"
    )


def _ledger_entry_xml(entry):
    amount = abs(entry.amount) if entry.is_debit else -abs(entry.amount)
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
    print(
        "posting xml to tally:",
        f"url={tally_url}",
        f"company={os.environ.get('TALLY_COMPANY_NAME') or '(active company)'}",
        f"import_id={os.environ.get('TALLY_IMPORT_ID', 'Vouchers')}",
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
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(f"Could not reach Tally at {tally_url}: {reason}") from error


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
