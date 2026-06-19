from copy import deepcopy


INVOICE_DATA_SCHEMA = {
    "description": "Minimal schema to extract GST tax invoice data and post a Purchase or Sales voucher.",
    "type": "object",
    "required": [
        "voucher_type",
        "invoice_no",
        "invoice_date",
        "supplier",
        "buyer",
        "line_items",
        "totals",
        "page_number",
    ],
    "additionalProperties": False,

    "properties": {

        "page_number": {
            "type": "integer",
            "description": "The page number of the invoice."
        },

        "voucher_type": {
            "type": "string",
            "enum": ["Purchase", "Sales"],
            "description": (
                "Tally VOUCHERTYPENAME. "
                "Determined by which party is SHUBHAM STEEL & FERTILIZERS PRIVATE LTD (GSTIN prefix 06ABMCS5444E or 08ABMCS5444E): "
                "if Shubham Steel is the SUPPLIER (issuer/seller) → 'Sales'. "
                "If Shubham Steel is the BUYER (bill-to / consignee) → 'Purchase'. "
                "When Shubham Steel does not appear on the invoice, "
                "use context: 'Purchase' if the company whose books are being posted is the buyer, 'Sales' if it is the seller."
            )
        },

        "invoice_no": {
            "type": "string",
            "description": "Supplier's invoice number exactly as printed. Used as Tally bill reference."
        },

        "invoice_date": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            "description": "YYYY-MM-DD. Common printed formats: '30-04-2026', '30-Apr-26', '30/04/2026', '30.04.2026'."
        },

        "supplier": {
            "type": "object",
            "description": "Seller / issuer of the invoice.",
            "required": ["name", "gstin", "pan", "mobile"],
            "additionalProperties": False,
            "properties": {
                "name":  {"type": "string", "description": "Legal name as printed on invoice."},
                "gstin": {"type": "string", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
                "pan":   {"type": ["string", "null"]},
                "mobile":{"type": ["string", "null"], "description": "Supplier's mobile number exactly as printed, if present."}
            }
        },

        "buyer": {
            "type": "object",
            "description": "Purchaser / bill-to party.",
            "required": ["name", "gstin", "pan", "mobile"],
            "additionalProperties": False,
            "properties": {
                "name":  {"type": "string"},
                "gstin": {"type": "string", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
                "pan":   {"type": ["string", "null"]},
                "mobile": {"type":["string", "null"], "description": "Purchaser's mobile number exactly as printed, if present."}
            }
        },

        "line_items": {
            "type": "array",
            "minItems": 1,
            "description": "One entry per printed invoice row. Maps to Tally INVENTORYENTRIES.LIST.",
            "items": {
                "type": "object",
                "required": [
                    "sl_no",
                    "description",
                    "hsn",
                    "qty",
                    "unit",
                    "rate",
                    "taxable_amount",
                    "discount_percentage",
                    "discount_amount",
                    "gst_rate",
                    "igst_amount",
                    "cgst_amount",
                    "sgst_amount",
                    "cess_amount",
                    "line_total",
                ],
                "additionalProperties": False,
                "properties": {
                    "sl_no":          {"type": "integer", "minimum": 1},
                    "description":    {"type": "string", "description": "Item description as printed."},
                    "hsn":            {"type": "string", "description": "HSN code for goods, SAC for services."},
                    "qty":            {"type": ["number", "null"]},
                    "unit":           {"type": ["string", "null"], "description": "e.g. MT, KG, NOS."},
                    "rate":           {"type": ["number", "null"], "description": "Price per unit before tax."},
                    "taxable_amount": {
                        "type": "number",
                        "description": (
                            "Pre-tax subtotal for this line = qty × rate minus any discount. "
                            "IMPORTANT: Many invoice formats show a combined Amount() column that includes tax — "
                            "do NOT use that column as taxable_amount. "
                            "The taxable_amount is always the value BEFORE GST is added. "
                            "Verify: taxable_amount × (1 + gst_rate/100) ≈ line_total."
                        )
                    },
                    "discount_amount": {
                        "type": ["number", "null"],
                        "description": "Item discount amount only from an explicit discount amount column; otherwise null. Never use scheme/free/bonus values here.",
                    },
                    "discount_percentage": {
                        "type": ["number", "null"],
                        "description": "Item discount percentage only from an explicit discount percentage/cash discount column; otherwise null. Never use scheme/free/bonus percentage or values here.",
                    },
                    "gst_rate":        {"type": "number", "description": "Total GST % e.g. 18."},
                    "igst_amount":     {"type": "number", "default": 0, "description": "0 if intra-state."},
                    "cgst_amount":     {"type": "number", "default": 0, "description": "0 if inter-state."},
                    "sgst_amount":     {"type": "number", "default": 0, "description": "0 if inter-state."},
                    "cess_amount":     {"type": "number", "default": 0},
                    "line_total":      {
                        "type": "number",
                        "description": (
                            "taxable_amount + igst_amount + cgst_amount + sgst_amount + cess_amount for this line. "
                            "Copy directly from the printed Amount() column if available, preserving all decimal places. "
                            "Rounding off is applied at the invoice level, not per line."
                        )
                    }
                }
            }
        },

        "other_charges": {
            "type": "array",
            "description": (
                "Invoice-level charges listed as separate line items (e.g. Freight, Material Insurance, Packing). "
                "Include only if explicitly printed on the invoice and included in the invoice totals. "
                "Do not invent charges not shown."
            ),
            "items": {
                "type": "object",
                "required": ["description", "amount"],
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "hsn":         {"type": "string"},
                    "amount":      {"type": "number"},
                    "gst_rate":    {"type": "number", "default": 0},
                    "igst_amount": {"type": "number", "default": 0},
                    "cgst_amount": {"type": "number", "default": 0},
                    "sgst_amount": {"type": "number", "default": 0}
                }
            }
        },

        "totals": {
            "type": "object",
            "description": "Invoice footer totals. All values must match the printed document exactly.",
            "required": ["taxable_value", "grand_total"],
            "additionalProperties": False,
            "properties": {
                "taxable_value":       {"type": "number"},
                "total_igst":          {"type": "number", "default": 0},
                "total_cgst":          {"type": "number", "default": 0},
                "total_sgst":          {"type": "number", "default": 0},
                "total_cess":          {"type": "number", "default": 0},
                "total_other_charges": {"type": "number", "default": 0},
                "rounding_off":        {
                    "type": "number",
                    "default": 0,
                    "description": (
                        "Signed rounding adjustment as printed. "
                        "Positive (Add: Rounded Off (+)) means added to total. "
                        "Negative (Less: Rounded Off (-)) means deducted."
                    )
                },
                "grand_total":     {
                    "type": "number",
                    "description": (
                        "Copy the Grand Total / Amount Chargeable exactly as printed — do not recompute. "
                        "Indian number format: 12,57,109 = 1257109. "
                        "Always verify against the amount-in-words field as a cross-check."
                    )
                },
                "amount_in_words": {"type": "string"}
            }
        },

        "transport": {
            "type": "object",
            "description": "Logistics details from the invoice and/or accompanying e-Way Bill / LR.",
            "additionalProperties": False,
            "properties": {
                "transporter":    {"type": "string"},
                "vehicle_no":     {"type": "string"},
                "lr_no":          {"type": ["string", "null"]},
                "lr_date":        {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "from":           {"type": "string"},
                "to":             {"type": ["string", "null"]},
                "freight_terms":  {
                    "type": "string",
                    "enum": ["Prepaid", "To Pay", "FOB", "Paid"],
                    "description": "Who bears freight cost. Default 'To Pay' if not stated."
                },
                "freight_amount": {
                    "type": "number",
                    "description": (
                        "Freight amount as stated on the LR/bilty, if a separate LR document is present. "
                        "Set to 0 if no LR freight amount is explicitly printed. "
                        "Do NOT use the invoice grand total as the freight amount."
                    )
                }
            }
        }
    }
}


INVOICE_SYSTEM_PROMPT = """
You are a GST invoice data extraction specialist for Indian businesses. The invoice you are
processing may be from any industry — steel trading, medical/pharma distribution, construction
materials, chemicals, FMCG, or any other sector. Adapt your extraction to the specific invoice
format and line item fields present in the input.

Your task: read ONE PAGE of a parsed invoice (markdown table + PAGE_META JSON) and output a
single PageLineItems JSON object for that page only. Multiple page outputs will be merged
downstream — do NOT wait for other pages or attempt to produce a full invoice summary.

The JSON will be consumed by a program that posts a voucher to TallyPrime via XML import —
accuracy is critical.

---

## INPUT FORMAT
Each input contains two sections separated by `---PAGE_META---`:
1. **Markdown section** — the parsed invoice page as a markdown table.
2. **PAGE_META section** — a JSON object pre-computed by the parser with:
   - `page_number`
   - `page_type`: tax_invoice | eway_bill | lr_consignment | other
   - `item_count_this_page`: data rows the parser counted on this page
   - `item_serial_numbers`: exact list of S.No values the parser saw
   - `first_sno_this_page` / `last_sno_this_page`: S.No range for this page
   - `bf_amount`: carry-forward subtotal at top of page (null on page 1)
   - `has_grand_total`: true only on the final invoice page
   - `printed_total_items`: the "TOTAL ITEMS : N" footer value, if present

**PAGE_META is your ground truth for row count. Extract exactly `item_count_this_page` rows.**

---

## EXTRACTION RULES

### 1  invoice_header
- Populate only when `PAGE_META.bf_amount` is null (first invoice page). Set to null on all continuation pages.
- Extract from the header section above the item table:
  - `invoice_no`: exactly as printed
  - `invoice_date`: normalize to YYYY-MM-DD
  - `payment_mode`: exactly as printed
  - `supplier_name`, `supplier_gstin`: issuing party
  - `buyer_name`, `buyer_gstin`: bill-to party (buyer_gstin null if absent)
  - `supply_type`: "Intra-State" or "Inter-State" (see Rule 3)

### 2  GST supply type
- Compare first 2 digits of `supplier_gstin` vs `buyer_gstin`.
- If buyer GSTIN is absent → default to Intra-State.
- Same state code → **Intra-State** → per line: `cgst_amount` = `sgst_amount` = taxable_amount × (gst_rate / 2 / 100); `igst_amount` = 0.
- Different state codes → **Inter-State** → per line: `igst_amount` = taxable_amount × (gst_rate / 100); `cgst_amount` = `sgst_amount` = 0.

### 3  invoice_footer
- Populate only when `PAGE_META.has_grand_total` is true. Set to null on all other pages.
- Extract from the summary section below the item table:
  - `taxable_value`, `total_igst`, `total_cgst`, `total_sgst`, `total_cess`: as printed, 0 if absent
  - `total_other_charges`: 0 if absent
  - `rounding_off`: positive if "Add: Rounded Off (+)", negative if "Less: Rounded Off (-)", 0 if absent
  - `grand_total`: copy exactly as printed — do NOT recompute; verify against `amount_in_words`
  - `amount_in_words`: exactly as printed
  - `transport` (all fields null/0 if absent):
    - `transporter`, `vehicle_no`, `lr_no`, `lr_date` (YYYY-MM-DD)
    - `freight_terms`: exactly as printed, default "To Pay"
    - `freight_amount`: from LR/bilty only; 0 if no LR freight amount is printed

### 5  Column layout — identify once per page before reading any row
Read the header row of the item table and map each column to its schema field.
Column names vary by invoice type — use the closest match from the variants below:

| Schema field       | Common column name variants                          |
|--------------------|------------------------------------------------------|
| `sl_no`            | S.N., Sr., No., #                                    |
| `hsn`              | HSN, HSN/SAC, HSN Code                               |
| `description`      | ITEM NAME, Description, Particulars, Material        |
| `qty`              | QTY, Quantity, Nos, MT, KG                           |
| `unit`             | Unit, UOM — infer from pack/qty if absent            |
| `rate`             | RATE, Price, Unit Price                              |
| `discount_percentage` | Disc %, Discount %, DIS. %, CD % — null if absent |
| `discount_amount`  | Disc. Amt, Discount Amt, Discount Value — null if absent |
| `gst_rate`         | GST, GST%, IGST Rate, Tax Rate — strip %             |
| `line_total`       | TAX AMT., Amount(), Total, Net Amt — copy exactly    |

If a column is absent, use null for strings and nullable numbers; use 0 only for GST/tax amounts that are absent.
**line_total always includes GST — never assign it directly to `taxable_amount`.**

### Discount vs Scheme — never conflate these two fields

- `discount_percentage`: map ONLY from a column explicitly labelled Disc %, Discount %, DIS. %, CD %, or equivalent discount/cash-discount labels.
  Set to 0 if no such column exists or the value is blank/zero.
- `scheme_percentage`: map ONLY from a column explicitly labelled "Scheme%", "SCH%", "Scheme",
  or similar. Set to null if absent.

These are independent fields. A scheme column must never be mapped to `discount_percentage`
and a discount column must never be mapped to `scheme_percentage`. If both columns exist, extract both values separately. If only one exists, extract it and set the other to null/0.

### 6  `taxable_amount` — back-calculate from TAX AMT.
  taxable_amount = line_total ÷ (1 + gst_rate / 100)

Cross-check: taxable_amount × (1 + gst_rate / 100) must equal line_total (within ₹0.02).
If it doesn't match, re-read the row.

Then compute:
- Intra-State: cgst_amount = sgst_amount = round(taxable_amount × gst_rate / 2 / 100, 2); igst_amount = 0
- Inter-State: igst_amount = round(taxable_amount × gst_rate / 100, 2); cgst_amount = sgst_amount = 0
- cess_amount = 0 unless explicitly printed

### 7  MANDATORY ROW COUNT GATE

  **GATE 1 — Read PAGE_META first**
  Record before touching the markdown:
    EXPECTED_COUNT = item_count_this_page
    EXPECTED_SNOS  = item_serial_numbers
    FIRST_SNO      = first_sno_this_page
    LAST_SNO       = last_sno_this_page

  **GATE 2 — Count rows before extracting**
  Count rows where the first cell matches a number in EXPECTED_SNOS → MARKDOWN_COUNT.
  Exclude: header row, B/F row, subtotal/total rows, blank rows.
  If MARKDOWN_COUNT ≠ EXPECTED_COUNT → re-scan before proceeding.

  **GATE 3 — Extract row by row in S.No order**
  Process FIRST_SNO to LAST_SNO in sequence.
  - Row has no S.No but has ITEM NAME and TAX AMT → standalone item, assign next sequential sl_no.
  - Row has no S.No and no TAX AMT → description continuation, append to previous item's description only.
  - Rows containing "B/F", "Subtotal", "Total", "TOTAL ITEMS" → skip entirely.

  **GATE 4 — Verify before outputting**
  If len(line_items) ≠ EXPECTED_COUNT → re-scan from Gate 2. Do not output until they match.

### 8  Amounts
- Plain JSON numbers only — no ₹, no commas, no quotes.
- Indian number format: 1,253.42 → 1253.42
- Preserve all decimal places exactly as printed.

---

## OUTPUT RULES

- Output **only the JSON object** — no explanation, no markdown fences, no preamble.
- Strictly follow the provided PageLineItems JSON schema.
- String fields not found: null. Number fields not found: 0.
- Do not hallucinate values.

---

## FINAL CHECKLIST — run before outputting

1. `page_audit.count_verified` is true — if not, re-extract.
2. `page_audit.serial_match` is true — serial_numbers_extracted exactly equals PAGE_META.item_serial_numbers.
3. Every line: taxable_amount × (1 + gst_rate/100) ≈ line_total (within ₹0.02).
4. All amounts are plain numbers — no commas, no currency symbols.
5. Every `expiry_date` is in YYYY-MM format.
6. `page_audit.page_line_total` equals sum of all line_total values on this page.
7. `invoice_header` non-null only if PAGE_META.bf_amount is null.
8. `invoice_footer` non-null only if PAGE_META.has_grand_total is true.
9. `grand_total` matches `amount_in_words` — if conflict, trust the words.
"""

def _invoice_header_schema():
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "invoice_no": {"type": ["string", "null"]},
            "invoice_date": {"type": ["string", "null"]},
            "payment_mode": {"type": ["string", "null"]},
            "supplier_name": {"type": ["string", "null"]},
            "supplier_gstin": {"type": ["string", "null"]},
            "supplier_pan": {"type": ["string", "null"]},
            "supplier_mobile": {"type": ["string", "null"]},
            "buyer_name": {"type": ["string", "null"]},
            "buyer_gstin": {"type": ["string", "null"]},
            "buyer_pan": {"type": ["string", "null"]},
            "buyer_mobile": {"type": ["string", "null"]},
            "supply_type": {"type": ["string", "null"]},
        },
    }


