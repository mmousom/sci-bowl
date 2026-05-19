"""Structural field extraction and normalization for Science Bowl PDF chunks."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CANONICAL_CATEGORIES: frozenset[str] = frozenset({
    "Biology",
    "Chemistry",
    "Computer Science",
    "Earth and Space Science",
    "Energy",
    "General Science",
    "Life Science",
    "Mathematics",
    "Physical Science",
    "Physics",
    "Astronomy",
})

# Maps any known alias (lowercased) to its canonical form.
# Add new aliases here as new PDF sets introduce variant spellings.
_CATEGORY_ALIASES: dict[str, str] = {
    # Earth variants
    "earth science":             "Earth and Space Science",
    "earth and space":           "Earth and Space Science",
    "earth & space":             "Earth and Space Science",
    "earth & space science":     "Earth and Space Science",
    # Math variants
    "math":                      "Mathematics",
    "maths":                     "Mathematics",
}

# Regex patterns for structural field extraction
_MATCH_TYPE_PATTERN = re.compile(r"^(TOSS-UP|BONUS)", re.MULTILINE)
_QUESTION_NUMBER_PATTERN = re.compile(r"(\d+)\)")
_ANSWER_FORMAT_PATTERN = re.compile(r"(Short Answer|Multiple Choice)", re.IGNORECASE)
_CATEGORY_NEW_PATTERN = re.compile(
    r"\d+\)\s+(.+?)\s+[–-]\s+(?:Short Answer|Multiple Choice)",
    re.IGNORECASE,
)
_CATEGORY_OLD_PATTERN = re.compile(
    r"\d+\)\s+([A-Z][A-Z ]+?)\s+(?:Short Answer|Multiple Choice)",
    re.IGNORECASE,
)

# Validation pattern for S3 key structure
_S3_KEY_PATTERN = re.compile(
    r"^raw-pdf-vault/middle-school/([^/]+)/([^/]+\.pdf)$"
)


def _extractMatchType(chunk: str) -> str | None:
    """Return the match type from the first line of a chunk, or None."""
    match = _MATCH_TYPE_PATTERN.search(chunk)
    return match.group(1) if match else None


def _extractQuestionNumber(categoryLine: str) -> str | None:
    """Return the question number from the category line, or None."""
    match = _QUESTION_NUMBER_PATTERN.search(categoryLine)
    return match.group(1) if match else None


def _extractAnswerFormat(categoryLine: str) -> str | None:
    """Return the answer format from the category line, or None."""
    match = _ANSWER_FORMAT_PATTERN.search(categoryLine)
    if not match:
        return None
    raw = match.group(1)
    # Normalise to canonical casing
    lower = raw.lower()
    if lower == "short answer":
        return "Short Answer"
    if lower == "multiple choice":
        return "Multiple Choice"
    return None


def _extractCategory(categoryLine: str) -> str | None:
    """Return the raw category string from the category line, or None."""
    match = _CATEGORY_NEW_PATTERN.search(categoryLine)
    if match:
        return match.group(1).strip()
    match = _CATEGORY_OLD_PATTERN.search(categoryLine)
    if match:
        return match.group(1).strip()
    return None


def _findCategoryLine(chunk: str) -> str:
    """Return the line in the chunk that contains the question number and category."""
    for line in chunk.splitlines():
        if _QUESTION_NUMBER_PATTERN.search(line):
            return line
    return ""


def parseStructuralFields(chunk: str) -> dict[str, str]:
    """Extract structural fields from a PDF question chunk via regex.

    Extracts ``question_number``, ``category``, ``match_type``, and
    ``answer_format`` from the raw chunk text.

    Args:
        chunk: A single question block starting with ``TOSS-UP`` or ``BONUS``.

    Returns:
        A dict with keys ``question_number``, ``category``, ``match_type``,
        and ``answer_format``.

    Raises:
        ValueError: If any required field cannot be extracted or is invalid.
    """
    match_type = _extractMatchType(chunk)
    if not match_type:
        logger.error(
            "parseStructuralFields: missing field=match_type chunk=%.500s", chunk
        )
        raise ValueError("Missing field: match_type")

    categoryLine = _findCategoryLine(chunk)

    question_number = _extractQuestionNumber(categoryLine)
    if not question_number:
        logger.error(
            "parseStructuralFields: missing field=question_number chunk=%.500s", chunk
        )
        raise ValueError("Missing field: question_number")

    answer_format = _extractAnswerFormat(categoryLine)
    if not answer_format:
        logger.error(
            "parseStructuralFields: missing field=answer_format chunk=%.500s", chunk
        )
        raise ValueError("Missing field: answer_format")

    rawCategory = _extractCategory(categoryLine)
    if not rawCategory:
        logger.warning(
            "parseStructuralFields: category not found, defaulting to 'General Science'. "
            "chunk=%.500s", chunk
        )
        rawCategory = "General Science"

    category = normalizeCategory(rawCategory)

    return {
        "question_number": question_number,
        "category": category,
        "match_type": match_type,
        "answer_format": answer_format,
    }


def normalizeCategory(raw: str) -> str:
    """Normalise a raw category string to its canonical title-case form.

    Resolution order:
    1. Alias map lookup (case-insensitive) — handles known variant spellings.
    2. Exact case-insensitive match against CANONICAL_CATEGORIES.
    3. Unknown category — stored as title-cased raw value so no question is
       dropped; a warning is logged so new variants can be added to the alias
       map on the next ETL run.

    Args:
        raw: The raw category string extracted from a PDF chunk.

    Returns:
        The canonical category name, or title-cased raw value if unknown.

    Raises:
        ValueError: If the value is empty after stripping.
    """
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Category is empty")

    lowerRaw = stripped.lower()

    # 1. Alias map — explicit variant → canonical mapping
    if lowerRaw in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[lowerRaw]

    # 2. Exact case-insensitive match against canonical set
    for canonical in CANONICAL_CATEGORIES:
        if canonical.lower() == lowerRaw:
            return canonical

    # 3. Unknown — store as title-case, log for future alias addition
    titleCased = stripped.title()
    logger.warning(
        "normalizeCategory: unknown category raw=%r, storing as %r — "
        "add to _CATEGORY_ALIASES if this is a known variant",
        raw,
        titleCased,
    )
    return titleCased


def deriveSetRound(s3Key: str) -> str:
    """Derive the ``Set_Round`` value from an S3 object key.

    Expects a key of the form
    ``raw-pdf-vault/middle-school/{set-name}/{filename}.pdf``.

    Args:
        s3Key: The full S3 object key.

    Returns:
        A string of the form ``{set-name}_{filename}`` (filename without the
        ``.pdf`` extension).

    Raises:
        ValueError: If the key does not match the expected 4-segment pattern.
    """
    match = _S3_KEY_PATTERN.match(s3Key)
    if not match:
        logger.error("deriveSetRound: malformed S3 key=%r", s3Key)
        raise ValueError(f"Malformed S3 key: {s3Key!r}")

    segments = s3Key.split("/")
    setName = segments[2]
    stem = Path(segments[3]).stem
    return f"{setName}_{stem}"


def buildQuestionId(questionNumber: str, matchType: str) -> str:
    """Build the ``Question_Id`` sort key for a DynamoDB item.

    Args:
        questionNumber: The question number as a string (e.g. ``"1"``).
        matchType: Either ``"TOSS-UP"`` or ``"BONUS"``.

    Returns:
        A string of the form ``Q_{n:02d}_{matchType}``
        (e.g. ``"Q_01_TOSS-UP"``).
    """
    return f"Q_{int(questionNumber):02d}_{matchType}"
