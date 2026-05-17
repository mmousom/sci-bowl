"""DynamoDB writer for Science Bowl question records."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_FIELDS: tuple[str, ...] = (
    "Set_Round",
    "Question_Id",
    "Category",
    "MatchType",
    "question_stem",
    "answer_choices",
    "answer",
    "answer_format",
    "source_s3_key",
)


def writeQuestion(dynamoClient: Any, tableName: str, item: dict) -> None:
    """Validate required fields and write item via unconditional put_item.

    Validates that all REQUIRED_FIELDS are present and non-None in item.
    Calls unconditional put_item (no ConditionExpression) for idempotency.
    For Short Answer items, answer_choices is written as [] (empty list).

    Args:
        dynamoClient: A boto3 DynamoDB client.
        tableName: The name of the DynamoDB table to write to.
        item: A dict containing the question attributes to write.

    Raises:
        ValueError: If any required field is missing or None in item.
        Exception: Re-raises any exception from put_item after logging.
    """
    _validateRequiredFields(item)

    setRound = item["Set_Round"]
    questionId = item["Question_Id"]

    try:
        dynamoClient.put_item(TableName=tableName, Item=_marshalItem(item))
    except Exception as exc:
        logger.error(
            "DynamoDB put_item failed for Set_Round=%s Question_Id=%s: %s",
            setRound,
            questionId,
            exc,
        )
        raise


def _validateRequiredFields(item: dict) -> None:
    """Check all REQUIRED_FIELDS are present and non-None.

    Args:
        item: The item dict to validate.

    Raises:
        ValueError: On the first missing or None field found.
    """
    setRound = item.get("Set_Round")
    questionId = item.get("Question_Id")

    for field in REQUIRED_FIELDS:
        if field not in item or item[field] is None:
            logger.error(
                "Missing required field '%s' for Set_Round=%s Question_Id=%s",
                field,
                setRound,
                questionId,
            )
            raise ValueError(
                f"Missing required field '{field}' "
                f"(Set_Round={setRound}, Question_Id={questionId})"
            )


def _marshalItem(item: dict) -> dict:
    """Convert a plain Python dict to DynamoDB attribute-value format.

    Args:
        item: Plain Python dict with question attributes.

    Returns:
        Dict in DynamoDB {AttributeName: {TypeCode: value}} format.
    """
    marshalled: dict = {}
    for key, value in item.items():
        marshalled[key] = _marshalValue(value)
    return marshalled


def _marshalValue(value: Any) -> dict:
    """Convert a single Python value to a DynamoDB typed attribute dict.

    Args:
        value: A Python str, list, or bool value.

    Returns:
        DynamoDB typed attribute dict, e.g. {"S": "foo"} or {"L": [...]}.
    """
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, list):
        return {"L": [_marshalValue(v) for v in value]}
    return {"S": str(value)}
