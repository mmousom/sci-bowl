"""Unit and property-based tests for src/orchestrator/handler.py."""

import json
import logging
from unittest.mock import MagicMock, call

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.orchestrator.handler import enqueueKeys, listPdfKeys


# ---------------------------------------------------------------------------
# Property 1: S3 Pagination Completeness
# Feature: sci-bowl-pdf-etl, Property 1: S3 Pagination Completeness
# Validates: Requirements 1.1, 1.2
# ---------------------------------------------------------------------------


def _buildPaginator(pages: list[list[str]]) -> MagicMock:
    """Return a mock S3 paginator that yields the given pages of keys."""
    mockPages = []
    for pageKeys in pages:
        contents = [{"Key": k} for k in pageKeys]
        mockPages.append({"Contents": contents} if contents else {})

    mockPaginator = MagicMock()
    mockPaginator.paginate.return_value = iter(mockPages)
    return mockPaginator


def _splitIntoPages(keys: list[str], pageSize: int) -> list[list[str]]:
    """Partition a flat list of keys into pages of at most pageSize."""
    if not keys:
        return [[]]
    return [keys[i : i + pageSize] for i in range(0, len(keys), pageSize)]


# Feature: sci-bowl-pdf-etl, Property 1: S3 Pagination Completeness
@given(
    st.lists(st.text(min_size=1, max_size=80, alphabet=st.characters(blacklist_categories=("Cs",)))),
    st.integers(min_value=1, max_value=5),
)
@settings(max_examples=200)
def test_listPdfKeysReturnsAllPdfKeys(keys: list[str], pageSize: int) -> None:
    """Property 1: S3 Pagination Completeness — Validates: Requirements 1.1, 1.2

    For any collection of S3 keys distributed across any number of paginator
    pages, listPdfKeys SHALL return exactly the subset of those keys whose
    suffix is .pdf (case-insensitive), with no keys omitted and no non-pdf
    keys included.
    """
    pages = _splitIntoPages(keys, pageSize)
    mockPaginator = _buildPaginator(pages)

    mockS3 = MagicMock()
    mockS3.get_paginator.return_value = mockPaginator

    result = listPdfKeys(mockS3, "test-bucket", "test-prefix/")

    expectedPdfKeys = [k for k in keys if k.lower().endswith(".pdf")]
    assert sorted(result) == sorted(expectedPdfKeys), (
        f"Expected {sorted(expectedPdfKeys)}, got {sorted(result)}"
    )


# ---------------------------------------------------------------------------
# Property 2: Orchestrator Enqueue Count
# Feature: sci-bowl-pdf-etl, Property 2: Orchestrator Enqueue Count
# Validates: Requirements 1.3, 1.4
# ---------------------------------------------------------------------------


# Feature: sci-bowl-pdf-etl, Property 2: Orchestrator Enqueue Count
@given(st.lists(st.from_regex(r"[\w/]+\.pdf", fullmatch=True)))
@settings(max_examples=200)
def test_enqueueKeysCallsOncePerKey(keys: list[str]) -> None:
    """Property 2: Orchestrator Enqueue Count — Validates: Requirements 1.3, 1.4

    For any list of N pdf keys, enqueueKeys SHALL call send_message exactly N
    times and return N, with each call's message body containing the
    corresponding s3_key.
    """
    mockSqs = MagicMock()

    result = enqueueKeys(mockSqs, "https://sqs.example.com/queue", keys)

    assert mockSqs.send_message.call_count == len(keys), (
        f"Expected {len(keys)} send_message calls, got {mockSqs.send_message.call_count}"
    )
    assert result == len(keys), (
        f"Expected return value {len(keys)}, got {result}"
    )

    for key in keys:
        expectedBody = json.dumps({"s3_key": key})
        mockSqs.send_message.assert_any_call(
            QueueUrl="https://sqs.example.com/queue",
            MessageBody=expectedBody,
        )


# ---------------------------------------------------------------------------
# Unit tests for src/orchestrator/handler.py
# Validates: Requirements 1.1–1.6, 10.5
# ---------------------------------------------------------------------------


