"""Unit and property-based tests for src/worker/dynamo_writer.py."""

import logging
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.worker.dynamo_writer import REQUIRED_FIELDS, writeQuestion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TABLE_NAME = "ScienceBowlQuestions"


def _makeCompleteItem(**overrides) -> dict:
    """Return a complete item dict with all nine required fields."""
    base = {
        "Set_Round": "Sample-Set-13_Round-10A",
        "Question_Id": "Q_01_TOSS-UP",
        "Category": "Life Science",
        "MatchType": "TOSS-UP",
        "question_stem": "What is photosynthesis?",
        "answer_choices": [],
        "answer": "The process by which plants make food",
        "answer_format": "Short Answer",
        "source_s3_key": "raw-pdf-vault/middle-school/Sample-Set-13/Round-10A.pdf",
    }
    base.update(overrides)
    return base


def _makeDynamoClient() -> MagicMock:
    """Return a mock DynamoDB client with a no-op put_item."""
    client = MagicMock()
    client.put_item.return_value = {}
    return client


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 13: DynamoDB Item Completeness
@given(
    st.fixed_dictionaries(
        {field: st.text(min_size=1) for field in REQUIRED_FIELDS}
    )
)
def test_writeQuestionCallsPutItemCorrectly(item: dict) -> None:
    """Property 13: DynamoDB Item Completeness — Validates: Requirements 8.1, 8.3, 10.4

    For any complete set of extracted fields, writeQuestion SHALL call put_item
    with an item containing exactly the nine required attributes and no
    ConditionExpression.
    """
    # answer_choices is a list in the real schema; override the text value
    item["answer_choices"] = []
    dynamoClient = _makeDynamoClient()

    writeQuestion(dynamoClient, TABLE_NAME, item)

    dynamoClient.put_item.assert_called_once()
    callKwargs = dynamoClient.put_item.call_args[1]

    # Must not include ConditionExpression
    assert "ConditionExpression" not in callKwargs

    # The marshalled Item must contain all nine required attributes
    marshalledItem = callKwargs["Item"]
    for field in REQUIRED_FIELDS:
        assert field in marshalledItem, f"Missing field in put_item Item: {field}"


# Feature: sci-bowl-pdf-etl, Property 15: Short Answer answer_choices Written as Empty List
@given(
    st.fixed_dictionaries(
        {
            field: st.text(min_size=1)
            for field in REQUIRED_FIELDS
            if field not in ("answer_choices", "answer_format")
        }
    )
)
def test_writeQuestionSaAnswerChoicesEmpty(baseItem: dict) -> None:
    """Property 15: Short Answer answer_choices Written as Empty List — Validates: Requirements 8.6

    For any item where answer_format = "Short Answer", writeQuestion SHALL pass
    answer_choices = [] in the put_item call.
    """
    item = dict(baseItem)
    item["answer_format"] = "Short Answer"
    item["answer_choices"] = []

    dynamoClient = _makeDynamoClient()
    writeQuestion(dynamoClient, TABLE_NAME, item)

    dynamoClient.put_item.assert_called_once()
    marshalledItem = dynamoClient.put_item.call_args[1]["Item"]

    # answer_choices must be marshalled as an empty DynamoDB List
    assert marshalledItem["answer_choices"] == {"L": []}


