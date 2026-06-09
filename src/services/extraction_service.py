from extractors import bank_statement_extractor, invoice_extractor


SUPPORTED_DOCUMENT_TYPES = (
    invoice_extractor.SUPPORTED_DOCUMENT_TYPES
    | bank_statement_extractor.SUPPORTED_DOCUMENT_TYPES
)


def infer_document_type(file_path):
    return invoice_extractor.infer_document_type(file_path)


def extract_document(file_path, document_type=None):
    selected_document_type = document_type or infer_document_type(file_path)

    if selected_document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError("Unsupported document type.")

    if selected_document_type == "bank_statement":
        return bank_statement_extractor.extract_file(
            file_path,
            document_type=selected_document_type,
        )

    if selected_document_type == "invoice":
        return invoice_extractor.extract_file(
            file_path,
            document_type=selected_document_type,
        )

    raise ValueError("Unsupported document type.")
