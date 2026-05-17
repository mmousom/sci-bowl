"""Question chunker: splits raw PDF text into per-question blocks."""

import logging
import re

logger = logging.getLogger(__name__)

_SPLIT_PATTERN = re.compile(r"(?m)^(?=TOSS-UP|BONUS)")


def chunkQuestions(text: str) -> list[str]:
    """Split PDF text into individual question chunks.

    Splits on lines beginning with ``TOSS-UP`` or ``BONUS``, preserving the
    header line in each chunk.  Leading whitespace-only segments (e.g. page
    headers before the first question) are discarded.

    Args:
        text: Full concatenated text extracted from a PDF.

    Returns:
        A list of non-empty chunk strings, each starting with ``TOSS-UP`` or
        ``BONUS``.

    Raises:
        ValueError: If ``text`` contains no non-whitespace characters (blank
            document), or if ``text`` is non-empty but produces zero chunks
            (no ``TOSS-UP``/``BONUS`` lines found).
    """
    if not text.strip():
        logger.warning("chunkQuestions received text with no non-whitespace characters")
        raise ValueError("Text contains no non-whitespace characters and no TOSS-UP/BONUS lines")

    raw_chunks = _SPLIT_PATTERN.split(text)
    # Keep only segments that start with TOSS-UP or BONUS (the real question chunks).
    # Segments before the first header (e.g. page titles) are discarded.
    chunks = [c for c in raw_chunks if c.lstrip().startswith(("TOSS-UP", "BONUS"))]

    if not chunks:
        logger.warning(
            "chunkQuestions produced zero chunks from non-empty text (first 200 chars): %.200s",
            text,
        )
        raise ValueError("Non-empty text produced zero chunks — no TOSS-UP/BONUS lines found")

    return chunks
