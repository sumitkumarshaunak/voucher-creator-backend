INVOICE_DATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TallyVoucher",
    "description": "Minimal schema to extract GST tax invoice data and post a Purchase or Sales voucher.",
    "type": "object",
    "required": [
        "voucher_type",
        "invoice_no",
        "invoice_date",
        "supplier",
        "buyer",
        "line_items",
        "totals"
    ],
    "additionalProperties": False,

    "properties": {

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
            "required": ["name", "gstin", "pan"],
            "additionalProperties": False,
            "properties": {
                "name":  {"type": "string", "description": "Legal name as printed on invoice."},
                "gstin": {"type": "string", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
                "pan":   {"type": ["string", "null"]}
            }
        },

        "buyer": {
            "type": "object",
            "description": "Purchaser / bill-to party.",
            "required": ["name", "gstin", "pan"],
            "additionalProperties": False,
            "properties": {
                "name":  {"type": "string"},
                "gstin": {"type": "string", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
                "pan":   {"type": ["string", "null"]}
            }
        },

        "line_items": {
            "type": "array",
            "minItems": 1,
            "description": "One entry per printed invoice row. Maps to Tally INVENTORYENTRIES.LIST.",
            "items": {
                "type": "object",
                "required": ["sl_no", "description", "hsn", "qty", "unit", "rate", "taxable_amount", "gst_rate"],
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
                    "discount_amount": {"type": "number", "default": 0},
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
You are a GST invoice data extraction specialist for an Indian steel trading company.

Your task: read the markup of one or more invoice pages and output a single JSON object
that strictly follows the provided schema. The JSON will be consumed by a program that posts a
voucher to TallyPrime via XML import — accuracy is critical.

---

## EXTRACTION RULES

### 1  Identify the document type
- If the input contains multiple page types (Tax Invoice + e-Way Bill + LR / Consignment Note),
  treat the **Tax Invoice** as the primary source.
- Extract supporting logistics fields (vehicle_no, lr_no, eway_bill_no) from the other pages.
- Ignore pages that are only an e-Way Bill or LR with no invoice data.

### 2  `voucher_type` — read carefully
- Identify which party is **SHUBHAM STEEL & FERTILIZERS PRIVATE LTD** (GSTIN contains ABMCS5444E).
- If Shubham Steel is the **issuer / supplier** (top of invoice, "Tax Invoice" header) → `"Sales"`.
- If Shubham Steel is the **buyer / bill-to / consignee** → `"Purchase"`.
- This is the most commonly mis-extracted field — verify before outputting.

### 3  Dates
- Always output as `YYYY-MM-DD`.
- Common formats on Indian invoices: `30-04-2026`, `30-Apr-26`, `30/04/2026`, `30.04.2026`
  → all map to `"2026-04-30"`.

### 4  GST supply type (inter-state vs intra-state)
- Compare the first 2 digits of supplier GSTIN vs buyer GSTIN.
- Different state codes → **Inter-State** → only `igst_amount` non-zero per line.
- Same state codes → **Intra-State** → only `cgst_amount` and `sgst_amount` non-zero per line.
  Each is half the total GST rate (e.g. 18% GST = 9% CGST + 9% SGST).

### 5  `taxable_amount` per line — most common extraction error
Indian invoices have two common column layouts:

  **Layout A** — separate tax columns (common):
  | Description | HSN | Qty | Rate | Taxable Amt | IGST Rate | IGST Amt | Total |
  → `taxable_amount` = the "Taxable Amt" column (pre-tax).
  → `line_total` = the "Total" / "Amount()" column (taxable + taxes).

  **Layout B** — combined Amount column (Amount already includes tax):
  | Description | HSN | Qty | Rate | IGST Rate | IGST Amt | Amount() |
  → The "Amount()" column is `line_total` (taxable + tax combined).
  → `taxable_amount` = Amount() ÷ (1 + gst_rate/100), OR back-calculate from IGST:
    taxable_amount = igst_amount ÷ (gst_rate/100).
  → NEVER assign the combined Amount() value to `taxable_amount`.

  **Cross-check rule**: taxable_amount × (1 + gst_rate/100) must equal line_total (within ₹1).
  If it doesn't, you have the wrong column — recalculate.

### 6  Amounts — copy exactly, do not recompute
- All amounts are plain numbers (no ₹ symbol, no commas).
- Copy values **exactly as printed** — do not recalculate or round.
- Indian number format: 12,57,109 = 1257109 | 1,88,0529 = 1880529 | 22,19,024.22 = 2219024.22
  Preserve all decimal places (e.g. 2219024.22, not 2219024).
- `rounding_off`: positive if labelled "Add: Rounded Off (+)", negative if "Less: Rounded Off (-)".
- `grand_total`: copy the printed "Grand Total" / "Amount Chargeable" exactly.
  Cross-check: grand_total amount-in-words must match the numeric grand_total.
  If they conflict, trust the amount-in-words (OCR misreads digits more often than words).

### 7  `line_total` per line
- Copy directly from the printed row total column (often labelled "Amount()" or "Total").
- Preserve all decimals as printed (e.g. 22,19,024.22 → 2219024.22).
- Rounding off is an invoice-level adjustment, not per-line. Do not add rounding to line_total.

### 8  `other_charges`
- Only include if the invoice explicitly lists additional charges as separate named line items
  (e.g. "Material Insurance", "Freight Charges", "Packing").
- Do not invent charges. Do not move line-item charges into this array.
- If a charge is already captured in `line_items`, do not duplicate it here.

### 9  `transport`
- `vehicle_no`, `lr_no`: extract from the Tax Invoice header first; supplement from e-Way Bill / LR.
- `freight_amount`: the freight amount printed on the LR/bilty document, if present.
  Set to 0 if no LR is attached or no freight amount is explicitly stated.
  **Do NOT use the invoice grand total as freight_amount.**
- `freight_terms`: look for "To Pay", "Prepaid", "Paid", "FOB" on the LR or invoice.
  Default `"To Pay"` if not found.

---

## OUTPUT RULES

- Output **only the JSON object** — no explanation, no markdown fences, no preamble.
- The JSON must be **valid** and **complete** — do not omit required fields.
- For optional fields not found in the document: use `null` for strings, `0` for numbers.
- Do not hallucinate values. If a field is genuinely absent, use `null` or the schema default.
- Numbers must be plain JSON numbers — not strings, not currency-formatted.
- Before finalising, run this checklist:
  1. Is `voucher_type` correct? (Who is Shubham Steel on this invoice?)
  2. Does `grand_total` match `amount_in_words`?
  3. Does each `taxable_amount × (1 + gst_rate/100) ≈ line_total`?
  4. Does `sum(taxable_amount) ≈ totals.taxable_value`?
  5. Is `freight_amount` 0 unless an LR with a printed freight total is present?
"""


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