def _invoice_footer_schema():
    totals_schema = deepcopy(INVOICE_DATA_SCHEMA["properties"]["totals"])
    totals_schema["type"] = ["object", "null"]
    totals_schema["required"] = []
    totals_schema["properties"]["transport"] = INVOICE_DATA_SCHEMA["properties"]["transport"]
    return totals_schema


def _page_audit_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "count_verified": {"type": "boolean"},
            "serial_match": {"type": "boolean"},
            "expected_count": {"type": ["integer", "null"]},
            "extracted_count": {"type": "integer"},
            "serial_numbers_extracted": {"type": "array", "items": {"type": "integer"}},
            "page_line_total": {"type": "number"},
        },
        "required": [
            "count_verified",
            "serial_match",
            "expected_count",
            "extracted_count",
            "serial_numbers_extracted",
            "page_line_total",
        ],
    }


def get_invoice_data_schema(expected_line_item_count=None, medical_invoice=False, page_mode=False):
    schema = deepcopy(INVOICE_DATA_SCHEMA)
    line_item_schema = schema["properties"]["line_items"]["items"]

    if medical_invoice:
        line_item_schema["properties"].update(
            {
                "expiry_date": {
                    "type": ["string", "null"],
                    "description": "Medicine expiry date exactly as printed, e.g. MM/YY, MM/YYYY, or YYYY-MM-DD.",
                },
                "batch": {
                    "type": ["string", "null"],
                    "description": "Medicine batch number exactly as printed.",
                },
                "manufacturer": {
                    "type": ["string", "null"],
                    "description": "Medicine manufacturer name exactly as printed.",
                },
                "packing_type": {
                    "type": ["string", "null"],
                    "description": "Packing type/pack size exactly as printed, often the number of units in one pack.",
                },
                "scheme%": {
                    "type": ["string", "number", "null"],
                    "description": "Medicine scheme/bonus percentage exactly as printed only from a separate Scheme/Sch/Bonus column; otherwise null. Never copy discount percentage here.",
                },
                "free_qty": {
                    "type": ["string", "number", "null"],
                    "description": "Free/bonus quantity exactly as printed only from a separate Free/Bonus quantity column; otherwise null. Never copy discount percentage here.",
                },
                "mrp": {
                    "type": ["string", "number", "null"],
                    "description": "Maximum retail price of the item as printed."
                }
            }
        )
        line_item_schema["required"] = [
            *line_item_schema["required"],
            "expiry_date",
            "batch",
            "scheme%",
            "free_qty",
            "manufacturer",
            "packing_type",
            "mrp"
        ]

    if page_mode:
        schema["description"] = "Schema for one parsed invoice page. The backend will merge page JSON objects."
        schema["required"] = [
            "page_number",
            "invoice_header",
            "invoice_footer",
            "line_items",
            "other_charges",
            "page_audit",
        ]
        schema["properties"]["invoice_header"] = _invoice_header_schema()
        schema["properties"]["invoice_footer"] = _invoice_footer_schema()
        schema["properties"]["page_audit"] = _page_audit_schema()
        schema["properties"]["line_items"]["minItems"] = 0
        schema["properties"]["other_charges"]["default"] = []
        return schema

    if not expected_line_item_count:
        return schema

    schema["required"] = [
        *schema["required"],
        "expected_line_item_count",
        "extracted_line_item_count",
    ]
    schema["properties"]["expected_line_item_count"] = {
        "type": "integer",
        "const": expected_line_item_count,
        "description": "User-provided expected number of printed invoice item rows.",
    }
    schema["properties"]["extracted_line_item_count"] = {
        "type": "integer",
        "const": expected_line_item_count,
        "description": "Number of entries returned in line_items. Must equal expected_line_item_count.",
    }
    return schema


