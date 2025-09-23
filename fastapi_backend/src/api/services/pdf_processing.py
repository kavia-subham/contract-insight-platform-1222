import io

from PyPDF2 import PdfReader


# PUBLIC_INTERFACE
def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text content from a PDF byte stream.

    This function attempts to read the provided bytes as a PDF document using
    PyPDF2 and returns concatenated text from all pages.

    Args:
        pdf_bytes: The raw bytes of the uploaded PDF file.

    Returns:
        A string containing the extracted text from the PDF.

    Raises:
        ValueError: If the PDF cannot be parsed or contains no extractable text.
    """
    try:
        buffer = io.BytesIO(pdf_bytes)
        reader = PdfReader(buffer)
    except Exception as exc:
        raise ValueError(f"Failed to read PDF: {exc}") from exc

    texts = []
    try:
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                # If a page fails to extract, continue with others
                text = ""
            texts.append(text)
    except Exception as exc:
        raise ValueError(f"Failed while iterating PDF pages: {exc}") from exc

    combined = "\n".join(part for part in texts if part is not None)
    combined = combined.strip()

    if not combined:
        raise ValueError("No extractable text found in PDF.")

    return combined