class TestListPdfKeys:
    """Unit tests for listPdfKeys."""

    def _makeS3Client(self, pages: list[list[str]]) -> MagicMock:
        """Build a mock S3 client whose paginator returns the given pages."""
        mockPaginator = _buildPaginator(pages)
        mockS3 = MagicMock()
        mockS3.get_paginator.return_value = mockPaginator
        return mockS3

    def test_paginationAcrossMultiplePages(self) -> None:
        """Keys spread across multiple pages are all returned (Req 1.1)."""
        page1 = ["raw-pdf-vault/middle-school/Set-1/round1.pdf", "raw-pdf-vault/middle-school/Set-1/round2.pdf"]
        page2 = ["raw-pdf-vault/middle-school/Set-2/round3.pdf"]
        mockS3 = self._makeS3Client([page1, page2])

        result = listPdfKeys(mockS3, "bucket", "raw-pdf-vault/middle-school/")

        assert sorted(result) == sorted(page1 + page2)

    def test_filtersPdfKeysOnly(self) -> None:
        """Only keys ending in .pdf are returned; others are excluded (Req 1.2)."""
        keys = [
            "raw-pdf-vault/middle-school/Set-1/round1.pdf",
            "raw-pdf-vault/middle-school/Set-1/readme.txt",
            "raw-pdf-vault/middle-school/Set-1/notes.docx",
            "raw-pdf-vault/middle-school/Set-1/round2.pdf",
        ]
        mockS3 = self._makeS3Client([keys])

        result = listPdfKeys(mockS3, "bucket", "raw-pdf-vault/middle-school/")

        assert sorted(result) == sorted([
            "raw-pdf-vault/middle-school/Set-1/round1.pdf",
            "raw-pdf-vault/middle-school/Set-1/round2.pdf",
        ])

    def test_pdfFilterIsCaseInsensitive(self) -> None:
        """Keys ending in .PDF or .Pdf are also included (Req 1.2)."""
        keys = [
            "raw-pdf-vault/middle-school/Set-1/round1.PDF",
            "raw-pdf-vault/middle-school/Set-1/round2.Pdf",
            "raw-pdf-vault/middle-school/Set-1/round3.pdf",
            "raw-pdf-vault/middle-school/Set-1/notes.txt",
        ]
        mockS3 = self._makeS3Client([keys])

        result = listPdfKeys(mockS3, "bucket", "raw-pdf-vault/middle-school/")

        assert len(result) == 3
        assert "raw-pdf-vault/middle-school/Set-1/notes.txt" not in result

    def test_emptyBucketReturnsEmptyList(self) -> None:
        """An empty bucket (no Contents) returns an empty list."""
        mockS3 = self._makeS3Client([[]])

        result = listPdfKeys(mockS3, "bucket", "prefix/")

        assert result == []

    def test_s3FailurePropagates(self) -> None:
        """Paginator exceptions are re-raised (Req 1.5)."""
        mockPaginator = MagicMock()
        mockPaginator.paginate.side_effect = RuntimeError("S3 unavailable")
        mockS3 = MagicMock()
        mockS3.get_paginator.return_value = mockPaginator

        with pytest.raises(RuntimeError, match="S3 unavailable"):
            listPdfKeys(mockS3, "bucket", "prefix/")

    def test_s3FailureLogsPrefix(self, caplog: pytest.LogCaptureFixture) -> None:
        """S3 failure is logged with the prefix before re-raising (Req 1.5)."""
        mockPaginator = MagicMock()
        mockPaginator.paginate.side_effect = RuntimeError("timeout")
        mockS3 = MagicMock()
        mockS3.get_paginator.return_value = mockPaginator

        with caplog.at_level(logging.ERROR, logger="src.orchestrator.handler"):
            with pytest.raises(RuntimeError):
                listPdfKeys(mockS3, "bucket", "raw-pdf-vault/middle-school/")

        assert any(
            "raw-pdf-vault/middle-school/" in record.message
            for record in caplog.records
        )

    def test_paginatorCalledWithCorrectBucketAndPrefix(self) -> None:
        """get_paginator is called with list_objects_v2 and correct Bucket/Prefix."""
        mockS3 = self._makeS3Client([[]])

        listPdfKeys(mockS3, "my-bucket", "my-prefix/")

        mockS3.get_paginator.assert_called_once_with("list_objects_v2")
        mockS3.get_paginator.return_value.paginate.assert_called_once_with(
            Bucket="my-bucket", Prefix="my-prefix/"
        )


