from extractors import bank_statement_extractor, invoice_extractor, sales_report_extractor


SUPPORTED_DOCUMENT_TYPES = (
    invoice_extractor.SUPPORTED_DOCUMENT_TYPES
    | bank_statement_extractor.SUPPORTED_DOCUMENT_TYPES
    | sales_report_extractor.SUPPORTED_DOCUMENT_TYPES
)


def infer_document_type(file_path):
    return invoice_extractor.infer_document_type(file_path)


def extract_document(file_path, document_type=None, row_options=None):
    selected_document_type = document_type or infer_document_type(file_path)

    if selected_document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError("Unsupported document type.")

    if selected_document_type == "bank_statement":
        return bank_statement_extractor.extract_file(
            file_path,
            document_type=selected_document_type,
            row_options=row_options,
        )

    if selected_document_type == "sales_report":
        return sales_report_extractor.extract_file(
            file_path,
            document_type=selected_document_type,
            row_options=row_options,
        )

    if selected_document_type == "invoice":
        return invoice_extractor.extract_file(
            file_path,
            document_type=selected_document_type,
            row_options=row_options,
        )

    raise ValueError("Unsupported document type.")


def extract_documents(file_paths, document_type=None, row_options=None):
    if not file_paths:
        raise ValueError("At least one file is required.")

    selected_document_type = document_type or infer_document_type(file_paths[0])

    if selected_document_type != "invoice":
        raise ValueError("Multiple-file extraction is supported for invoice images only.")

    return invoice_extractor.extract_files(
        file_paths,
        document_type=selected_document_type,
        row_options=row_options,
    )
