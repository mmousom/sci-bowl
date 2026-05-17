"""Orchestrator Lambda entry point for the sci-bowl-pdf-etl pipeline."""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

_DEFAULT_BUCKET = "eshaan-sci-bowl-paper"
_DEFAULT_PREFIX = "raw-pdf-vault/middle-school/"


def listPdfKeys(s3Client: Any, bucket: str, prefix: str) -> list[str]:
    """Paginate S3 and return all .pdf keys under prefix.

    Uses ``list_objects_v2`` paginator to retrieve every key under
    ``bucket/prefix``, then filters to those whose suffix is ``.pdf``
    (case-insensitive).

    Args:
        s3Client: A boto3 S3 client.
        bucket: The S3 bucket name to list.
        prefix: The key prefix to list under.

    Returns:
        A list of S3 key strings ending in ``.pdf``.

    Raises:
        Exception: Re-raises any paginator exception after logging the prefix
            and error details.
    """
    keys: list[str] = []
    try:
        paginator = s3Client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if key.lower().endswith(".pdf"):
                    keys.append(key)
    except Exception as exc:
        logger.error("S3 listing failed for prefix=%s: %s", prefix, exc)
        raise

    return keys


def enqueueKeys(sqsClient: Any, queueUrl: str, keys: list[str]) -> int:
    """Send one SQS message per key. Returns count enqueued.

    Each message body is a JSON object ``{"s3_key": "<key>"}``.

    Args:
        sqsClient: A boto3 SQS client.
        queueUrl: The URL of the SQS queue to send messages to.
        keys: A list of S3 key strings to enqueue.

    Returns:
        The number of messages successfully sent.

    Raises:
        Exception: Re-raises any ``send_message`` exception after logging the
            affected key and error details.
    """
    count = 0
    for key in keys:
        try:
            sqsClient.send_message(
                QueueUrl=queueUrl,
                MessageBody=json.dumps({"s3_key": key}),
            )
            count += 1
        except Exception as exc:
            logger.error("SQS send_message failed for key=%s: %s", key, exc)
            raise

    return count


def handler(event: dict, context: object) -> dict:
    """Lambda entry point. Returns {"enqueued": int}.

    Discovers all ``.pdf`` keys under the configured S3 prefix and enqueues
    one SQS message per key.  Reads configuration from environment variables:

    - ``S3_BUCKET``: S3 bucket name (default ``eshaan-sci-bowl-paper``)
    - ``S3_PREFIX``: S3 key prefix (default ``raw-pdf-vault/middle-school/``)
    - ``SQS_QUEUE_URL``: SQS queue URL (required)

    Args:
        event: The Lambda invocation event (unused).
        context: The Lambda context object (unused).

    Returns:
        A dict ``{"enqueued": <count>}`` with the number of messages sent.

    Raises:
        ValueError: If ``SQS_QUEUE_URL`` environment variable is not set.
        Exception: Re-raises any S3 or SQS exception after logging.
    """
    bucket = os.environ.get("S3_BUCKET", _DEFAULT_BUCKET)
    prefix = os.environ.get("S3_PREFIX", _DEFAULT_PREFIX)
    queueUrl = os.environ.get("SQS_QUEUE_URL")

    if not queueUrl:
        raise ValueError("SQS_QUEUE_URL environment variable is required but not set")

    session = boto3.Session(profile_name="onasmmon") if os.environ.get("AWS_PROFILE") else boto3.Session()
    s3Client = session.client("s3")
    sqsClient = session.client("sqs")

    keys = listPdfKeys(s3Client, bucket, prefix)
    logger.info("Discovered %d PDF(s) under s3://%s/%s", len(keys), bucket, prefix)

    count = enqueueKeys(sqsClient, queueUrl, keys)
    logger.info("Enqueued %d message(s) to %s", count, queueUrl)

    return {"enqueued": count}
