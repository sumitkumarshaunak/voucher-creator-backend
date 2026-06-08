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

BANK_STATEMENT_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "transactions": {
            "description": "List of all transaction rows present in the statement. Extract every transaction row exactly once. Do not skip rows and do not include opening or closing balance rows as transactions.",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value_date": {
                        "description": "The transaction value date or effective date. Extract in YYYY-MM-DD format. Use the date associated with the transaction row, not the statement generation date.",
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                    "transaction_number": {
                        "description": "Unique transaction reference number associated with the transaction. Examples include UTR number, UPI reference number, transaction ID, bank reference number, cheque number, or journal reference. Do not use account numbers, IFSC codes, balances, or customer IDs.",
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                    "payment_mode": {
                        "description": "Payment channel or transaction mode. Examples: UPI, IMPS, NEFT, RTGS, CASH, CHEQUE, ATM, CARD, ECS, NACH, INTEREST, BANK CHARGES, TRANSFER. Extract only the transaction mode, not the full narration.",
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                    "party": {
                        "description": "Counterparty involved in the transaction. This may be a customer, vendor, bank account holder, merchant, beneficiary, remitter, or payer.",
                        "type": "object",
                        "properties": {
                            "name": {
                                "description": "Human-readable name of the counterparty. Examples: 'SANJAY KUMAR', 'ULTRA TECH CEMENT LTD', 'BHAGWATI TRANSPORT CO'. Do not populate with UPI IDs, account numbers, phone numbers, or reference numbers.",
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                            },
                            "identifier": {
                                "description": "Machine-readable identifier of the counterparty when available. Examples: UPI ID, virtual payment address (VPA), mobile-linked identifier, masked account number, merchant ID, beneficiary account reference, or similar identifier. Do not duplicate the party name unless no better identifier exists.",
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                            },
                        },
                        "required": ["name", "identifier"],
                        "additionalProperties": False,
                    },
                    "amount": {
                        "description": "Transaction amount only. Extract the absolute monetary value without sign symbols. Do not include running balance, opening balance, closing balance, taxes, or fees unless they are the actual transaction amount.",
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                    },
                    "direction": {
                        "description": "Direction of money movement relative to the account. Use 'credit' when money enters the account and 'debit' when money leaves the account. Map CR/CREDIT to 'credit' and DR/DEBIT to 'debit'.",
                        "anyOf": [
                            {"type": "string", "enum": ["credit", "debit"]},
                            {"type": "null"},
                        ],
                    },
                },
                "required": [
                    "value_date",
                    "transaction_number",
                    "payment_mode",
                    "party",
                    "amount",
                    "direction",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["transactions"],
    "additionalProperties": False,
}

BANK_STATEMENT_SYSTEM_PROMPT = """
You are an expert bank statement transaction extraction system.

Extract every transaction row exactly once from the provided bank statement.
Return data strictly matching the provided schema.

Rules:
1. Do not include opening balance, closing balance, carried forward, brought forward, summary, or totals rows as transactions.
2. Use the transaction row date for value_date and return it in YYYY-MM-DD format.
3. Extract only the transaction amount, not the running balance.
4. Use absolute amount values. Put money movement in direction as credit or debit.
5. Extract the payment mode only, such as UPI, IMPS, NEFT, RTGS, CASH, CHEQUE, ATM, CARD, ECS, NACH, INTEREST, BANK CHARGES, or TRANSFER.
6. Extract transaction_number from UTR, UPI reference, transaction ID, bank reference, cheque number, or journal reference when present.
7. Do not use account numbers, IFSC codes, customer IDs, balances, or phone numbers as transaction_number.
8. Extract party.name only when a human-readable counterparty name is present.
9. Put UPI IDs, VPAs, masked account numbers, merchant IDs, beneficiary references, or similar machine-readable values in party.identifier.
10. Use null when a value cannot be confidently identified.
11. Never guess, calculate, or invent missing values.

Return only the structured output matching the provided schema.
"""

DATA_SCHEMA = INVOICE_DATA_SCHEMA
SYSTEM_PROMPT = INVOICE_SYSTEM_PROMPT