# Feature: sci-bowl-pdf-etl, Property 16: Missing Required Field Prevents Write
@given(
    st.fixed_dictionaries(
        {field: st.text(min_size=1) for field in REQUIRED_FIELDS}
    ),
    st.sampled_from(list(REQUIRED_FIELDS)),
)
def test_writeQuestionRaisesOnMissingField(item: dict, missingField: str) -> None:
    """Property 16: Missing Required Field Prevents Write — Validates: Requirements 8.7

    For any item dict where one of the nine required fields is None, writeQuestion
    SHALL raise a ValueError without calling put_item.
    """
    item["answer_choices"] = []
    item[missingField] = None  # force the field to be missing/None

    dynamoClient = _makeDynamoClient()

    with pytest.raises(ValueError):
        writeQuestion(dynamoClient, TABLE_NAME, item)

    dynamoClient.put_item.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestWriteQuestion:
    """Unit tests for writeQuestion."""

    def test_completeItemWritesToDynamo(self) -> None:
        """A complete item is written via put_item (Req 8.1)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem()

        writeQuestion(dynamoClient, TABLE_NAME, item)

        dynamoClient.put_item.assert_called_once()

    def test_putItemReceivesCorrectTableName(self) -> None:
        """put_item is called with the correct TableName (Req 8.1)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem()

        writeQuestion(dynamoClient, TABLE_NAME, item)

        callKwargs = dynamoClient.put_item.call_args[1]
        assert callKwargs["TableName"] == TABLE_NAME

    def test_noConditionExpression(self) -> None:
        """put_item is called without a ConditionExpression (Req 8.3)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem()

        writeQuestion(dynamoClient, TABLE_NAME, item)

        callKwargs = dynamoClient.put_item.call_args[1]
        assert "ConditionExpression" not in callKwargs

    def test_missingFieldRaisesValueError(self) -> None:
        """A missing required field raises ValueError before any write (Req 8.7)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem()
        del item["Category"]

        with pytest.raises(ValueError, match="Category"):
            writeQuestion(dynamoClient, TABLE_NAME, item)

        dynamoClient.put_item.assert_not_called()

    def test_noneFieldRaisesValueError(self) -> None:
        """A None required field raises ValueError before any write (Req 8.7)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem(question_stem=None)

        with pytest.raises(ValueError, match="question_stem"):
            writeQuestion(dynamoClient, TABLE_NAME, item)

        dynamoClient.put_item.assert_not_called()

    def test_shortAnswerWritesEmptyAnswerChoices(self) -> None:
        """Short Answer items write answer_choices as an empty list (Req 8.6)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem(answer_format="Short Answer", answer_choices=[])

        writeQuestion(dynamoClient, TABLE_NAME, item)

        marshalledItem = dynamoClient.put_item.call_args[1]["Item"]
        assert marshalledItem["answer_choices"] == {"L": []}

    def test_putItemFailurePropagates(self) -> None:
        """Exceptions from put_item are re-raised (Req 8.5)."""
        dynamoClient = _makeDynamoClient()
        dynamoClient.put_item.side_effect = RuntimeError("DynamoDB unavailable")
        item = _makeCompleteItem()

        with pytest.raises(RuntimeError, match="DynamoDB unavailable"):
            writeQuestion(dynamoClient, TABLE_NAME, item)

    def test_putItemFailureLogsSetRoundAndQuestionId(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """put_item failure is logged with Set_Round and Question_Id (Req 8.5)."""
        dynamoClient = _makeDynamoClient()
        dynamoClient.put_item.side_effect = RuntimeError("timeout")
        item = _makeCompleteItem(
            Set_Round="Sample-Set-13_Round-10A",
            Question_Id="Q_01_TOSS-UP",
        )

        with caplog.at_level(logging.ERROR, logger="src.worker.dynamo_writer"):
            with pytest.raises(RuntimeError):
                writeQuestion(dynamoClient, TABLE_NAME, item)

        logMessages = " ".join(r.message for r in caplog.records)
        assert "Sample-Set-13_Round-10A" in logMessages
        assert "Q_01_TOSS-UP" in logMessages

    def test_allNineAttributesPresentInPutItem(self) -> None:
        """All nine required attributes appear in the marshalled put_item Item (Req 8.1)."""
        dynamoClient = _makeDynamoClient()
        item = _makeCompleteItem()

        writeQuestion(dynamoClient, TABLE_NAME, item)

        marshalledItem = dynamoClient.put_item.call_args[1]["Item"]
        for field in REQUIRED_FIELDS:
            assert field in marshalledItem, f"Missing field in put_item Item: {field}"
