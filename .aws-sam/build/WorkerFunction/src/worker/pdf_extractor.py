"""PDF download and text extraction utilities for the Worker Lambda."""

import io
import logging

import pdfplumber

logger = logging.getLogger(__name__)


def downloadPdf(s3Client, bucket: str, key: str) -> bytes:
    """Download a PDF from S3 and return its raw bytes.

    Args:
        s3Client: A boto3 S3 client.
        bucket: The S3 bucket name.
        key: The S3 object key.

    Returns:
        The raw PDF bytes.

    Raises:
        Exception: Re-raises any exception from ``get_object`` after logging.
    """
    try:
        response = s3Client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except Exception as exc:
        logger.error("Failed to download PDF from S3. key=%s error=%s", key, exc)
        raise


def extractText(pdfBytes: bytes) -> str:
    """Extract and concatenate text from all pages of a PDF.

    Pages that return ``None`` or an empty string from ``extract_text()``
    are treated as empty strings. Pages are concatenated in page order.

    Args:
        pdfBytes: Raw PDF bytes.

    Returns:
        Concatenated text from all pages.

    Raises:
        Exception: Re-raises any pdfplumber exception after logging.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdfBytes)) as pdf:
            parts: list[str] = []
            for page in pdf.pages:
                text = page.extract_text()
                parts.append(text if text else "")
            return "".join(parts)
    except Exception as exc:
        logger.error("Failed to extract text from PDF. error=%s", exc)
        raise
