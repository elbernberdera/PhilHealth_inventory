"""Validate PPE asset PDF uploads without trusting client Content-Type or extension alone."""

from __future__ import annotations

from typing import Optional

# Reasonable cap for attachment PDFs; adjust if needed.
MAX_PPE_PDF_BYTES = 10 * 1024 * 1024

_PDF_SIG = b"%PDF-"
_UTF8_BOM = b"\xef\xbb\xbf"


def validate_ppe_pdf_upload(uploaded_file) -> Optional[str]:
    """
    Return a user-facing error string if the upload is not an acceptable PDF, else None.
    Always seeks the file back to offset 0 on success or failure so callers can save it.
    """
    if uploaded_file is None:
        return None

    name = getattr(uploaded_file, "name", "") or ""
    if "\x00" in name:
        return "Invalid file name."

    if not name.lower().endswith(".pdf"):
        return "Only PDF files are allowed (.pdf extension)."

    try:
        size = int(getattr(uploaded_file, "size", 0) or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return "The uploaded file is empty."
    if size > MAX_PPE_PDF_BYTES:
        return "PDF file is too large (maximum 10 MB)."

    uploaded_file.seek(0)
    head = uploaded_file.read(2048)
    uploaded_file.seek(0)

    if head.startswith(_UTF8_BOM):
        head = head[len(_UTF8_BOM) :]

    if not head.startswith(_PDF_SIG):
        return "File content is not a valid PDF."

    return None
