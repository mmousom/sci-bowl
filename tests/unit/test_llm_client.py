"""Unit and property-based tests for src/worker/llm_client.py."""

import json
import logging
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from hypothesis import given
from hypothesis import strategies as st

from src.worker.llm_client import buildPrompt, extractFreeTextFields, parseBedrockResponse


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 11: Multiple Choice Prompt Instruction
@given(st.text())
def test_buildPromptMcContainsListInstruction(chunk: str) -> None:
    """Property 11: Multiple Choice Prompt Instruction — Validates: Requirements 7.3

    For any chunk with answer_format = "Multiple Choice", buildPrompt SHALL
    produce a prompt string that instructs the LLM to return answer_choices
    as an ordered list of 2 to 26 non-empty strings.
    """
    prompt = buildPrompt(chunk, "Multiple Choice")

    # The prompt must reference the 2-to-26 range for answer_choices
    assert "2" in prompt
    assert "26" in prompt
    # Must instruct an ordered list / array of non-empty strings
    assert "answer_choices" in prompt
    assert "non-empty" in prompt.lower() or "non-empty" in prompt


# Feature: sci-bowl-pdf-etl, Property 12: Short Answer Prompt Instruction
@given(st.text())
def test_buildPromptSaContainsEmptyListInstruction(chunk: str) -> None:
    """Property 12: Short Answer Prompt Instruction — Validates: Requirements 7.4

    For any chunk with answer_format = "Short Answer", buildPrompt SHALL
    produce a prompt string that instructs the LLM to return answer_choices
    as an empty list.
    """
    prompt = buildPrompt(chunk, "Short Answer")

    # The prompt must reference answer_choices and instruct an empty list
    assert "answer_choices" in prompt
    assert "[]" in prompt