def get_invoice_system_prompt(expected_line_item_count=None, medical_invoice=False, page_mode=False):
    extra_instructions = []

    if page_mode:
        extra_instructions.append(
            """
### Page JSON shape
Return one page JSON object for the current PAGE_META only.
- `invoice_header`: object only on the first invoice page, otherwise null.
- `invoice_footer`: object only on the page where PAGE_META.has_grand_total is true, otherwise null.
- `line_items`: must contain exactly PAGE_META.item_count_this_page rows when has_item_table is true.
- `page_audit.extracted_count` must equal len(line_items).
- Do not return a full merged invoice here. The backend will merge page JSON objects.
"""
        )

    if medical_invoice:
        extra_instructions.append(
            """
### Medical invoice line item fields
The user has marked this as a medical/pharma invoice.
- For every `line_items` entry, also extract the following fields:
  - `expiry_date`: Medicine expiry exactly as printed. Look under columns labeled "EXP", "EXPIRY", or similar variants.
  - `batch`: Batch/lot number exactly as printed.
  - `scheme%`: Scheme/bonus percentage exactly as printed only from a separate Scheme/Sch/Bonus column; otherwise null. Never copy discount percentage here.
  - `free_qty`: Free/bonus quantity exactly as printed only from a separate Free/Bonus quantity column; otherwise null. Never copy discount percentage here.
  - `mrp`: Maximum retail price exactly as printed, if present.
  - `manufacturer`: Medicine manufacturer exactly as printed. Look under columns labeled "MFG", "MANUFACTURER", or similar variants.
  - `packing_type`: Pack size or type exactly as printed (often the count of units per pack). Look under columns labeled "PACK", "PACKING", or similar variants.
- Set any genuinely absent field to `null`. Do not guess or infer missing values.
- Do not normalize, convert, or reformat values — trim leading/trailing whitespace only.
"""
        )

    if expected_line_item_count:
        extra_instructions.append(
            f"""
### Explicit line item count validation
The user has provided expected_line_item_count = {expected_line_item_count}.

Invoices often contain repeated products, similar descriptions, or visually dense rows that are easy to merge or skip — every printed row is a distinct billable entry and must be preserved independently.

- Extract every line item from the complete input, reading row by row without skipping.
- Count the extracted line items after the first pass.
- If the count does not match {expected_line_item_count}, the extraction is incomplete or incorrect — re-read the input carefully, looking specifically for:
  - Rows with repeated product names that may have been collapsed.
  - Rows near page breaks, headers, or subtotals that may have been skipped.
  - Closely packed or low-contrast rows that may have been visually merged.
- Do not return until the count is exactly {expected_line_item_count}.
- Return exactly {expected_line_item_count} entries in `line_items`.
- Set `expected_line_item_count` to {expected_line_item_count}.
- Set `extracted_line_item_count` to the actual number of rows extracted (must equal {expected_line_item_count}).
- Do not merge rows, summarize rows, omit repeated products, or alter any printed value.
"""
        )

    if not extra_instructions:
        return INVOICE_SYSTEM_PROMPT

    return INVOICE_SYSTEM_PROMPT.rstrip() + "\n".join(extra_instructions)


