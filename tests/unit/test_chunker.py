"""Tests for src/worker/chunker.py — property-based and unit tests."""

import pytest
from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st

from src.worker.chunker import chunkQuestions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADERS = ["TOSS-UP\n", "BONUS\n"]

# Lines that would be mis-interpreted as chunk boundaries must not appear at
# the start of a generated block's lines.
_FORBIDDEN_LINE_STARTS = ("TOSS-UP", "BONUS")


def _isSafeBlock(block: str) -> bool:
    """Return True if no line in block starts with TOSS-UP or BONUS."""
    return not any(
        line.startswith(_FORBIDDEN_LINE_STARTS)
        for line in block.splitlines()
    )


# Strategy: text blocks that cannot be mis-parsed as chunk boundaries.
# Blocks must end with '\n' so that the next TOSS-UP/BONUS header always
# lands at the start of a new line when blocks are concatenated.
_safeBlockStrategy = st.text(min_size=1).filter(_isSafeBlock).map(
    lambda b: b if b.endswith("\n") else b + "\n"
)


# ---------------------------------------------------------------------------
# Property 6: Chunker Partitions Text Correctly
# Feature: sci-bowl-pdf-etl, Property 6: Chunker Partitions Text Correctly
# Validates: Requirements 5.1, 5.4
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 6: Chunker Partitions Text Correctly
@given(st.lists(_safeBlockStrategy, min_size=1))
@settings(max_examples=200, suppress_health_check=[HealthCheck.filter_too_much])
def test_chunkerPartitionsTextCorrectly(blocks: list[str]) -> None:
    """For N blocks each prefixed with TOSS-UP/BONUS, chunkQuestions returns
    exactly N chunks whose concatenation equals the original input.

    Validates: Requirements 5.1, 5.4
    """
    # Prepend a TOSS-UP or BONUS header to each block, alternating header type.
    prefixed = [(_HEADERS[i % 2] + block) for i, block in enumerate(blocks)]
    original = "".join(prefixed)

    chunks = chunkQuestions(original)

    assert len(chunks) == len(prefixed), (
        f"Expected {len(prefixed)} chunks, got {len(chunks)}"
    )
    assert "".join(chunks) == original, (
        "Concatenation of chunks does not equal original input"
    )


# ---------------------------------------------------------------------------
# Property 7: Non-Empty Input Produces At Least One Chunk
# Feature: sci-bowl-pdf-etl, Property 7: Non-Empty Input Produces At Least One Chunk
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

# Strategy: build text that is guaranteed to contain at least one TOSS-UP/BONUS
# line by constructing it directly rather than filtering random text.
_textWithHeaderStrategy = st.builds(
    lambda header, suffix: header + suffix,
    header=st.sampled_from(["TOSS-UP\n", "BONUS\n"]),
    suffix=st.text(),
)


# Feature: sci-bowl-pdf-etl, Property 7: Non-Empty Input Produces At Least One Chunk
@given(_textWithHeaderStrategy)
@settings(max_examples=200)
def test_chunkQuestionsProducesAtLeastOne(text: str) -> None:
    """Any text containing at least one TOSS-UP or BONUS line produces >= 1 chunk.

    Validates: Requirements 5.2
    """
    chunks = chunkQuestions(text)
    assert len(chunks) >= 1, "Expected at least one chunk from text with TOSS-UP/BONUS line"


# ---------------------------------------------------------------------------
# Unit tests for chunker.py
# Validates: Requirements 5.1, 5.2, 5.3, 5.5
# ---------------------------------------------------------------------------

# --- New Format ---

def test_newFormatChunksCorrectly() -> None:
    """New Format PDF text is split into the correct number of chunks."""
    text = (
        "MIDDLE SCHOOL - ROUND 10A\n"
        "TOSS-UP\n"
        "1) Earth and Space – Short Answer\n"
        "ANSWER: Mars\n"
        "BONUS\n"
        "1) Earth and Space – Short Answer\n"
        "ANSWER: Jupiter\n"
    )
    chunks = chunkQuestions(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("TOSS-UP")
    assert chunks[1].startswith("BONUS")


# --- Old Format ---

def test_oldFormatChunksCorrectly() -> None:
    """Old Format PDF text (all-caps category, space-separated) is chunked correctly."""
    text = (
        "ROUND 1\n"
        "TOSS-UP\n"
        "1) LIFE SCIENCE Short Answer\n"
        "ANSWER: Mitosis\n"
        "BONUS\n"
        "1) LIFE SCIENCE Short Answer\n"
        "ANSWER: Meiosis\n"
    )
    chunks = chunkQuestions(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("TOSS-UP")
    assert chunks[1].startswith("BONUS")


# --- Double Elimination Format ---

def test_doubleEliminationFormatChunksCorrectly() -> None:
    """Double Elimination Format PDF text is chunked correctly."""
    text = (
        "DOUBLE ELIMINATION ROUND 1\n"
        "TOSS-UP\n"
        "1) GENERAL SCIENCE Short Answer\n"
        "ANSWER: Gravity\n"
        "BONUS\n"
        "1) GENERAL SCIENCE Short Answer\n"
        "ANSWER: Friction\n"
    )
    chunks = chunkQuestions(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("TOSS-UP")
    assert chunks[1].startswith("BONUS")


# --- Single chunk ---

def test_singleChunkReturnsOneElement() -> None:
    """A text with exactly one TOSS-UP block returns a list of length 1."""
    text = "TOSS-UP\n1) Mathematics Short Answer\nANSWER: 42\n"
    chunks = chunkQuestions(text)
    assert len(chunks) == 1
    assert chunks[0] == text


# --- Empty text ---

def test_emptyTextRaisesValueError() -> None:
    """Empty string raises ValueError (no non-whitespace characters)."""
    with pytest.raises(ValueError):
        chunkQuestions("")


# --- Whitespace-only text ---

def test_whitespaceOnlyTextRaisesValueError() -> None:
    """Text containing only whitespace raises ValueError."""
    with pytest.raises(ValueError):
        chunkQuestions("   \n\t\n  ")


# --- Non-empty text with no TOSS-UP/BONUS headers ---

def test_nonEmptyTextWithNoHeadersRaisesValueError() -> None:
    """Non-empty text that contains no TOSS-UP/BONUS lines raises ValueError."""
    with pytest.raises(ValueError):
        chunkQuestions("This is some text without any question headers.\n")


# --- Chunk text is preserved verbatim (Requirement 5.4) ---

def test_chunkTextPreservedVerbatim() -> None:
    """Each chunk's text is preserved exactly as it appears in the original."""
    block1 = "TOSS-UP\n1) Energy – Multiple Choice\nW) A\nX) B\nY) C\nZ) D\nANSWER: W\n"
    block2 = "BONUS\n1) Energy – Multiple Choice\nW) E\nX) F\nY) G\nZ) H\nANSWER: X\n"
    text = block1 + block2
    chunks = chunkQuestions(text)
    assert chunks[0] == block1
    assert chunks[1] == block2


# --- Leading preamble before first header is discarded ---

def test_leadingPreambleIsDiscarded() -> None:
    """Text before the first TOSS-UP/BONUS header is not included in any chunk."""
    preamble = "MIDDLE SCHOOL - ROUND 5\nSome preamble text\n"
    question = "TOSS-UP\n1) Math Short Answer\nANSWER: 7\n"
    text = preamble + question
    chunks = chunkQuestions(text)
    assert len(chunks) == 1
    assert chunks[0] == question