# Feature: sci-bowl-pdf-etl, Property 10: LLM Response Validation
@given(
    st.fixed_dictionaries(
        {
            "question_stem": st.one_of(st.none(), st.just("")),
            "answer_choices": st.just(["choice A", "choice B"]),
            "answer": st.just("choice A"),
        }
    )
    | st.fixed_dictionaries(
        {
            "question_stem": st.just("What is 2+2?"),
            "answer_choices": st.one_of(st.none(), st.just("")),
            "answer": st.just("4"),
        }
    )
    | st.fixed_dictionaries(
        {
            "question_stem": st.just("What is 2+2?"),
            "answer_choices": st.just(["choice A", "choice B"]),
            "answer": st.one_of(st.none(), st.just("")),
        }
    )
)
def test_parseBedrockResponseRejectsIncomplete(incompleteData: dict) -> None:
    """Property 10: LLM Response Validation — Validates: Requirements 7.1, 7.7

    For any Bedrock response JSON that is missing one or more of
    question_stem, answer_choices, or answer (or contains null/empty values),
    parseBedrockResponse SHALL raise a ValueError.
    """
    responseBody = json.dumps(incompleteData)
    with pytest.raises(ValueError):
        parseBedrockResponse(responseBody)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Unit tests for buildPrompt."""

    def test_mcPromptContainsChunk(self) -> None:
        """The chunk text appears verbatim in the MC prompt (Req 7.3)."""
        chunk = "TOSS-UP\n1) Life Science – Multiple Choice\nW) A\nX) B\nANSWER: W"
        prompt = buildPrompt(chunk, "Multiple Choice")
        assert chunk in prompt

    def test_saPromptContainsChunk(self) -> None:
        """The chunk text appears verbatim in the SA prompt (Req 7.4)."""
        chunk = "BONUS\n2) Math – Short Answer\nANSWER: 42"
        prompt = buildPrompt(chunk, "Short Answer")
        assert chunk in prompt

    def test_mcPromptInstructsOrderedList(self) -> None:
        """MC prompt instructs an ordered list of 2–26 non-empty strings (Req 7.3)."""
        prompt = buildPrompt("some chunk", "Multiple Choice")
        assert "2" in prompt
        assert "26" in prompt
        assert "answer_choices" in prompt

    def test_saPromptInstructsEmptyList(self) -> None:
        """SA prompt instructs answer_choices as empty list [] (Req 7.4)."""
        prompt = buildPrompt("some chunk", "Short Answer")
        assert "[]" in prompt
        assert "answer_choices" in prompt

    def test_mcAndSaPromptsAreDifferent(self) -> None:
        """MC and SA prompts differ in their answer_choices instruction."""
        chunk = "shared chunk text"
        mcPrompt = buildPrompt(chunk, "Multiple Choice")
        saPrompt = buildPrompt(chunk, "Short Answer")
        assert mcPrompt != saPrompt


class TestParseBedrockResponse:
    """Unit tests for parseBedrockResponse."""

    def _validBody(self) -> str:
        return json.dumps(
            {
                "question_stem": "What is the powerhouse of the cell?",
                "answer_choices": ["W) Nucleus", "X) Mitochondria", "Y) Ribosome", "Z) Vacuole"],
                "answer": "X) Mitochondria",
            }
        )

    def test_validResponseReturnsDict(self) -> None:
        """A complete, valid response is parsed and returned (Req 7.1)."""
        result = parseBedrockResponse(self._validBody())
        assert result["question_stem"] == "What is the powerhouse of the cell?"
        assert result["answer"] == "X) Mitochondria"
        assert len(result["answer_choices"]) == 4

    def test_missingQuestionStemRaisesValueError(self) -> None:
        """Missing question_stem raises ValueError (Req 7.7)."""
        body = json.dumps({"answer_choices": ["W) A"], "answer": "W) A"})
        with pytest.raises(ValueError, match="question_stem"):
            parseBedrockResponse(body)

    def test_missingAnswerChoicesRaisesValueError(self) -> None:
        """Missing answer_choices raises ValueError (Req 7.7)."""
        body = json.dumps({"question_stem": "Q?", "answer": "A"})
        with pytest.raises(ValueError, match="answer_choices"):
            parseBedrockResponse(body)

    def test_missingAnswerRaisesValueError(self) -> None:
        """Missing answer raises ValueError (Req 7.7)."""
        body = json.dumps({"question_stem": "Q?", "answer_choices": ["W) A"]})
        with pytest.raises(ValueError, match="answer"):
            parseBedrockResponse(body)

    def test_nullQuestionStemRaisesValueError(self) -> None:
        """Null question_stem raises ValueError (Req 7.7)."""
        body = json.dumps({"question_stem": None, "answer_choices": ["W) A"], "answer": "W) A"})
        with pytest.raises(ValueError):
            parseBedrockResponse(body)

    def test_emptyAnswerRaisesValueError(self) -> None:
        """Empty string answer raises ValueError (Req 7.7)."""
        body = json.dumps({"question_stem": "Q?", "answer_choices": ["W) A"], "answer": ""})
        with pytest.raises(ValueError):
            parseBedrockResponse(body)

    def test_invalidJsonRaisesValueError(self) -> None:
        """Non-JSON response body raises ValueError (Req 7.1)."""
        with pytest.raises(ValueError):
            parseBedrockResponse("not valid json {{{")

    def test_missingFieldIsLogged(self, caplog: pytest.LogCaptureFixture) -> None:
        """A missing field is logged before raising (Req 7.7)."""
        body = json.dumps({"answer_choices": ["W) A"], "answer": "W) A"})
        with caplog.at_level(logging.ERROR, logger="src.worker.llm_client"):
            with pytest.raises(ValueError):
                parseBedrockResponse(body)
        assert any("question_stem" in record.message for record in caplog.records)


class TestExtractFreeTextFields:
    """Unit tests for extractFreeTextFields."""

    def _makeBedrockClient(self, responseText: str) -> MagicMock:
        """Build a mock Bedrock client that returns responseText."""
        mockClient = MagicMock()
        mockClient.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": responseText}]
                }
            }
        }
        return mockClient

    def _validResponseText(self) -> str:
        return json.dumps(
            {
                "question_stem": "What is 2 + 2?",
                "answer_choices": [],
                "answer": "4",
            }
        )

    def test_validMcResponseReturnsFields(self) -> None:
        """A valid MC Bedrock response returns all three fields (Req 7.1)."""
        responseText = json.dumps(
            {
                "question_stem": "Which organelle produces energy?",
                "answer_choices": ["W) Nucleus", "X) Mitochondria", "Y) Ribosome", "Z) Vacuole"],
                "answer": "X) Mitochondria",
            }
        )
        mockClient = self._makeBedrockClient(responseText)
        result = extractFreeTextFields(mockClient, "chunk text", "Multiple Choice")

        assert result["question_stem"] == "Which organelle produces energy?"
        assert result["answer"] == "X) Mitochondria"
        assert len(result["answer_choices"]) == 4

    def test_validSaResponseReturnsFields(self) -> None:
        """A valid SA Bedrock response returns all three fields (Req 7.1)."""
        mockClient = self._makeBedrockClient(self._validResponseText())
        result = extractFreeTextFields(mockClient, "chunk text", "Short Answer")

        assert result["question_stem"] == "What is 2 + 2?"
        assert result["answer_choices"] == []
        assert result["answer"] == "4"

    def test_throttlingExceptionIsReRaised(self) -> None:
        """ThrottlingException is re-raised directly for SQS backoff (Req 7.5)."""
        mockClient = MagicMock()
        throttlingError = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "converse",
        )
        mockClient.converse.side_effect = throttlingError

        with pytest.raises(ClientError) as excInfo:
            extractFreeTextFields(mockClient, "chunk", "Short Answer", s3Key="test/key.pdf")

        assert excInfo.value.response["Error"]["Code"] == "ThrottlingException"

    def test_genericExceptionIsReRaised(self) -> None:
        """Non-throttling exceptions are logged and re-raised (Req 7.6)."""
        mockClient = MagicMock()
        mockClient.converse.side_effect = RuntimeError("connection reset")

        with pytest.raises(RuntimeError, match="connection reset"):
            extractFreeTextFields(mockClient, "chunk", "Short Answer", s3Key="test/key.pdf")

    def test_genericExceptionIsLogged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Non-throttling exceptions are logged with s3Key context (Req 7.6)."""
        mockClient = MagicMock()
        mockClient.converse.side_effect = RuntimeError("network error")

        with caplog.at_level(logging.ERROR, logger="src.worker.llm_client"):
            with pytest.raises(RuntimeError):
                extractFreeTextFields(mockClient, "chunk", "Short Answer", s3Key="my/key.pdf")

        assert any("my/key.pdf" in record.message for record in caplog.records)

    def test_missingFieldInResponseRaisesValueError(self) -> None:
        """A Bedrock response missing a required field raises ValueError (Req 7.7)."""
        incompleteResponse = json.dumps({"question_stem": "Q?", "answer": "A"})
        mockClient = self._makeBedrockClient(incompleteResponse)

        with pytest.raises(ValueError, match="answer_choices"):
            extractFreeTextFields(mockClient, "chunk", "Short Answer")
