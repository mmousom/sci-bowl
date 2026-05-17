"""Integration smoke tests for the sci-bowl-pdf-etl pipeline.

Run manually (not part of the default pytest suite):
    AWS_PROFILE=onasmmon python tests/integration/smoke_test.py

Tests:
    1. Orchestrator discovery  — invoke Orchestrator Lambda, assert enqueued > 0
    2. Worker end-to-end       — send a known S3 key to SQS, wait for Worker,
                                 assert DynamoDB item exists with all nine fields
    3. DLQ routing             — send a malformed message three times,
                                 assert message appears in DLQ
"""

import json
import sys
import time
from typing import Any

import boto3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AWS_PROFILE = "onasmmon"
AWS_REGION = "us-east-1"

ORCHESTRATOR_FUNCTION = "sci-bowl-orchestrator"
WORKER_FUNCTION = "sci-bowl-worker"
SQS_QUEUE_NAME = "sci-bowl-pdf-processing"
DLQ_NAME = "sci-bowl-pdf-processing-dlq"
DYNAMO_TABLE = "ScienceBowlQuestions"

# A known PDF that exists in the S3 bucket and produces at least one question.
# Adjust this key if the bucket contents change.
KNOWN_S3_KEY = "raw-pdf-vault/middle-school/Sample-Set-13/2019-NSB-MSR-Round-10A.pdf"

# Expected DynamoDB keys for the first question in the known PDF.
EXPECTED_SET_ROUND = "Sample-Set-13_2019-NSB-MSR-Round-10A"
EXPECTED_QUESTION_ID = "Q_01_TOSS-UP"

