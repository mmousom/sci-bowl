"""Tests for src/worker/regex_parser.py — structural field extraction, normalization,
Set_Round derivation, and Question_Id construction."""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.worker.regex_parser import (
    CANONICAL_CATEGORIES,
    buildQuestionId,
    deriveSetRound,
    normalizeCategory,
    parseStructuralFields,
)

# ---------------------------------------------------------------------------
# Format variant templates used by property and unit tests
# ---------------------------------------------------------------------------

# Each entry is a callable (question_number, category, match_type, answer_format) -> str
# that produces a valid chunk for that format variant.

def _newFormatChunk(
    questionNumber: str,
    category: str,
    matchType: str,
    answerFormat: str,
) -> str:
    """New Format: category line uses em-dash separator."""
    return (
        f"{matchType}\n"
        f"{questionNumber}) {category} – {answerFormat}\n"
        "QUESTION: What is the answer?\n"
    )


def _oldFormatChunk(
    questionNumber: str,
    category: str,
    matchType: str,
    answerFormat: str,
) -> str:
    """Old Format: category line uses space separator, category is upper-case."""
    return (
        f"{matchType}\n"
        f"{questionNumber}) {category.upper()} {answerFormat}\n"
        "QUESTION: What is the answer?\n"
    )


def _doubleElimChunk(
    questionNumber: str,
    category: str,
    matchType: str,
    answerFormat: str,
) -> str:
    """Double Elimination Format: same layout as Old Format."""
    return (
        f"{matchType}\n"
        f"{questionNumber}) {category.upper()} {answerFormat}\n"
        "QUESTION: What is the answer?\n"
    )


FORMAT_VARIANTS = [_newFormatChunk, _oldFormatChunk, _doubleElimChunk]

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_VALID_QUESTION_NUMBERS = st.integers(min_value=1, max_value=30).map(str)
_VALID_MATCH_TYPES = st.sampled_from(["TOSS-UP", "BONUS"])
_VALID_ANSWER_FORMATS = st.sampled_from(["Short Answer", "Multiple Choice"])
_VALID_CATEGORIES = st.sampled_from(sorted(CANONICAL_CATEGORIES))

# ---------------------------------------------------------------------------
# Property 4: Set_Round Derivation Round-Trip
# Validates: Requirements 4.1, 4.2
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 4: Set_Round Derivation Round-Trip
@given(
    setName=st.from_regex(r"[A-Za-z0-9-]+", fullmatch=True),
    filename=st.from_regex(r"[A-Za-z0-9-]+", fullmatch=True),
)
def test_deriveSetRoundRoundTrip(setName: str, filename: str) -> None:
    """deriveSetRound returns {setName}_{filename} for any valid key."""
    key = f"raw-pdf-vault/middle-school/{setName}/{filename}.pdf"
    assert deriveSetRound(key) == f"{setName}_{filename}"


# ---------------------------------------------------------------------------
# Property 5: Malformed S3 Key Rejection
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

_VALID_KEY_PATTERN = re.compile(
    r"^raw-pdf-vault/middle-school/[^/]+/[^/]+\.pdf$"
)


# Feature: sci-bowl-pdf-etl, Property 5: Malformed S3 Key Rejection
@given(key=st.text())
def test_deriveSetRoundRejectsInvalidKeys(key: str) -> None:
    """deriveSetRound raises ValueError for any key not matching the valid pattern."""
    if _VALID_KEY_PATTERN.match(key):
        return  # skip valid keys
    with pytest.raises(ValueError):
        deriveSetRound(key)


# ---------------------------------------------------------------------------
# Property 8: Structural Field Extraction Across All Formats
# Validates: Requirements 6.1, 6.2, 6.3, 6.4, 9.1, 9.2, 9.3, 9.4
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 8: Structural Field Extraction Across All Formats
@given(
    formatVariant=st.sampled_from(FORMAT_VARIANTS),
    questionNumber=_VALID_QUESTION_NUMBERS,
    category=_VALID_CATEGORIES,
    matchType=_VALID_MATCH_TYPES,
    answerFormat=_VALID_ANSWER_FORMATS,
)
def test_parseStructuralFieldsAllFormats(
    formatVariant: object,
    questionNumber: str,
    category: str,
    matchType: str,
    answerFormat: str,
) -> None:
    """parseStructuralFields extracts all four fields correctly across all format variants."""
    chunk = formatVariant(questionNumber, category, matchType, answerFormat)  # type: ignore[operator]
    result = parseStructuralFields(chunk)
    assert result["question_number"] == questionNumber
    assert result["category"] == category
    assert result["match_type"] == matchType
    assert result["answer_format"] == answerFormat


# ---------------------------------------------------------------------------
# Property 9: Category Normalization
# Validates: Requirements 6.5
# ---------------------------------------------------------------------------

def _randomCase(s: str) -> str:
    """Return a string with each character's case toggled randomly (deterministic via Hypothesis)."""
    # We use a fixed strategy: alternate upper/lower by index so Hypothesis can shrink it.
    return "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(s))


