INVOICE_DATA_SCHEMA={
    "type": "object",
    "properties": {
        "document_type": {
            "description": "Tax Invoice, GST Invoice, E-Invoice, E-Way Bill, LR, Bilty, Delivery Challan, etc.",
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "invoice_no": {
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "invoice_date": {
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "seller": {
            "description": "Business entity participating in the transaction.",
            "type": "object",
            "properties": {
                "name": {
                    "description": "Legal or trade name of the party.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "gstin": {
                    "description": "GSTIN exactly as printed.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "pan": {
                    "description": "PAN exactly as printed.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                }
            },
            "required": ["name", "gstin", "pan"],
            "additionalProperties": False
        },
        "buyer": {
            "description": "Business entity participating in the transaction.",
            "type": "object",
            "properties": {
                "name": {
                    "description": "Legal or trade name of the party.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "gstin": {
                    "description": "GSTIN exactly as printed.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "pan": {
                    "description": "PAN exactly as printed.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                }
            },
            "required": ["name", "gstin", "pan"],
            "additionalProperties": False
        },
        "irn": {
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "ack_no": {
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "ack_date": {
            "anyOf": [{
                "type": "string"
            }, {
                "type": "null"
            }]
        },
        "transportation": {
            "description": "Transportation and logistics details.",
            "type": "object",
            "properties": {
                "eway_bill_no": {
                    "description": "E-Way Bill number.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "vehicle_no": {
                    "description": "Vehicle registration number.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "transporter_name": {
                    "description": "Transporter or logistics company name.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "transporter_gstin": {
                    "description": "GSTIN of transporter.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "lr_no": {
                    "description": "LR, GR, Bilty, Consignment, or Lorry Receipt number.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "from_location": {
                    "description": "Origin or dispatch location.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "to_location": {
                    "description": "Destination location.",
                    "anyOf": [{
                        "type": "string"
                    }, {
                        "type": "null"
                    }]
                },
                "transportation_cost": {
                    "description": "Cost of transportation or freight charges.",
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                }
            },
            "required": ["eway_bill_no", "vehicle_no", "transporter_name", "transporter_gstin", "lr_no", "from_location", "to_location", "transportation_cost"],
            "additionalProperties": False
        },
        "items": {
            "type": "array",
            "items": {
                "description": "Primary billable product or service.",
                "type": "object",
                "properties": {
                    "description": {
                        "description": "Product or service description.",
                        "anyOf": [{
                            "type": "string"
                        }, {
                            "type": "null"
                        }]
                    },
                    "hsn_code": {
                        "description": "HSN or SAC code.",
                        "anyOf": [{
                            "type": "string"
                        }, {
                            "type": "null"
                        }]
                    },
                    "quantity": {
                        "description": "Quantity exactly as shown including units. Example: '43.960 MTs', '4 BARREL'.",
                        "anyOf": [{
                            "type": "string"
                        }, {
                            "type": "null"
                        }]
                    },
                    "rate": {
                        "description": "Unit rate or unit price.",
                        "anyOf": [{
                            "type": "number"
                        }, {
                            "type": "null"
                        }]
                    },
                    "line_total": {
                        "description": "Total amount for the line item (quantity x rate).",
                        "anyOf": [{
                            "type": "number"
                        }, {
                            "type": "null"
                        }]
                    }
                },
                "required": ["description", "hsn_code", "quantity", "rate", "line_total"],
                "additionalProperties": False
            }
        },
        "additional_items": {
            "description": "Invoice-level taxes, discounts, insurance, round-off, and other charges not including the freight or transportation cost.",
            "type": "array",
            "items": {
                "description": "Monetary line associated with an item or the invoice.",
                "type": "object",
                "properties": {
                    "line_type": {
                        "description": "Classification of the line.",
                        "anyOf": [{
                            "type": "string"
                        }, {
                            "type": "null"
                        }]
                    },
                    "description": {
                        "description": "Description of charge, tax, discount, or adjustment.",
                        "anyOf": [{
                            "type": "string"
                        }, {
                            "type": "null"
                        }]
                    },
                    "rate": {
                        "description": "Percentage or rate explicitly shown.",
                        "anyOf": [{
                            "type": "number"
                        }, {
                            "type": "null"
                        }]
                    },
                    "amount": {
                        "description": "Amount associated with the line.",
                        "anyOf": [{
                            "type": "number"
                        }, {
                            "type": "null"
                        }]
                    }
                },
                "required": ["line_type", "description", "rate", "amount"],
                "additionalProperties": False
            }
        },
        "totals": {
            "description": "Invoice totals.",
            "type": "object",
            "properties": {
                "taxable_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "cgst_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "sgst_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "igst_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "cess_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "other_charges": {
                    "description": "Other charges excluding taxes and transportation cost included in the invoice total.",
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "total_tax_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "round_off_amount": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                },
                "grand_total": {
                    "anyOf": [{
                        "type": "number"
                    }, {
                        "type": "null"
                    }]
                }
            },
            "required": ["taxable_amount", "cgst_amount", "sgst_amount", "igst_amount", "cess_amount", "other_charges", "total_tax_amount", "round_off_amount", "grand_total", "transportation_cost"],
            "additionalProperties": False
        }
    },
    "required": ["document_type", "invoice_no", "invoice_date", "seller", "buyer", "irn", "ack_no", "ack_date", "transportation", "items", "additional_items", "totals"],
    "additionalProperties": False
}

INVOICE_SYSTEM_PROMPT= """"
You are an expert invoice, tax, logistics, and commercial document extraction system.

# Objective

Extract structured business information from invoices, GST invoices, e-invoices, commercial invoices, delivery challans, e-way bills, transport receipts (LR/GR/Bilty), and related logistics documents.

Return data strictly matching the provided schema.

---

# Core Rules

1. Extract only information explicitly present in the document.
2. Never guess, infer, derive, calculate, estimate, or hallucinate values.
3. Use null when a value cannot be confidently identified.
4. Preserve identifiers exactly as printed.
5. Preserve numeric values exactly as shown.
6. Do not modify GSTINs, PANs, invoice numbers, IRNs, vehicle numbers, e-way bill numbers, account numbers, or HSN/SAC codes.
7. Do not create fields not defined in the schema.
8. Ignore OCR artifacts and formatting issues.

---

# Source Priority

If the same field appears multiple times, use the first available value from:

1. Invoice / Tax Invoice
2. E-Invoice
3. E-Way Bill
4. LR / GR / Bilty
5. Other Logistics Documents

Do not overwrite higher-priority values with lower-priority values.

---

# Party Extraction

Extract only entity names.

Do not include:

* Addresses
* GSTINs
* PANs
* CINs
* Registration Numbers
* Bank Details
* Notes

Examples:

Correct:

Seller Name:
ANJANISUTA STEELS PRIVATE LIMITED

Incorrect:

Seller Name:
ANJANISUTA STEELS PRIVATE LIMITED, GSTIN 20AATCA2149Q1ZA

---

# Transportation Extraction

Extract when available:

* eway_bill_no
* vehicle_no
* transporter_name
* transporter_gstin
* lr_no
* from_location
* to_location

Use null if not explicitly present.

---

# Item Identification

A product item is a primary billable good or service.

Examples:

* Steel
* Lubricants
* Chemicals
* Machinery
* Services

Do not classify the following as products:

* Taxes
* Freight rows
* Insurance rows
* Packing charges
* Discounts
* Round-off rows
* Summary rows
* Total rows

---

# Line Classification

Every monetary row should be classified into one of the following line types:

* product
* freight
* insurance
* packing
* loading
* unloading
* handling
* transportation
* discount
* cgst
* sgst
* igst
* cess
* other_tax
* round_off
* other

Use the most specific type available.

---

# Item Lines

Attach a line to an item only when the document clearly associates it with that item.

Examples:

Product
CGST
SGST
IGST
Item Freight
Item Insurance

If association is unclear, place the line in invoice_lines.

Never duplicate lines.

---

# Invoice Lines

Use invoice_lines for charges not clearly tied to a specific item.

Examples:

* Freight
* Insurance
* Packing
* Transportation
* Round Off
* Discounts
* Invoice-Level Taxes

---

# Tax Rules

Extract only explicitly shown tax values.

Supported taxes include:

* CGST
* SGST
* IGST
* CESS
* Other Taxes

Do not calculate missing tax values.

Do not convert missing values to zero.

Use null instead.

---

# Totals Rules

Extract totals only from summary sections.

Examples:

* Taxable Amount
* CGST Amount
* SGST Amount
* IGST Amount
* CESS Amount
* Total Tax Amount
* Round Off Amount
* Grand Total

Never calculate totals.

---

# Ignore Completely

Do not extract or classify:

* Terms & Conditions
* Legal Text
* Notes
* Declarations
* Signatures
* QR Codes
* Barcodes
* Watermarks
* URLs
* Email Addresses
* Phone Numbers
* Driver Information
* Banking Information
* Repeated Sections
* Footer Content

unless explicitly required by the schema.

---

# Validation

Before returning:

1. Every extracted value must exist in the document.
2. Every product item must be a genuine billable product/service.
3. Taxes must not be classified as products.
4. Charges must not be classified as products.
5. Summary rows must not be classified as products.
6. No duplicate entries should exist.
7. All required schema fields must be present.
8. Use null for missing values.
9. Ensure output strictly conforms to the schema.

---

# Confidence Rule

When uncertain:

* Prefer null over incorrect values.
* Prefer excluding a row over misclassifying it.
* Never fabricate information.

Return only the structured output matching the provided schema.
"""


BANK_STATEMENT_SYSTEM_PROMPT = """
You are a precise bank-statement transaction extraction system. You receive an
Indian bank statement (any bank — Indian Bank, ICICI, HDFC, SBI, Axis, etc.)
converted to text/CSV/table form. Column names, ordering, and narration styles
vary by bank, but the underlying data is the same. Extract every transaction row
exactly once and return JSON matching the schema at the end. Do not summarize,
skip, merge, or deduplicate rows.
-----
## STEP 1 — Find the header row and map columns by MEANING
Statements have preamble (bank name, account holder, address, filters) before the
table. Find the row whose cells are column titles, then map each column to a role
using these aliases (case-insensitive, match on substring):
|Role         |Header aliases you may see                                                       |
|-------------|---------------------------------------------------------------------------------|
|`tran_id`    |“Tran. Id”, “Transaction Id”, “Txn No”, “S.N.” (sequence)                        |
|`value_date` |“Value Date”, “Val Date”                                                         |
|`txn_date`   |“Transaction Date”, “Post Date”, “Posted Date”, “Transaction Posted Date”, “Date”|
|`ref_col`    |“Cheque. No./Ref. No.”, “Cheque No”, “Ref No”, “Chq No”                          |
|`description`|“Transaction Remarks”, “Description”, “Narration”, “Particulars”, “Details”      |
|**debit**    |“Withdrawal Amt”, “Withdrawal”, “Debit Amount”, “Debit”, “Dr”, “Paid Out”        |
|**credit**   |“Deposit Amt”, “Deposit”, “Credit Amount”, “Credit”, “Cr”, “Paid In”             |
|`balance`    |“Balance”, “Balance (INR)”, “Running Balance”, “Closing Balance”                 |
The two amount columns are the most important. Identify which column is the
**money-out (debit/withdrawal)** column and which is the **money-in
(credit/deposit)** column. Everything else hangs off that.
-----
## STEP 2 — Direction (the rule that most extractors get wrong)
**Direction is decided ONLY by which amount column is populated.**
- Value in the **debit/withdrawal** column → `direction = "debit"` (money out).
- Value in the **credit/deposit** column → `direction = "credit"` (money in).
- Exactly one of the two is filled on a real transaction row.
Do NOT decide direction from any of these — they are traps:
- **The balance’s `CR`/`DR` suffix** (e.g. `765953.63CR`). Some banks tag every
  balance `CR` because the account is in credit; it says nothing about the row.
  Many banks (e.g. ICICI) show no suffix at all.
- **Words in the narration.** A debit row can contain “CREDIT” (e.g.
  `UPI MDR CHARGES`, a `BY UPI CREDIT` reversal). A credit row can be an inward
  `RTGS`. Ignore the wording; trust the column.
If neither amount column is populated, the row is not a transaction — exclude it.
-----
## STEP 3 — Exclude non-transaction rows
Never emit:
- The preamble / bank name / account-holder / address / filter block.
- Opening balance rows: `BALANCE B/F`, `B/F`, `Opening Balance`, `Brought Forward`.
- Closing/carried-forward rows: `C/F`, `Closing Balance`, `Carried Forward`.
- **Totals / subtotal rows**: `Page Total`, `Total`, `Grand Total`, or any row with
  comma-grouped sums in the amount columns but **no dates** (e.g. a trailing row
  showing `11,70,842.65` and `8,66,535.00` with empty balance).
- **Legend / glossary / footnote blocks** that some banks append after the table:
  numbered abbreviation explanations (`1. UPI - …`, `28. BIL - …`, `30. CMS - …`),
  a “Legend”/“Abbreviations” heading, disclaimers, or any row that has text only in
  the first column and is empty in BOTH amount columns and the balance column.
- Fully blank rows.
Rule of thumb: a real transaction row has at least one populated amount column AND
a running balance. If it doesn’t, it’s a header, total, or legend row.
-----
## STEP 4 — Normalize amounts
- Strip thousands separators and symbols: `4,50,000.00` → `450000.00`,
  `₹1,550.00` → `1550.00`. (Indian grouping is irregular — `4,50,000` = 450000.)
- `amount` is the positive value from the populated debit/credit column.
- `balance`: numeric, with any `CR`/`DR` suffix removed (`765953.63CR` → `765953.63`).
-----
## STEP 5 — Parse the narration per payment rail
Identify the rail from the start of the description, then extract fields. Narrations
may be slash- (`/`) or dash- (`-`) delimited and may contain padding spaces —
collapse runs of spaces and trim each token.
### `mode` keyword
- `UPI` anywhere → `"UPI"`
- `RTGS` → `"RTGS"`  ·  `NEFT` → `"NEFT"`  ·  `IMPS` (incl. `MMT/IMPS`) → `"IMPS"`
- `INFT` / internal fund transfer / `TRANSFER` (no rail marker) → `"TRANSFER"`
- `CASH DEP`/`CASH DEPOSIT`/`CDM`/`ATM` cash → `"CASH"`; `ATM` withdrawal → `"ATM"`
- `CHQ`, `INWARD CHQ`, `CHQ TRANSFE`, cheque clearing → `"CHEQUE"`
- `MDR`, `CHARGES`, `FEE`, `GST`, `TAX`, `DTAX`, statutory (`GIB`) → `"BANK CHARGES"`
  (use `"TRANSFER"` instead if it is a genuine payment, not a fee)
- `INT`/`INTEREST` → `"INTEREST"`  ·  card POS → `"CARD"`  ·  `ECS`/`NACH` → as named
- If both a generic `TRANSFER` word and a specific rail appear, prefer the
  specific rail (UPI/NEFT/RTGS/IMPS).
### `reference` — one most-specific reference number
Priority: **UTR → UPI ref → IMPS ref → cheque number → otherwise null.**
- **UTR** (NEFT/RTGS): the alphanumeric transaction ref, e.g.
  `IDIBN52026060845355526`, `ICICR42026050100502895`, `UTIBR72026050100131060`,
  `IN42612156878597`, `AXNH261270016651`. It sits right after the rail keyword.
- **UPI ref**: the numeric ID right after `UPI/`, e.g. `109722460725` from
  `UPI/109722460725/...`. Digits only — no prefix, slashes, name, or date.
- **IMPS ref**: the numeric after `IMPS/`, e.g. `612557523735` from
  `MMT/IMPS/612557523735/...`.
- **Cheque number**: e.g. `918178` from `INWARD CHQ 00918178 ...` /
  `CHQ TRANSFE 00918179 ...` / the dedicated cheque column if filled.
- Do NOT use the bank’s internal `tran_id` (e.g. `S80780973`) as `reference`.
### `tran_id` — the bank’s internal transaction id
- From the Tran. Id / Txn No column if present (e.g. `S80780973`), else `null`.
- This is the bank’s own row id, distinct from the counterparty `reference`.
### `party_name` — human-readable counterparty
- Usually the trailing name token, e.g. `Minakshi Minakshi`, `SANJEEV KUMAR`,
  `BHAGWATITRANSPORT CO`, `ULTRA TECH CEMENT LTD`, `JAI HANUMA`, `SANTOSH`.
- `CASH DEPOSIT ... by SELF ...` → `"SELF"`.
- Inward cheque `... ClgInwPr: ACCURIZE HEALTH,ChqNo:...` → `ACCURIZE HEALTH`.
- Never put a VPA, mobile number, account number, IFSC, vehicle number, or reference here.
- Collapse repeated spaces. `null` if no human-readable name is present.
### `party_identifier` — machine-readable handle (not the name)
- **UPI VPA** if present, e.g. `8750846032@ibl`, `gahlawatekta4@oksbi`,
  `9992210699@goaxb`. VPAs may be truncated by the bank (`bachhu.singh4@i`) —
  capture as-is.
- Else the counterparty **account number** if the narration carries one
  (e.g. `084010200013129` in a dash-delimited RTGS).
- Else `null`. Do not duplicate `party_name`. Do not put the UPI RRN hash
  (e.g. `ICI669ab0024...`) here.
### `ifsc` — full 11-character IFSC if present
- e.g. `SBIN0002499`, `HDFC0001968`, `UTIB0000084`, `PUNB0HGB001`.
- A short 4-letter bank code alone (`SBIN`, `PUNB`, `FINO`) is NOT an IFSC → `null`.
### Dates
- `value_date` and `txn_date` copied as written (e.g. `01/06/2026`,
  `01/May/2026`, `01/05/2026 07:51:08 AM`). Keep both if the statement has both.
-----
## Worked examples (cover both column styles and many rails)
**A. Debit/Credit-column bank, UPI credit (note: balance suffix CR is ignored)**
```
BY UPI CREDIT UPI/730090036071/UPI Payment XXXXX00944/9306200944@axl SBIN0002499/Minakshi  Minakshi
Credit Amount = 300.00 | Balance = 959419.59CR
```
```json
{ "mode":"UPI","direction":"credit","amount":300.00,"reference":"730090036071",
  "party_name":"Minakshi Minakshi","party_identifier":"9306200944@axl",
  "ifsc":"SBIN0002499","balance":959419.59 }
```
**B. Withdrawal/Deposit-column bank, RTGS outward (slash form)**
```
Withdrawal Amt = 4,50,000.00 | Remarks = RTGS/ICICR42026050100502895/HDFC0001968/BHAGWATITRANSPORT CO | TranId = S80780973
```
```json
{ "tran_id":"S80780973","mode":"RTGS","direction":"debit","amount":450000.00,
  "reference":"ICICR42026050100502895","party_name":"BHAGWATITRANSPORT CO",
  "party_identifier":null,"ifsc":"HDFC0001968" }
```
**C. RTGS inward (dash form: UTR-name-account-IFSC)**
```
Deposit Amt = 4,12,037.16 | Remarks = RTGS-UTIBR72026050100131060-ULTRA TECH CEMENT  LTD-084010200013129-UTIB0000084
```
```json
{ "mode":"RTGS","direction":"credit","amount":412037.16,
  "reference":"UTIBR72026050100131060","party_name":"ULTRA TECH CEMENT LTD",
  "party_identifier":"084010200013129","ifsc":"UTIB0000084" }
```
**D. UPI debit, ICICI layout (vehicle no in remark, truncated VPA, RRN hash)**
```
Withdrawal Amt = 4,200.00 | Remarks = UPI/109722460725/HR55AT7757/bachhu.singh4@i//ICI669ab0024aaa4b7387bc8bb48a82d08c/
```
```json
{ "mode":"UPI","direction":"debit","amount":4200.00,"reference":"109722460725",
  "party_name":null,"party_identifier":"bachhu.singh4@i","ifsc":null }
```
**E. NEFT (INF/NEFT/UTR/IFSC/ref/name)**
```
Withdrawal Amt = 1,25,000.00 | Remarks = INF/NEFT/IN42612156878597/HDFC0003519/HR63E3740   /SHRIBANKEHR63E3
```
```json
{ "mode":"NEFT","direction":"debit","amount":125000.00,
  "reference":"IN42612156878597","party_name":"SHRIBANKEHR63E3",
  "party_identifier":null,"ifsc":"HDFC0003519" }
```
**F. IMPS (MMT/IMPS/ref/short/name/bank)**
```
Deposit Amt = 1,00,000.00 | Remarks = MMT/IMPS/612557523735/ULTRA/JAI HANUMA/HDFC Bank
```
```json
{ "mode":"IMPS","direction":"credit","amount":100000.00,"reference":"612557523735",
  "party_name":"JAI HANUMA","party_identifier":null,"ifsc":null }
```
**G. Statutory / tax payment (GIB) → treated as charges/transfer out**
```
Withdrawal Amt = 18,217.00 | Remarks = GIB/002064785915/DTAX      /26050701119465ICIC
```
```json
{ "mode":"BANK CHARGES","direction":"debit","amount":18217.00,
  "reference":"002064785915","party_name":null,"party_identifier":null,
  "ifsc":null }
```
**H. Fee with no DEBIT word (debit column is filled → debit)**
```
UPI MDR CHARGES | Debit Amount = 3.54
```
```json
{ "mode":"BANK CHARGES","direction":"debit","amount":3.54,"reference":null,
  "party_name":null,"party_identifier":null,"ifsc":null }
```
**I. Cash deposit**
```
CASH DEPOSIT Deposit by SELF CASH DEP/HISAR GREEN SQUARE MKT | Credit Amount = 150000.00
```
```json
{ "mode":"CASH","direction":"credit","amount":150000.00,"reference":null,
  "party_name":"SELF","party_identifier":null,"ifsc":null }
```
**J. Inward cheque clearing (cheque no inside narration, not the chq column)**
```
INWARD CHQ  00918178 INW_CLG :ClgInwPr: ACCURIZE HEALTH,ChqNo:918178, | Debit Amount = 99000.00
```
```json
{ "mode":"CHEQUE","direction":"debit","amount":99000.00,"reference":"918178",
  "party_name":"ACCURIZE HEALTH","party_identifier":"00918178",
  "ifsc":null }
```
-----
## Final checks before returning
- One object per real transaction row, in statement order.
- Dropped: preamble, `BALANCE B/F`/opening, totals/`Page Total`, and the numbered
  legend/abbreviation footer.
- Every `direction` derived from which amount column is filled — never the balance
  `CR`/`DR` suffix and never the narration wording.
- All amounts comma-free positive numbers; Indian grouping expanded correctly.
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
                    "tran_id": {
                        "type": ["string", "null"],
                    },
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
                    "tran_id",
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
