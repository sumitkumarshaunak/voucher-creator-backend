import base64


FILE_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def file_data_uri(file_path):
    suffix = file_path.suffix.lower()
    mime_type = FILE_MIME_TYPES[suffix]
    b64 = base64.b64encode(file_path.read_bytes()).decode()
    return f"data:{mime_type};base64,{b64}"