# Feature: sci-bowl-pdf-etl, Property 9: Category Normalization
@given(canonical=st.sampled_from(sorted(CANONICAL_CATEGORIES)))
def test_normalizeCategoryCanonicalVariants(canonical: str) -> None:
    """normalizeCategory returns the canonical form for any case variant of a canonical category."""
    # Test lower-case, upper-case, and alternating-case variants
    for variant in (canonical.lower(), canonical.upper(), _randomCase(canonical)):
        assert normalizeCategory(variant) == canonical


@given(raw=st.text())
def test_normalizeCategoryRejectsUnknown(raw: str) -> None:
    """normalizeCategory raises ValueError for any string not matching a canonical category."""
    if any(raw.strip().lower() == c.lower() for c in CANONICAL_CATEGORIES):
        return  # skip valid categories
    with pytest.raises(ValueError):
        normalizeCategory(raw)


# ---------------------------------------------------------------------------
# Property 14: Question_Id Format
# Validates: Requirements 8.2
# ---------------------------------------------------------------------------

_QUESTION_ID_PATTERN = re.compile(r"^Q_\d{2}_(TOSS-UP|BONUS)$")


# Feature: sci-bowl-pdf-etl, Property 14: Question_Id Format
@given(
    questionNumber=st.integers(1, 99),
    matchType=st.sampled_from(["TOSS-UP", "BONUS"]),
)
def test_buildQuestionIdFormat(questionNumber: int, matchType: str) -> None:
    """buildQuestionId always returns a string matching Q_{n:02d}_{matchType}."""
    result = buildQuestionId(str(questionNumber), matchType)
    assert _QUESTION_ID_PATTERN.match(result), f"Unexpected format: {result!r}"


# ===========================================================================
# Unit Tests (Task 4.8)
# Requirements: 4.1, 4.2, 4.3, 6.1–6.6, 9.1–9.5
# ===========================================================================


class TestDeriveSetRound:
    """Unit tests for deriveSetRound."""

    def test_typicalNewFormatKey(self) -> None:
        key = "raw-pdf-vault/middle-school/Sample-Set-13/2019-NSB-MSR-Round-10A.pdf"
        assert deriveSetRound(key) == "Sample-Set-13_2019-NSB-MSR-Round-10A"

    def test_oldFormatKey(self) -> None:
        key = "raw-pdf-vault/middle-school/Sample-Set-1/m_round01.pdf"
        assert deriveSetRound(key) == "Sample-Set-1_m_round01"

    def test_singleCharSegments(self) -> None:
        key = "raw-pdf-vault/middle-school/A/B.pdf"
        assert deriveSetRound(key) == "A_B"

    def test_malformedKeyTooFewSegments(self) -> None:
        with pytest.raises(ValueError):
            deriveSetRound("raw-pdf-vault/middle-school/only-three-segments")

    def test_malformedKeyNoPdfExtension(self) -> None:
        with pytest.raises(ValueError):
            deriveSetRound("raw-pdf-vault/middle-school/Set-1/round01.txt")

    def test_malformedKeyEmptyString(self) -> None:
        with pytest.raises(ValueError):
            deriveSetRound("")

    def test_malformedKeyWrongPrefix(self) -> None:
        with pytest.raises(ValueError):
            deriveSetRound("wrong-prefix/middle-school/Set-1/round01.pdf")

    def test_malformedKeyTooManySegments(self) -> None:
        with pytest.raises(ValueError):
            deriveSetRound("raw-pdf-vault/middle-school/Set-1/sub/round01.pdf")


class TestBuildQuestionId:
    """Unit tests for buildQuestionId — zero-padding and format."""

    def test_singleDigitTossUp(self) -> None:
        assert buildQuestionId("1", "TOSS-UP") == "Q_01_TOSS-UP"

    def test_singleDigitBonus(self) -> None:
        assert buildQuestionId("3", "BONUS") == "Q_03_BONUS"

    def test_twoDigitNumber(self) -> None:
        assert buildQuestionId("10", "TOSS-UP") == "Q_10_TOSS-UP"

    def test_largeNumber(self) -> None:
        assert buildQuestionId("99", "BONUS") == "Q_99_BONUS"

    def test_zeroPaddingApplied(self) -> None:
        result = buildQuestionId("5", "TOSS-UP")
        assert result.startswith("Q_0"), f"Expected zero-padding, got {result!r}"