BANK_STATEMENT_SYSTEM_PROMPT = """
# Bank Statement Transaction Extraction — System Prompt
You are a precise bank-statement transaction extraction system. You receive an
Indian bank statement (any bank — Indian Bank, ICICI, HDFC, SBI, Axis, etc.)
converted to text/CSV/table form. Column names, ordering, and narration styles
vary by bank, but the underlying data is the same. Extract every transaction row
exactly once and return JSON matching the schema at the end. Do not summarize,
skip, merge, or deduplicate rows.
---
## STEP 1 — Find the header row and map columns by MEANING
Statements have preamble (bank name, account holder, address, filters) before the
table. Find the row whose cells are column titles, then map each column to a role
using these aliases (case-insensitive, match on substring):
| Role        | Header aliases you may see                                                        |
|-------------|-----------------------------------------------------------------------------------|
| `value_date`| "Value Date", "Val Date"                                                          |
| `txn_date`  | "Transaction Date", "Post Date", "Posted Date", "Transaction Posted Date", "Date" |
| `ref_col`   | "Cheque. No./Ref. No.", "Cheque No", "Ref No", "Chq No"                           |
| `description`| "Transaction Remarks", "Description", "Narration", "Particulars", "Details"     |
| **debit**   | "Withdrawal Amt", "Withdrawal", "Debit Amount", "Debit", "Dr", "Paid Out"         |
| **credit**  | "Deposit Amt", "Deposit", "Credit Amount", "Credit", "Cr", "Paid In"             |
| `balance`   | "Balance", "Balance (INR)", "Running Balance", "Closing Balance"                  |
The two amount columns are the most important. Identify which column is the
**money-out (debit/withdrawal)** column and which is the **money-in (credit/deposit)**
column. Everything else hangs off that.
---
## STEP 2 — Direction (the rule that most extractors get wrong)
**Direction is decided ONLY by which amount column is populated.**
- Value in the **debit/withdrawal** column → `direction = "debit"` (money out).
- Value in the **credit/deposit** column → `direction = "credit"` (money in).
- Exactly one of the two is filled on a real transaction row.
Do NOT decide direction from any of these — they are traps:
- **The balance's `CR`/`DR` suffix** (e.g. `765953.63CR`). Some banks tag every
  balance `CR` because the account is in credit; it says nothing about the row.
  Many banks (e.g. ICICI) show no suffix at all.
- **Words in the narration.** A debit row can contain "CREDIT" (e.g.
  `UPI MDR CHARGES`, a `BY UPI CREDIT` reversal). A credit row can be an inward
  `RTGS`. Ignore the wording; trust the column.
If neither amount column is populated, the row is not a transaction — exclude it.
---
## STEP 3 — Exclude non-transaction rows
Never emit:
- The preamble / bank name / account-holder / address / filter block.
- Opening balance rows: `BALANCE B/F`, `B/F`, `Opening Balance`, `Brought Forward`.
- Closing/carried-forward rows: `C/F`, `Closing Balance`, `Carried Forward`.
- **Totals / subtotal rows**: `Page Total`, `Total`, `Grand Total`, or any row with
  comma-grouped sums in the amount columns but **no dates**.
- **Legend / glossary / footnote blocks**: numbered abbreviation explanations
  (`1. UPI - …`, `28. BIL - …`, `30. CMS - …`), a "Legend"/"Abbreviations" heading,
  disclaimers, or any row that has text only in the first column and is empty in
  BOTH amount columns and the balance column.
- Fully blank rows.
> **Rule of thumb:** a real transaction row has at least one populated amount column
> AND a running balance. If it doesn't, it's a header, total, or legend row.
---
## STEP 4 — Normalize amounts
- Strip thousands separators and symbols: `4,50,000.00` → `450000.00`, `₹1,550.00` → `1550.00`.
  (Indian grouping is irregular — `4,50,000` = 450000.)
- `amount` is the positive value from the populated debit/credit column.
- `balance`: numeric, with any `CR`/`DR` suffix removed (`765953.63CR` → `765953.63`).
---
## STEP 5 — Parse the narration per payment rail
Identify the rail from the start of the description, then extract fields. Narrations
may be slash- (`/`) or dash- (`-`) delimited and may contain padding spaces —
collapse runs of spaces and trim each token.
### `mode` keyword
- `UPI` anywhere → `"UPI"`
- `RTGS` → `"RTGS"` · `NEFT` → `"NEFT"` · `IMPS` (incl. `MMT/IMPS`) → `"IMPS"`
- `INFT` / internal fund transfer / `TRANSFER` (no rail marker) → `"TRANSFER"`
- `CASH DEP` / `CASH DEPOSIT` / `CDM` / `ATM` cash → `"CASH"`; `ATM` withdrawal → `"ATM"`
- `CHQ`, `INWARD CHQ`, `CHQ TRANSFE`, cheque clearing → `"CHEQUE"`
- `MDR`, `CHARGES`, `FEE`, `GST`, `TAX`, `DTAX`, statutory (`GIB`) → `"BANK CHARGES"`
  (use `"TRANSFER"` instead if it is a genuine payment, not a fee)
- `INT` / `INTEREST` → `"INTEREST"` · card POS → `"CARD"` · `ECS` / `NACH` → as named
- If both a generic `TRANSFER` word and a specific rail appear, prefer the specific rail
  (UPI / NEFT / RTGS / IMPS).
---
### `reference` — one most-specific reference number
Priority: **valid `Chq./Ref.No.` → EMI/DPI mandate from narration → null.**
- Use `Chq./Ref.No.` as-is when present and not all zeros / placeholders (`************`).
  It may be a UTR, UPI/IMPS numeric ref, cheque no., or other bank ref.
- If `Chq./Ref.No.` is null/all zeros, parse EMI/DPI narration/description for a mandate reference:
  `EMI|DPI {policy_no} CHQ {mandate_no} {batch_ref}` → use the `S`-prefixed
  `{mandate_no}`, e.g. `EMI 89586928 CHQ S895869280281 052689586928` →
  `S895869280281`.
- Do NOT use bank internal `tran_id`, all-zero strings, EMI/DPI policy number, or
  `0526...` batch ref as `reference`.
---
### `party_name` — human-readable counterparty
> ⚠️ **Two hard overrides — apply before anything else:**
> - **If `mode` is `"BANK CHARGES"` → always set `party_name = "Bank Charges"`**, regardless of narration.
> - **If `mode` is `"CASH"` → always set `party_name = "Cash"`**, regardless of narration (overrides the `"SELF"` rule below).
- Usually the trailing name token, e.g. `Minakshi Minakshi`, `SANJEEV KUMAR`,
  `BHAGWATITRANSPORT CO`, `ULTRA TECH CEMENT LTD`, `JAI HANUMA`, `SANTOSH`.
- `CASH DEPOSIT ... by SELF ...` → `"SELF"` *(superseded by the CASH mode rule above — will always be `"Cash"`)*.
- Inward cheque `... ClgInwPr: ACCURIZE HEALTH,ChqNo:...` → `ACCURIZE HEALTH`.
- Never put a VPA, mobile number, account number, IFSC, vehicle number, or reference here.
- Collapse repeated spaces. `null` if no human-readable name is present.
---
### `party_identifier` — machine-readable handle (not the name)
- **UPI VPA** if present, e.g. `8750846032@ibl`, `gahlawatekta4@oksbi`. VPAs may be
  truncated by the bank (`bachhu.singh4@i`) — capture as-is.
- Else the counterparty **account number** if the narration carries one.
- Else `null`. Do not duplicate `party_name`. Do not put the UPI RRN hash here.
---
### `ifsc` — full 11-character IFSC if present
- e.g. `SBIN0002499`, `HDFC0001968`, `UTIB0000084`, `PUNB0HGB001`.
- A short 4-letter bank code alone (`SBIN`, `PUNB`, `FINO`) is NOT an IFSC → `null`.
---
### Dates
- `value_date` and `txn_date` copied as written (e.g. `01/06/2026`, `01/May/2026`,
  `01/05/2026 07:51:08 AM`). Keep both if the statement has both.
---
## Worked Examples
### A — UPI credit (balance CR suffix ignored)
```
BY UPI CREDIT UPI/730090036071/UPI Payment XXXXX00944/9306200944@axl SBIN0002499/Minakshi  Minakshi
Credit Amount = 300.00 | Balance = 959419.59CR
```
```json
{ "mode":"UPI","direction":"credit","amount":300.00,"reference":"730090036071",
  "party_name":"Minakshi Minakshi","party_identifier":"9306200944@axl",
  "ifsc":"SBIN0002499","balance":959419.59 }
```
### B — RTGS outward (slash form)
```
Withdrawal Amt = 4,50,000.00 | Remarks = RTGS/ICICR42026050100502895/HDFC0001968/BHAGWATITRANSPORT CO
```
```json
{ "mode":"RTGS","direction":"debit","amount":450000.00,
  "reference":"ICICR42026050100502895","party_name":"BHAGWATITRANSPORT CO",
  "party_identifier":null,"ifsc":"HDFC0001968" }
```
### C — RTGS inward (dash form)
```
Deposit Amt = 4,12,037.16 | Remarks = RTGS-UTIBR72026050100131060-ULTRA TECH CEMENT LTD-084010200013129-UTIB0000084
```
```json
{ "mode":"RTGS","direction":"credit","amount":412037.16,
  "reference":"UTIBR72026050100131060","party_name":"ULTRA TECH CEMENT LTD",
  "party_identifier":"084010200013129","ifsc":"UTIB0000084" }
```
### D — UPI debit, truncated VPA
```
Withdrawal Amt = 4,200.00 | Remarks = UPI/109722460725/HR55AT7757/bachhu.singh4@i//ICI669ab0024.../
```
```json
{ "mode":"UPI","direction":"debit","amount":4200.00,"reference":"109722460725",
  "party_name":null,"party_identifier":"bachhu.singh4@i","ifsc":null }
```
### E — NEFT outward
```
Withdrawal Amt = 1,25,000.00 | Remarks = INF/NEFT/IN42612156878597/HDFC0003519/HR63E3740/SHRIBANKEHR63E3
```
```json
{ "mode":"NEFT","direction":"debit","amount":125000.00,
  "reference":"IN42612156878597","party_name":"SHRIBANKEHR63E3",
  "party_identifier":null,"ifsc":"HDFC0003519" }
```
### F — IMPS inward
```
Deposit Amt = 1,00,000.00 | Remarks = MMT/IMPS/612557523735/ULTRA/JAI HANUMA/HDFC Bank
```
```json
{ "mode":"IMPS","direction":"credit","amount":100000.00,"reference":"612557523735",
  "party_name":"JAI HANUMA","party_identifier":null,"ifsc":null }
```
### G — Statutory / tax payment → BANK CHARGES
```
Withdrawal Amt = 18,217.00 | Remarks = GIB/002064785915/DTAX/26050701119465ICIC
```
```json
{ "mode":"BANK CHARGES","direction":"debit","amount":18217.00,
  "reference":"002064785915","party_name":"Bank Charges",
  "party_identifier":"Bank Charges","ifsc":null }
```
### H — Fee row → BANK CHARGES
```
UPI MDR CHARGES | Debit Amount = 3.54
```
```json
{ "mode":"BANK CHARGES","direction":"debit","amount":3.54,"reference":null,
  "party_name":"Bank Charges","party_identifier":null,"ifsc":null }
```
### I — Cash deposit → CASH
```
CASH DEPOSIT Deposit by SELF CASH DEP/HISAR GREEN SQUARE MKT | Credit Amount = 150000.00
```
```json
{ "mode":"CASH","direction":"credit","amount":150000.00,"reference":null,
  "party_name":"Cash","party_identifier":"Cash","ifsc":null }
```
### J — Inward cheque clearing
```
INWARD CHQ  00918178 INW_CLG :ClgInwPr: ACCURIZE HEALTH,ChqNo:918178, | Debit Amount = 99000.00
```
```json
{ "mode":"CHEQUE","direction":"debit","amount":99000.00,"reference":"918178",
  "party_name":"ACCURIZE HEALTH","party_identifier":"00918178","ifsc":null }
```
---
## Final Checks Before Returning
- One object per real transaction row, in statement order.
- Dropped: preamble, `BALANCE B/F` / opening balance, totals / `Page Total`, numbered legend/abbreviation footer.
- Every `direction` derived from which amount column is filled — never the balance `CR`/`DR` suffix and never the narration wording.
- All amounts comma-free positive numbers; Indian grouping expanded correctly.
- `party_name` is **always `"Bank Charges"`** when `mode` is `"BANK CHARGES"`, and **always `"Cash"`** when `mode` is `"CASH"`.
- Return ONLY the JSON object.
"""


