import csv
import mimetypes
from io import StringIO
from pathlib import Path


ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".csv"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "application/octet-stream",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel"
}
MAX_BINARY_CONTROL_CHAR_RATIO = 0.20


def get_file_extension(filename):
    return Path(filename or "").suffix.lower()


def get_file_size(file):
    size = getattr(file, "size", None)

    if size is not None:
        return size

    return len(file.getvalue())


def has_binary_signature(file_bytes):
    if b"\x00" in file_bytes:
        return True

    if not file_bytes:
        return False

    allowed_control_bytes = {9, 10, 13}
    control_byte_count = sum(
        1 for byte in file_bytes
        if byte < 32 and byte not in allowed_control_bytes
    )
    control_byte_ratio = control_byte_count / len(file_bytes)

    return control_byte_ratio > MAX_BINARY_CONTROL_CHAR_RATIO


def decode_uploaded_text(file_bytes):
    if file_bytes.startswith(b"\xef\xbb\xbf"):
        return file_bytes.decode("utf-8-sig")

    return file_bytes.decode("utf-8")


def validate_csv_content(filename, content):
    if not content.strip():
        return f"{filename} is empty."

    if "\n" not in content and not any(delimiter in content for delimiter in [",", "\t", ";"]):
        return (
            f"{filename} looks like plain text, not a CSV file. "
            "Upload it as .txt or .md instead."
        )

    sample = content[:4096]

    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    try:
        rows = list(csv.reader(StringIO(content), dialect))
    except csv.Error as e:
        return f"{filename} could not be parsed as CSV: {e}"

    non_empty_rows = [
        row for row in rows
        if any(cell.strip() for cell in row)
    ]

    if not non_empty_rows:
        return f"{filename} does not contain usable CSV rows."

    if len(non_empty_rows) == 1 and len(non_empty_rows[0]) == 1:
        return (
            f"{filename} looks like plain text, not a CSV file. "
            "Upload it as .txt or .md instead."
        )

    return None


def validate_uploaded_file(file, max_upload_file_size_bytes, max_upload_file_size_mb):
    filename = file.name or "uploaded file"
    extension = get_file_extension(filename)

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        return None, (
            f"{filename} has unsupported extension '{extension or 'none'}'. "
            "Allowed types are .txt, .md, and .csv."
        )

    file_size = get_file_size(file)

    if file_size == 0:
        return None, f"{filename} is empty."

    if file_size > max_upload_file_size_bytes:
        return None, (
            f"{filename} is too large. Max file size is "
            f"{max_upload_file_size_mb} MB."
        )

    uploaded_mime_type = (getattr(file, "type", None) or "").lower()
    guessed_mime_type, _ = mimetypes.guess_type(filename)
    guessed_mime_type = (guessed_mime_type or "").lower()
    mime_types_to_check = {
        mime_type for mime_type in [uploaded_mime_type, guessed_mime_type]
        if mime_type
    }

    disallowed_mime_types = mime_types_to_check - ALLOWED_UPLOAD_MIME_TYPES

    if disallowed_mime_types:
        return None, (
            f"{filename} has unsupported content type: "
            f"{', '.join(sorted(disallowed_mime_types))}."
        )

    file_bytes = file.getvalue()

    if has_binary_signature(file_bytes):
        return None, (
            f"{filename} appears to contain binary data and was blocked."
        )

    try:
        content = decode_uploaded_text(file_bytes)
    except UnicodeDecodeError:
        return None, (
            f"{filename} is not valid UTF-8 text. Please upload a UTF-8 "
            "encoded .txt, .md, or .csv file."
        )

    if not content.strip():
        return None, f"{filename} does not contain readable text."

    if extension == ".csv":
        csv_error = validate_csv_content(filename, content)

        if csv_error:
            return None, csv_error

    return content, None
