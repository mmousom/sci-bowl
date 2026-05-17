"""Worker Lambda entry point — orchestrates the full PDF ETL pipeline per SQS record."""

import json
import logging
import os
from typing import Any

import boto3

from src.worker.chunker import chunkQuestions
from src.worker.dynamo_writer import writeQuestion
from src.worker.llm_client import extractFreeTextFields
from src.worker.pdf_extractor import downloadPdf, extractText
from src.worker.regex_parser import buildQuestionId, deriveSetRound, parseStructuralFields

logger = logging.getLogger(__name__)

_DEFAULT_BUCKET = "eshaan-sci-bowl-paper"
_DEFAULT_TABLE = "ScienceBowlQuestions"
_BEDROCK_REGION = "us-east-1"
# Use named profile locally; in Lambda the env var is absent and boto3 falls
# back to the execution role credentials automatically.
_AWS_PROFILE = os.environ.get("AWS_PROFILE")


def _buildItem(
    setRound: str,
    questionId: str,
    structural: dict[str, str],
    freeText: dict[str, Any],
    s3Key: str,
) -> dict[str, Any]:
    """Assemble the nine-field DynamoDB item from extracted data.

    Args:
        setRound: The ``Set_Round`` partition key value.
        questionId: The ``Question_Id`` sort key value.
        structural: Dict with ``category``, ``match_type``, ``answer_format``.
        freeText: Dict with ``question_stem``, ``answer_choices``, ``answer``.
        s3Key: The source S3 object key.

    Returns:
        A dict containing all nine required DynamoDB item attributes.
    """
    return {
        "Set_Round": setRound,
        "Question_Id": questionId,
        "Category": structural["category"],
        "MatchType": structural["match_type"],
        "question_stem": freeText["question_stem"],
        "answer_choices": freeText["answer_choices"],
        "answer": freeText["answer"],
        "answer_format": structural["answer_format"],
        "source_s3_key": s3Key,
    }


def _processChunk(
    index: int,
    chunk: str,
    setRound: str,
    s3Key: str,
    bedrockClient: Any,
    dynamoClient: Any,
    tableName: str,
) -> None:
    """Parse, enrich, and write a single question chunk to DynamoDB.

    Args:
        index: Zero-based chunk index (used for Bedrock error context).
        chunk: Raw question block text.
        setRound: Pre-derived ``Set_Round`` value for this PDF.
        s3Key: Source S3 key (for error context).
        bedrockClient: Boto3 Bedrock Runtime client.
        dynamoClient: Boto3 DynamoDB client.
        tableName: Target DynamoDB table name.
    """
    structural = parseStructuralFields(chunk)
    freeText = extractFreeTextFields(
        bedrockClient,
        chunk,
        structural["answer_format"],
        s3Key=s3Key,
    )
    questionId = buildQuestionId(structural["question_number"], structural["match_type"])
    item = _buildItem(setRound, questionId, structural, freeText, s3Key)
    writeQuestion(dynamoClient, tableName, item)
    logger.info("Written Set_Round=%s Question_Id=%s", setRound, questionId)


def processRecord(
    record: dict[str, Any],
    s3Client: Any,
    bedrockClient: Any,
    dynamoClient: Any,
    bucket: str,
    tableName: str,
) -> int:
    """Process one SQS record end-to-end through the ETL pipeline.

    Stages:
    1. Parse ``s3_key`` from the record body.
    2. Download the PDF from S3.
    3. Extract text from the PDF.
    4. Chunk the text into per-question blocks.
    5. For each chunk: parse structural fields, invoke Bedrock for free-text
       fields, assemble the item, and write to DynamoDB.

    Args:
        record: A single SQS record dict (from ``event["Records"]``).
        s3Client: Boto3 S3 client.
        bedrockClient: Boto3 Bedrock Runtime client.
        dynamoClient: Boto3 DynamoDB client.
        bucket: S3 bucket name containing the PDFs.
        tableName: DynamoDB table name to write items to.

    Returns:
        The number of DynamoDB items written.

    Raises:
        Exception: Re-raises any exception from any pipeline stage to trigger
            SQS retry.
    """
    body = json.loads(record["body"])
    s3Key: str = body["s3_key"]
    logger.info("processRecord: start s3Key=%s", s3Key)

    pdfBytes = downloadPdf(s3Client, bucket, s3Key)
    text = extractText(pdfBytes)
    chunks = chunkQuestions(text)
    logger.info("processRecord: extracted %d chunks from s3Key=%s", len(chunks), s3Key)

    setRound = deriveSetRound(s3Key)

    for index, chunk in enumerate(chunks):
        _processChunk(index, chunk, setRound, s3Key, bedrockClient, dynamoClient, tableName)

    count = len(chunks)
    if count == 0:
        logger.warning("processRecord: zero items written for s3Key=%s", s3Key)
    return count


def handler(event: dict[str, Any], context: object) -> None:
    """Lambda entry point — processes all SQS records in the event.

    Creates AWS clients using the ``onasmmon`` boto3 profile. Reads the S3
    bucket name from the ``S3_BUCKET`` environment variable (default:
    ``eshaan-sci-bowl-paper``) and the DynamoDB table name from
    ``DYNAMO_TABLE`` (default: ``ScienceBowlQuestions``).

    Iterates ``event["Records"]`` and calls ``processRecord`` for each.
    Any exception propagates out of the handler to trigger SQS retry.

    Args:
        event: The Lambda event dict containing ``Records``.
        context: The Lambda context object (unused).

    Raises:
        Exception: Re-raises any exception from ``processRecord`` to signal
            SQS that the message should be retried.
    """
    bucket = os.environ.get("S3_BUCKET", _DEFAULT_BUCKET)
    tableName = os.environ.get("DYNAMO_TABLE", _DEFAULT_TABLE)

    session = boto3.Session(profile_name=_AWS_PROFILE) if _AWS_PROFILE else boto3.Session()
    s3Client = session.client("s3")
    bedrockClient = session.client(
        service_name="bedrock-runtime",
        region_name=_BEDROCK_REGION,
    )
    dynamoClient = session.client("dynamodb")

    for record in event["Records"]:
        processRecord(record, s3Client, bedrockClient, dynamoClient, bucket, tableName)