class TestNormalizeCategory:
    """Unit tests for normalizeCategory."""

    def test_exactCanonicalPassthrough(self) -> None:
        assert normalizeCategory("Life Science") == "Life Science"

    def test_allUpperCase(self) -> None:
        assert normalizeCategory("LIFE SCIENCE") == "Life Science"

    def test_allLowerCase(self) -> None:
        assert normalizeCategory("earth and space") == "Earth and Space"

    def test_mixedCase(self) -> None:
        assert normalizeCategory("pHySiCaL sCiEnCe") == "Physical Science"

    def test_leadingTrailingWhitespace(self) -> None:
        assert normalizeCategory("  Mathematics  ") == "Mathematics"

    def test_unknownCategoryRaisesValueError(self) -> None:
        with pytest.raises(ValueError):
            normalizeCategory("Biology")

    def test_emptyStringRaisesValueError(self) -> None:
        with pytest.raises(ValueError):
            normalizeCategory("")

    def test_partialMatchRaisesValueError(self) -> None:
        with pytest.raises(ValueError):
            normalizeCategory("Life")


class TestParseStructuralFieldsNewFormat:
    """Unit tests for parseStructuralFields — New Format (em-dash separator)."""

    def test_shortAnswerChunk(self) -> None:
        chunk = "TOSS-UP\n1) Earth and Space – Short Answer\nQ: What is gravity?\n"
        result = parseStructuralFields(chunk)
        assert result["match_type"] == "TOSS-UP"
        assert result["question_number"] == "1"
        assert result["category"] == "Earth and Space"
        assert result["answer_format"] == "Short Answer"

    def test_multipleChoiceChunk(self) -> None:
        chunk = "BONUS\n2) Life Science – Multiple Choice\nQ: Which cell?\n"
        result = parseStructuralFields(chunk)
        assert result["match_type"] == "BONUS"
        assert result["question_number"] == "2"
        assert result["category"] == "Life Science"
        assert result["answer_format"] == "Multiple Choice"

    def test_physicalScienceCategory(self) -> None:
        chunk = "TOSS-UP\n5) Physical Science – Short Answer\nQ: What is force?\n"
        result = parseStructuralFields(chunk)
        assert result["category"] == "Physical Science"

    def test_mathematicsCategory(self) -> None:
        chunk = "BONUS\n3) Mathematics – Multiple Choice\nQ: Solve for x.\n"
        result = parseStructuralFields(chunk)
        assert result["category"] == "Mathematics"


class TestParseStructuralFieldsOldFormat:
    """Unit tests for parseStructuralFields — Old Format (space separator, upper-case category)."""

    def test_shortAnswerChunk(self) -> None:
        chunk = "TOSS-UP\n1) LIFE SCIENCE Short Answer\nQ: What is DNA?\n"
        result = parseStructuralFields(chunk)
        assert result["match_type"] == "TOSS-UP"
        assert result["question_number"] == "1"
        assert result["category"] == "Life Science"
        assert result["answer_format"] == "Short Answer"

    def test_multipleChoiceChunk(self) -> None:
        chunk = "BONUS\n4) EARTH AND SPACE Multiple Choice\nQ: Name a planet.\n"
        result = parseStructuralFields(chunk)
        assert result["match_type"] == "BONUS"
        assert result["question_number"] == "4"
        assert result["category"] == "Earth and Space"
        assert result["answer_format"] == "Multiple Choice"


class TestParseStructuralFieldsDoubleElimFormat:
    """Unit tests for parseStructuralFields — Double Elimination Format."""

    def test_shortAnswerChunk(self) -> None:
        chunk = "TOSS-UP\n1) GENERAL SCIENCE Short Answer\nQ: What is energy?\n"
        result = parseStructuralFields(chunk)
        assert result["match_type"] == "TOSS-UP"
        assert result["question_number"] == "1"
        assert result["category"] == "General Science"
        assert result["answer_format"] == "Short Answer"

    def test_chemistryCategory(self) -> None:
        chunk = "BONUS\n2) CHEMISTRY Multiple Choice\nQ: What is H2O?\n"
        result = parseStructuralFields(chunk)
        assert result["category"] == "Chemistry"


class TestParseStructuralFieldsMissingFields:
    """Unit tests for parseStructuralFields — missing/invalid field handling."""

    def test_missingMatchTypeRaisesValueError(self) -> None:
        chunk = "1) Life Science – Short Answer\nQ: What?\n"
        with pytest.raises(ValueError, match="match_type"):
            parseStructuralFields(chunk)

    def test_missingQuestionNumberRaisesValueError(self) -> None:
        # No digit) pattern on any line
        chunk = "TOSS-UP\nLife Science – Short Answer\nQ: What?\n"
        with pytest.raises(ValueError, match="question_number"):
            parseStructuralFields(chunk)

    def test_missingAnswerFormatRaisesValueError(self) -> None:
        chunk = "TOSS-UP\n1) Life Science\nQ: What?\n"
        with pytest.raises(ValueError, match="answer_format"):
            parseStructuralFields(chunk)

    def test_missingCategoryRaisesValueError(self) -> None:
        # Category line has number and answer format but no recognizable category text
        chunk = "TOSS-UP\n1) Short Answer\nQ: What?\n"
        with pytest.raises(ValueError):
            parseStructuralFields(chunk)

    def test_emptyChunkRaisesValueError(self) -> None:
        with pytest.raises(ValueError):
            parseStructuralFields("")