BANK_STATEMENT_DATA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "bank": {
            "type": ["string", "null"],
        },
        "account_number": {
            "type": ["string", "null"],
        },
        "statement_period": {
            "type": ["string", "null"],
        },
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value_date": {
                        "type": ["string", "null"],
                    },
                    "txn_date": {
                        "type": ["string", "null"],
                    },
                    "description": {
                        "type": "string",
                    },
                    "mode": {
                        "type": ["string", "null"],
                        "enum": [
                            "UPI",
                            "IMPS",
                            "NEFT",
                            "RTGS",
                            "CASH",
                            "CHEQUE",
                            "ATM",
                            "CARD",
                            "ECS",
                            "NACH",
                            "INTEREST",
                            "BANK CHARGES",
                            "TRANSFER",
                            None,
                        ],
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["credit", "debit"],
                    },
                    "amount": {
                        "type": "number",
                    },
                    "reference": {
                        "type": ["string", "null"],
                        "description": "Use valid Chq./Ref.No. as-is; if null/all-zero, extract EMI/DPI S-prefixed mandate from narration. Never use tran_id, all-zero placeholders, policy no., or 0526 batch ref.",
                    },
                    "party_name": {
                        "type": ["string", "null"],
                    },
                    "party_identifier": {
                        "type": ["string", "null"],
                    },
                    "ifsc": {
                        "type": ["string", "null"],
                    },
                    "balance": {
                        "type": ["number", "null"],
                    },
                },
                "required": [
                    "value_date",
                    "txn_date",
                    "description",
                    "mode",
                    "direction",
                    "amount",
                    "reference",
                    "party_name",
                    "party_identifier",
                    "ifsc",
                    "balance",
                ],
            },
        },
    },
    "required": [
        "bank",
        "account_number",
        "statement_period",
        "transactions",
    ],
}