# All nine required DynamoDB item attributes (matches dynamo_writer.REQUIRED_FIELDS).
REQUIRED_DYNAMO_FIELDS = (
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

# How long to wait for the Worker Lambda to process the SQS message (seconds).
WORKER_POLL_TIMEOUT_SECONDS = 120
WORKER_POLL_INTERVAL_SECONDS = 5

# How long to wait for the DLQ to receive the malformed message (seconds).
DLQ_POLL_TIMEOUT_SECONDS = 300
DLQ_POLL_INTERVAL_SECONDS = 10

# Number of times to send the malformed message to trigger DLQ routing.
DLQ_SEND_COUNT = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def buildSession() -> boto3.Session:
    """Return a boto3 Session using the onasmmon profile."""
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def getQueueUrl(sqsClient: Any, queueName: str) -> str:
    """Resolve a queue name to its URL.

    Args:
        sqsClient: A boto3 SQS client.
        queueName: The short name of the SQS queue.

    Returns:
        The full queue URL string.
    """
    response = sqsClient.get_queue_url(QueueName=queueName)
    return response["QueueUrl"]


def getDlqMessageCount(sqsClient: Any, dlqUrl: str) -> int:
    """Return the approximate number of messages visible in the DLQ.

    Args:
        sqsClient: A boto3 SQS client.
        dlqUrl: The URL of the dead-letter queue.

    Returns:
        Approximate number of visible messages.
    """
    response = sqsClient.get_queue_attributes(
        QueueUrl=dlqUrl,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    return int(response["Attributes"]["ApproximateNumberOfMessages"])


def getDynamoItem(dynamoClient: Any, setRound: str, questionId: str) -> dict | None:
    """Fetch a single item from DynamoDB by primary key.

    Args:
        dynamoClient: A boto3 DynamoDB client.
        setRound: The Set_Round partition key value.
        questionId: The Question_Id sort key value.

    Returns:
        The raw DynamoDB item dict, or None if not found.
    """
    response = dynamoClient.get_item(
        TableName=DYNAMO_TABLE,
        Key={
            "Set_Round": {"S": setRound},
            "Question_Id": {"S": questionId},
        },
    )
    return response.get("Item")


def pollForDynamoItem(
    dynamoClient: Any,
    setRound: str,
    questionId: str,
    timeoutSeconds: int,
    intervalSeconds: int,
) -> dict | None:
    """Poll DynamoDB until the expected item appears or timeout is reached.

    Args:
        dynamoClient: A boto3 DynamoDB client.
        setRound: The Set_Round partition key value.
        questionId: The Question_Id sort key value.
        timeoutSeconds: Maximum seconds to wait.
        intervalSeconds: Seconds between each poll attempt.

    Returns:
        The DynamoDB item dict if found, or None on timeout.
    """
    deadline = time.monotonic() + timeoutSeconds
    while time.monotonic() < deadline:
        item = getDynamoItem(dynamoClient, setRound, questionId)
        if item is not None:
            return item
        print(
            f"  Waiting for DynamoDB item "
            f"Set_Round={setRound} Question_Id={questionId} …"
        )
        time.sleep(intervalSeconds)
    return None


def pollForDlqMessage(
    sqsClient: Any,
    dlqUrl: str,
    timeoutSeconds: int,
    intervalSeconds: int,
) -> bool:
    """Poll the DLQ until at least one message is visible or timeout is reached.

    Args:
        sqsClient: A boto3 SQS client.
        dlqUrl: The URL of the dead-letter queue.
        timeoutSeconds: Maximum seconds to wait.
        intervalSeconds: Seconds between each poll attempt.

    Returns:
        True if at least one message appeared in the DLQ, False on timeout.
    """
    deadline = time.monotonic() + timeoutSeconds
    while time.monotonic() < deadline:
        count = getDlqMessageCount(sqsClient, dlqUrl)
        if count > 0:
            return True
        print(f"  Waiting for DLQ message (current count={count}) …")
        time.sleep(intervalSeconds)
    return False


# ---------------------------------------------------------------------------
# Test 1 — Orchestrator discovery
# ---------------------------------------------------------------------------


def testOrchestratorDiscovery(lambdaClient: Any) -> bool:
    """Invoke the Orchestrator Lambda and assert it enqueues at least one PDF.

    Validates: Requirements 1.1, 1.4

    Args:
        lambdaClient: A boto3 Lambda client.

    Returns:
        True on pass, False on failure.
    """
    print("\n[Test 1] Orchestrator discovery …")
    try:
        response = lambdaClient.invoke(
            FunctionName=ORCHESTRATOR_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps({}),
        )
        rawPayload = response["Payload"].read()
        payload = json.loads(rawPayload)

        if response.get("FunctionError"):
            print(f"  FAIL — Lambda returned FunctionError: {payload}")
            return False

        enqueued = payload.get("enqueued", 0)
        if enqueued > 0:
            print(f"  PASS — enqueued={enqueued}")
            return True

        print(f"  FAIL — enqueued={enqueued} (expected > 0)")
        return False

    except Exception as exc:
        print(f"  FAIL — unexpected exception: {exc}")
        return False


# ---------------------------------------------------------------------------
# Test 2 — Worker end-to-end
# ---------------------------------------------------------------------------


def testWorkerEndToEnd(sqsClient: Any, dynamoClient: Any) -> bool:
    """Send a known S3 key to SQS and assert the Worker writes the DynamoDB item.

    Validates: Requirements 2.1, 2.2, 8.1, 10.4

    Args:
        sqsClient: A boto3 SQS client.
        dynamoClient: A boto3 DynamoDB client.

    Returns:
        True on pass, False on failure.
    """
    print("\n[Test 2] Worker end-to-end …")
    try:
        queueUrl = getQueueUrl(sqsClient, SQS_QUEUE_NAME)
        messageBody = json.dumps({"s3_key": KNOWN_S3_KEY})

        sqsClient.send_message(QueueUrl=queueUrl, MessageBody=messageBody)
        print(f"  Sent s3_key={KNOWN_S3_KEY} to {SQS_QUEUE_NAME}")

        item = pollForDynamoItem(
            dynamoClient,
            EXPECTED_SET_ROUND,
            EXPECTED_QUESTION_ID,
            WORKER_POLL_TIMEOUT_SECONDS,
            WORKER_POLL_INTERVAL_SECONDS,
        )

        if item is None:
            print(
                f"  FAIL — DynamoDB item not found after "
                f"{WORKER_POLL_TIMEOUT_SECONDS}s "
                f"(Set_Round={EXPECTED_SET_ROUND}, "
                f"Question_Id={EXPECTED_QUESTION_ID})"
            )
            return False

        missingFields = [f for f in REQUIRED_DYNAMO_FIELDS if f not in item]
        if missingFields:
            print(f"  FAIL — item missing required fields: {missingFields}")
            return False

        print(
            f"  PASS — item found with all {len(REQUIRED_DYNAMO_FIELDS)} "
            f"required fields"
        )
        return True

    except Exception as exc:
        print(f"  FAIL — unexpected exception: {exc}")
        return False


# ---------------------------------------------------------------------------
# Test 3 — DLQ routing
# ---------------------------------------------------------------------------


def testDlqRouting(sqsClient: Any) -> bool:
    """Send a malformed message three times and assert it appears in the DLQ.

    The Worker Lambda will fail to process an empty-body message on each
    delivery attempt. After maxReceiveCount=3 failures SQS routes the message
    to the DLQ.

    Validates: Requirements 2.1, 2.2, 2.3

    Args:
        sqsClient: A boto3 SQS client.

    Returns:
        True on pass, False on failure.
    """
    print("\n[Test 3] DLQ routing …")
    try:
        queueUrl = getQueueUrl(sqsClient, SQS_QUEUE_NAME)
        dlqUrl = getQueueUrl(sqsClient, DLQ_NAME)

        # Record the DLQ depth before sending so we detect a net increase.
        initialDlqCount = getDlqMessageCount(sqsClient, dlqUrl)
        print(f"  DLQ message count before test: {initialDlqCount}")

        # Send a single malformed message (empty body).  SQS will redeliver it
        # up to maxReceiveCount=3 times before routing it to the DLQ.
        for i in range(DLQ_SEND_COUNT):
            sqsClient.send_message(QueueUrl=queueUrl, MessageBody="")
            print(f"  Sent malformed message {i + 1}/{DLQ_SEND_COUNT}")

        appeared = pollForDlqMessage(
            sqsClient,
            dlqUrl,
            DLQ_POLL_TIMEOUT_SECONDS,
            DLQ_POLL_INTERVAL_SECONDS,
        )

        if not appeared:
            print(
                f"  FAIL — no message appeared in DLQ after "
                f"{DLQ_POLL_TIMEOUT_SECONDS}s"
            )
            return False

        finalDlqCount = getDlqMessageCount(sqsClient, dlqUrl)
        if finalDlqCount > initialDlqCount:
            print(
                f"  PASS — DLQ message count increased from "
                f"{initialDlqCount} to {finalDlqCount}"
            )
            return True

        print(
            f"  FAIL — DLQ count did not increase "
            f"(before={initialDlqCount}, after={finalDlqCount})"
        )
        return False

    except Exception as exc:
        print(f"  FAIL — unexpected exception: {exc}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all smoke tests and exit with a non-zero code on any failure."""
    session = buildSession()
    lambdaClient = session.client("lambda")
    sqsClient = session.client("sqs")
    dynamoClient = session.client("dynamodb")

    results: dict[str, bool] = {
        "Test 1 — Orchestrator discovery": testOrchestratorDiscovery(lambdaClient),
        "Test 2 — Worker end-to-end": testWorkerEndToEnd(sqsClient, dynamoClient),
        "Test 3 — DLQ routing": testDlqRouting(sqsClient),
    }

    print("\n" + "=" * 60)
    print("Smoke test summary")
    print("=" * 60)
    allPassed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {name}")
        if not passed:
            allPassed = False

    print("=" * 60)
    if allPassed:
        print("All tests passed.")
        sys.exit(0)
    else:
        print("One or more tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
