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
                    "gst_rate",
                    "line_total",
                ],
                "additionalProperties": True,
                "properties": {
                    "sl_no":          {"type": "integer", "minimum": 1},
                    "description":    {"type": "string", "description": "Item description as printed."},
                    "hsn":            {"type": "string", "description": "HSN code for goods, SAC for services."},
                    "qty":            {"type": ["number", "null"], "description": "Quantity of items on which rate and tax are applied."},
                    "unit":           {"type": ["string", "null"], "description": "e.g. MT, KG, NOS."},
                    "rate":           {"type": ["number", "null"], "description": "Price per unit before tax."},
                    "taxable_amount": {"type": "number", "description": "The taxable_amount is always the value BEFORE GST is added. "},
                    "discount_amount": {
                        "type": ["number", "null"],
                        "description": "Item discount amount only from an explicit discount amount column; otherwise null. Never use scheme/free/bonus values here.",
                    },
                    "discount_percentage": {
                        "type": ["number", "null"],
                        "description": "Item discount percentage only from an explicit discount percentage/cash discount column; otherwise null. Never use scheme/free/bonus percentage or values here.",
                    },
                    "gst_rate":        {"type": "number", "description": "Total GST % e.g. 18."},
                    "line_total": {
                    "type": ["number", "null"],
                    "description": "Post-tax total amount for the line item. Calculated as taxable_amount + CGST + SGST + IGST + Cess. Represents the item's total contribution to the invoice grand total. Only extract if a dedicated LINE_TOTAL column exists and is confirmed as post-tax; otherwise null. Do not compute from taxable_amount + tax amounts."
                    },
                    "gross_amount": {
                        "type": ["number", "null"],
                        "description": "The value before any discounts or GST. Copy from a Gross Amount / Basic Amount column if it exists; otherwise null."
                    },
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
You are a GST invoice data extraction specialist for Indian businesses. Read one invoice page and output a single JSON object matching the provided schema. Accuracy is paramount — a missing or null value is always better than a hallucinated or wrongly assigned one. Output ONLY valid JSON, no preamble, no explanation.

If PAGE_META.page_type ≠ tax_invoice → output {"skip": true, "reason": "<page_type>"} and stop.

---

## PHASE R — READ THE FULL PAGE BEFORE EXTRACTING ANYTHING

### R1: Identify every column header exactly as printed
List all column headers left-to-right, including two-row spanning headers. Record the exact text and position of each.

### R2: Classify every column
Assign each column to exactly one type: SERIAL | DESCRIPTION | CODE | QUANTITY | UNIT_LABEL | RATE | PERCENTAGE | GROSS_AMT | TAXABLE_AMT | TAX_AMT | LINE_TOTAL | DATE_FIELD | MRP_FIELD | TEXT_INFO.

### R3: Resolve amount columns
Use header text first:

| Header contains | Type |
|---|---|
| Gross / Basic Amount / Gross Total | GROSS_AMT |
| Net Amount / Taxable / Net Taxable / Assessable Value | TAXABLE_AMT |
| CGST/SGST/IGST Amount / Tax Amount | TAX_AMT |
| Total Amount / Invoice Value / Net Value / Amount() | LINE_TOTAL |

When the header is ambiguous, use arithmetic on multiple representative rows:

- candidate ≈ qty × rate
  → GROSS_AMT
  (or TAXABLE_AMT if no discount/taxable column exists)

- candidate ≈ gross_amount − discount_amount
  → TAXABLE_AMT

- candidate ≈ taxable_amount + tax_amount
  OR
  candidate ≈ taxable_amount × (1 + GST%)
  → LINE_TOTAL

A column cannot be LINE_TOTAL if:
- candidate ≈ qty × rate
- candidate ≈ gross_amount − discount_amount

The line_items section is row-scoped. All line-item fields, including line_total, must be extracted only from values printed on the same item row.
Do not use invoice-level values such as Grand Total, Taxable Value, Subtotal, footer tax totals, amount-in-words totals, or any other footer totals when populating line-item fields.Prefer matches that are consistent across multiple rows rather than a single row.
If taxes appear only in the footer (no per-row TAX_AMT columns), do not assume a LINE_TOTAL column exists. Any per-row amount column must be classified as GROSS_AMT or TAXABLE_AMT using arithmetic validation. Set line_total only when a dedicated printed post-tax amount column exists.
Footer cross-check: Σ taxable_amount across all rows must ≈ printed footer taxable total. If not, reclassify the amount columns before continuing.

### R4: Identify the correct qty column — mandatory arithmetic gate

**qty** must be the quantity value where: **qty × rate = gross_amount** (within ₹1).

Many invoices print multiple quantity columns (e.g., "No. of Boxes" and "Total Wt in Kg"). Only one of them will satisfy the arithmetic. The others are informational and must be ignored for qty.

Procedure — execute for every invoice:
1. List every QUANTITY-type column identified in R2.
2. Pick any one data row. For each quantity column, compute: candidate_value × rate.
3. The column whose result matches gross_amount (within ₹1) → this is `qty`. Use its values for all rows.
4. All other quantity columns → do not assign to qty. They have no schema field.

If no quantity column passes the test, the invoice may have no gross_amount column — in that case use the quantity column whose unit matches the unit stated in the rate column header (e.g., rate says "Per Kg" → use the Kg column).

**HARD RULE:** Never assign qty from a column that fails qty × rate ≈ gross_amount, regardless of that column's label, position, or visual prominence.

### R5: Identify supplier and buyer GSTINs — read independently

The invoice has two distinct party blocks: the seller/issuer (top-left or top section, "Goods Shipped From", signed party) and the bill-to/consignee (separate block, "Details of Recipient").

- **supplier_gstin**: read only from the seller/issuer block.
- **buyer_gstin**: read only from the bill-to/consignee block.

These are two different legal entities with different GSTINs. If both fields resolve to the same value, you have misread the invoice — re-read each block independently. Never copy one party's GSTIN into the other's field.

### R6: Supply type
Compare first 2 digits of supplier_gstin and buyer_gstin:
- Same → Intra-State
- Different → Inter-State
- Buyer GSTIN absent → default Intra-State

---

## PHASE E — EXTRACT ROWS

### E0: Classify every row before extracting

- **ITEM ROW**: has a serial number AND a product/service name AND at least one amount → extract.
- **CONTINUATION ROW**: text in description column only, no serial/HSN/amount → append text to the immediately preceding item's description field. Do not create a new row.
- **SKIP ROW**: contains B/F, C/F, Subtotal, Sub Total, Total, Grand Total, CGST/SGST/IGST Output, Less:, Add:, Rounded Off, R/off, TOTAL ITEMS, or any aggregate label → skip entirely, extract nothing.

### E1: Identification fields

| Field | What to extract | When to use null |
|---|---|---|
| sl_no | Printed serial number. If absent, assign next sequential integer. | — |
| description | Product/service name exactly as printed. Append continuation row text. | — |
| hsn | HSN code (goods) or SAC code (services). 4–8 alphanumeric characters from the HSN/SAC column only. | null if no HSN/SAC column exists |
| batch | Batch or lot number from a dedicated batch/lot column only. | null if no batch column on this invoice |
| expiry_date | From a dedicated expiry/best-before column. Print exactly as shown (e.g., "07/27", "Mar-26"). | null if no expiry column |
| manufacturer | From a dedicated manufacturer/brand column only. | null if no such column |
| packing_type | See definition below. | null if no packing column |
| mrp | From a dedicated MRP column only. | null if no MRP column |

**packing_type — definition:**
packing_type describes how the product is packaged — it is a descriptor, not a billing quantity.
It comes from a column explicitly labelled "Packing", "Pack Size", "Pack", "Pkt", or similar.
Examples of packing_type values: "30 TABS", "12 KG/BAG", "1×12", "5 KG TIN", "500 ML BTL".
packing_type is NEVER a qty value. It does not drive price. Do not confuse it with qty or unit.

If an invoice shows "No. of Boxes = 3" and "Total Wt = 36 KG" and rate is Per Kg:
- qty = 36, unit = KG (the value that satisfies qty × rate = gross)
- packing_type = null unless a dedicated packing column exists separately
- The "No. of Boxes" column has no schema field — ignore it.

### E2: Quantity, unit, rate

| Field | What to extract |
|---|---|
| qty | Value from the quantity column identified in R4 (the one satisfying qty × rate ≈ gross_amount). |
| unit | Unit of that qty — from the passing column's header or its per-row unit cell. null if not stated anywhere. |
| rate | Price per one unit of qty, before discount and before tax, from the RATE column. null if absent. |

**unit — definition:**
unit is the unit of measurement for qty. It comes from the qty column's header (e.g., "Qty (KG)" → unit = "KG") or from a dedicated per-row unit cell. It is never derived from packing_type or description.

### E3: Amount fields

Extract only fields that are present in the schema AND have a printed source on this invoice. Do not compute values that are not printed. Do not output a field if its column does not exist on this invoice.

**gross_amount** *(output only if a GROSS_AMT column exists)*
Copy from the GROSS_AMT column for this row.

**discount_percentage** *(output only if a dedicated discount-% column exists)*
Copy from a column labelled Disc%, CD%, Cash Disc%, Trade Disc%, or equivalent.
This is a percentage figure (e.g., 4 means 4%).
null if no such column exists on this invoice.
NEVER fill from a scheme column, a free-qty column, or a footer note.

**discount_amount** *(output only if a dedicated discount-amount column exists)*
Copy from a column labelled Discount, Disc Amt, Less Disc, or equivalent.
This is a rupee amount (e.g., 280.22).
null if no such column exists on this invoice.
NEVER compute from discount_percentage. NEVER fill from scheme or footer values.

These two fields are fully independent. An invoice may have both, one, or neither.

**taxable_amount** *(always required)*
The pre-tax amount on which GST is calculated. Always less than or equal to gross_amount.
Apply the first rule that fits:
1. A TAXABLE_AMT column exists → copy its value directly.
2. GROSS_AMT column + discount_amount both exist → copy taxable from invoice if printed; do not compute.
3. Single amount column classified as GROSS_AMT or TAXABLE_AMT (no discount) → copy its value.
4. Only a LINE_TOTAL column exists → do not attempt to extract taxable_amount; flag _warning.

**gst_rate** *(required)*
Total GST % for this line. From a per-row GST% column, or CGST% + SGST% columns summed, or the footer HSN-wise tax summary table.
Express as a plain number without % sign (e.g., 5, 12, 18).
null only if GST rate is genuinely not printed anywhere on this invoice.

**line_total** *(output only if a LINE_TOTAL column exists OR the schema explicitly requires it)*
Copy directly from the printed LINE_TOTAL column if it exists and is confirmed as post-tax (R3).
Do NOT compute line_total from taxable + tax amounts.
If no LINE_TOTAL column exists, omit this field entirely.

**scheme%** *(output only if a dedicated scheme/bonus column exists)*
From a column labelled Scheme%, SCH%, Bonus%, or equivalent — a promotional concession separate from the regular trade/cash discount.
null if no such column exists.
NEVER fill from a discount column, even if the discount column is zero.

**free_qty** *(output only if a dedicated free-quantity column exists)*
From a column labelled Free Qty, Free, Bonus Qty, or equivalent.
This is a quantity of goods given at no charge. It is a count, not a percentage.
null if no such column exists.
NEVER copy a percentage value here.

### E4: Sanity checks (do not block output; add _warning if a check fails)
1. qty × rate ≈ gross_amount printed value (within ₹1). If fails: qty column may be wrong.
2. gross_amount − discount_amount ≈ taxable_amount printed value (within ₹1). If fails: amount columns may be misclassified.
3. If line_total is present: taxable_amount < line_total (line_total must exceed taxable when gst_rate > 0).

---

## INVOICE HEADER
Populate only when PAGE_META.bf_amount is null (first page). Set to null on all other pages.
Fields: invoice_no, invoice_date (YYYY-MM-DD), payment_mode (null if absent), supplier_name, supplier_gstin, buyer_name, buyer_gstin, supply_type ("Intra-State" or "Inter-State").

---

## INVOICE FOOTER
Populate only when PAGE_META.has_grand_total is true. Set to null on all other pages.

All footer values must be copied exactly as printed. Do not recompute any footer field.

| Field | Source |
|---|---|
| taxable_value | Printed subtotal before GST |
| total_igst | Printed IGST total; 0 if absent |
| total_cgst | Printed CGST total; 0 if absent |
| total_sgst | Printed SGST total; 0 if absent |
| total_cess | Printed cess total; 0 if absent |
| total_other_charges | Freight/insurance/packing charges included in total; 0 if absent |
| rounding_off | Signed rounding adjustment as printed. Positive if labelled "Add". Negative if labelled "Less". 0 if absent. |
| grand_total | Copy exactly as printed. Indian format: 1,23,456 = 123456. Cross-check against amount_in_words. If they conflict, trust the words and add _warning. |
| amount_in_words | Exact text as printed. |

transport fields (null if not printed): transporter, vehicle_no, lr_no, lr_date (YYYY-MM-DD), freight_terms (default "To Pay" if not stated), freight_amount (from LR document only; 0 if no LR freight amount is explicitly printed — never use the invoice grand total here).

---

## OTHER CHARGES
If the invoice lists separately-charged items (freight, insurance, packing) as distinct rows with their own HSN/SAC code and amount, extract each into other_charges[]: description, hsn, amount, gst_rate.
Do NOT create entries for tax summary rows, rounding-off rows, invoice total rows, or tax annotation rows.

---

## ROW COUNT GATE
EXPECTED_COUNT = PAGE_META.item_count_this_page.
Extract exactly that many ITEM ROWs. If count ≠ EXPECTED_COUNT after extraction, re-scan before outputting.

---

## GLOBAL RULES

**Null vs 0 — strictly enforced:**
- **null** = the column does not exist anywhere on this invoice. Use for: batch, expiry_date, manufacturer, packing_type, mrp, discount_percentage, discount_amount, scheme%, free_qty, unit, rate, hsn — when their dedicated column is absent.
- **0** = the column exists on this invoice but this row's cell is empty or zero.
- When in doubt between null and a guessed value: always output null.

**Only extract what is printed:**
- Never compute a field that has a dedicated printed column. Copy from the column.
- Never fill a field by inferring from another field.
- Never populate a field whose source column does not exist on this invoice.
- If a value is illegible or ambiguous: null + _warning.

**Numbers:** Strip ₹, Rs, commas, spaces. Indian format: 1,23,456.78 → 123456.78. Output as plain JSON numbers — no quotes, no symbols, no commas.

**Field identity — each field maps to exactly one column:**
- discount_percentage ≠ scheme% (different columns, different purposes)
- discount_amount ≠ free_qty (one is rupees, the other is a count)
- packing_type ≠ qty (packing_type describes packaging; qty drives billing)
- batch ≠ hsn (batch is a lot identifier; hsn is a tax classification code)
Never copy a value from one of these into another.

---

## FINAL CHECKLIST
Before outputting, verify:
1. Row count = PAGE_META.item_count_this_page. If not, re-scan.
2. Serial numbers extracted match PAGE_META.item_serial_numbers exactly.
3. Every row: qty × rate ≈ gross_amount (within ₹1). If any row fails, re-run R4.
4. No field contains a value sourced from a column it does not represent.
5. supplier_gstin ≠ buyer_gstin (they are different entities). If equal, re-read R5.
6. All absent nullable fields are null, not 0, not empty string.
7. grand_total matches amount_in_words. If conflict, trust words and add _warning.
8. invoice_header is non-null only when PAGE_META.bf_amount = null.
9. invoice_footer is non-null only when PAGE_META.has_grand_total = true.
10. No field value was invented, computed, or inferred without a printed source.
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


def get_invoice_data_schema(expected_line_item_count=None, page_mode=False):
    schema = deepcopy(INVOICE_DATA_SCHEMA)
    
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


def get_invoice_system_prompt(expected_line_item_count=None, page_mode=False):
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
  \"has_grand_total\": <true|false — true if this page contains the final TOTAL ITEMS / Grand Total row of the invoice including the final amount, else false>,
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