DATA_SCHEMA = INVOICE_DATA_SCHEMA
SYSTEM_PROMPT = INVOICE_SYSTEM_PROMPT


LLAMA_PROMPT_TEMPLATE = """
You are a document parser for Indian GST invoices. Your job is to convert one invoice page into clean markdown AND emit structured metadata about that page.

## YOUR OUTPUT FORMAT
You must output TWO sections, separated by exactly this delimiter on its own line:
---PAGE_META---

### SECTION 1: Markdown Content
Convert the page to clean markdown. Preserve all table rows exactly as printed. Do not merge, skip, or summarize any row.

### SECTION 2: Page Metadata (after the delimiter)
Output a JSON object with exactly these fields:

{
  \"page_number\": <integer, the page number in the document>,
  \"page_type\": \"<one of: tax_invoice | eway_bill | lr_consignment | other>\",
  \"has_item_table\": <true|false — true if this page contains a line item table>,
  \"bf_amount\": <number or null — the 'B/F' carry-forward amount printed at top of table, null if absent>,
  \"item_serial_numbers\": [<list of all S.No integers found on this page's item table, in order>],
  \"item_count_this_page\": <integer — count of data rows on THIS page only, excludes B/F row, headers, subtotals, grand total>,
  \"first_sno_this_page\": <integer or null — the S.No of the first item row on this page>,
  \"last_sno_this_page\": <integer or null — the S.No of the last item row on this page>,
  \"has_grand_total\": <true|false — true if this page contains the final TOTAL ITEMS / Grand Total footer>,
  \"printed_total_items\": <integer or null — the number printed next to 'TOTAL ITEMS :' if present on this page, else null>,
  \"page_subtotal_amount\": <number or null — the subtotal or B/C amount printed at the bottom of this page's item table, null if absent>
}

## COUNTING RULES — follow exactly
- Count ONLY rows that have: a serial number (S.No) OR a product description AND an amount in the last column.
- Do NOT count: the B/F row, repeated column header rows, subtotal rows, grand total rows, blank rows.
- If a product description spans two printed lines but has only one S.No and one amount → count it as ONE row.
- If two rows share the same product name but have different S.No values → count them as TWO separate rows.
- List every S.No you see in `item_serial_numbers` — this is your own verification that your count is correct.
  len(item_serial_numbers) MUST equal item_count_this_page.

## EXAMPLE OUTPUT STRUCTURE

[markdown table and content here]

---PAGE_META---
{
  \"page_number\": 2,
  \"page_type\": \"tax_invoice\",
  \"has_item_table\": true,
  \"bf_amount\": 57496.98,
  \"item_serial_numbers\": [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47],
  \"item_count_this_page\": 23,
  \"first_sno_this_page\": 25,
  \"last_sno_this_page\": 47,
  \"has_grand_total\": false,
  \"printed_total_items\": null,
  \"page_subtotal_amount\": 100738.02
}
"""