class TestEnqueueKeys:
    """Unit tests for enqueueKeys."""

    def test_enqueueCountMatchesKeyCount(self) -> None:
        """enqueueKeys returns the number of keys enqueued (Req 1.4)."""
        mockSqs = MagicMock()
        keys = ["a/b.pdf", "c/d.pdf", "e/f.pdf"]

        result = enqueueKeys(mockSqs, "https://sqs.example.com/q", keys)

        assert result == 3

    def test_sendMessageCalledOncePerKey(self) -> None:
        """send_message is called exactly once per key (Req 1.3)."""
        mockSqs = MagicMock()
        keys = ["a/b.pdf", "c/d.pdf"]

        enqueueKeys(mockSqs, "https://sqs.example.com/q", keys)

        assert mockSqs.send_message.call_count == 2

    def test_messageBodyContainsSqsKey(self) -> None:
        """Each message body is a JSON object with the s3_key field (Req 1.3)."""
        mockSqs = MagicMock()
        keys = ["raw-pdf-vault/middle-school/Set-1/round1.pdf"]

        enqueueKeys(mockSqs, "https://sqs.example.com/q", keys)

        mockSqs.send_message.assert_called_once_with(
            QueueUrl="https://sqs.example.com/q",
            MessageBody=json.dumps({"s3_key": "raw-pdf-vault/middle-school/Set-1/round1.pdf"}),
        )

    def test_emptyKeyListReturnsZero(self) -> None:
        """An empty key list returns 0 and makes no send_message calls."""
        mockSqs = MagicMock()

        result = enqueueKeys(mockSqs, "https://sqs.example.com/q", [])

        assert result == 0
        mockSqs.send_message.assert_not_called()

    def test_sqsFailurePropagates(self) -> None:
        """send_message exceptions are re-raised (Req 1.6)."""
        mockSqs = MagicMock()
        mockSqs.send_message.side_effect = RuntimeError("SQS unavailable")

        with pytest.raises(RuntimeError, match="SQS unavailable"):
            enqueueKeys(mockSqs, "https://sqs.example.com/q", ["a/b.pdf"])

    def test_sqsFailureLogsKey(self, caplog: pytest.LogCaptureFixture) -> None:
        """SQS failure is logged with the affected key before re-raising (Req 1.6)."""
        mockSqs = MagicMock()
        mockSqs.send_message.side_effect = RuntimeError("connection refused")

        with caplog.at_level(logging.ERROR, logger="src.orchestrator.handler"):
            with pytest.raises(RuntimeError):
                enqueueKeys(mockSqs, "https://sqs.example.com/q", ["raw-pdf-vault/Set-1/round1.pdf"])

        assert any(
            "raw-pdf-vault/Set-1/round1.pdf" in record.message
            for record in caplog.records
        )

    def test_keysEnqueuedInOrder(self) -> None:
        """Keys are enqueued in the order they appear in the input list."""
        mockSqs = MagicMock()
        keys = ["first.pdf", "second.pdf", "third.pdf"]

        enqueueKeys(mockSqs, "https://sqs.example.com/q", keys)

        expectedCalls = [
            call(QueueUrl="https://sqs.example.com/q", MessageBody=json.dumps({"s3_key": k}))
            for k in keys
        ]
        mockSqs.send_message.assert_has_calls(expectedCalls, any_order=False)


class TestHandlerReturnShape:
    """Unit tests for the handler return value shape (Req 10.5)."""

    def test_handlerReturnsEnqueuedCount(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """handler returns {"enqueued": N} where N is the number of PDFs found."""
        import os
        import src.orchestrator.handler as orchestratorModule

        monkeypatch.setenv("SQS_QUEUE_URL", "https://sqs.example.com/q")
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        monkeypatch.setenv("S3_PREFIX", "test-prefix/")

        pdfKeys = [
            "test-prefix/Set-1/round1.pdf",
            "test-prefix/Set-1/round2.pdf",
        ]

        mockPaginator = _buildPaginator([pdfKeys])
        mockS3 = MagicMock()
        mockS3.get_paginator.return_value = mockPaginator

        mockSqs = MagicMock()

        mockSession = MagicMock()
        mockSession.client.side_effect = lambda svc: mockS3 if svc == "s3" else mockSqs

        monkeypatch.setattr(orchestratorModule.boto3, "Session", lambda **_: mockSession)

        result = orchestratorModule.handler({}, None)

        assert result == {"enqueued": 2}

    def test_handlerRaisesWhenQueueUrlMissing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """handler raises ValueError when SQS_QUEUE_URL is not set."""
        import src.orchestrator.handler as orchestratorModule

        monkeypatch.delenv("SQS_QUEUE_URL", raising=False)

        with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
            orchestratorModule.handler({}, None)
