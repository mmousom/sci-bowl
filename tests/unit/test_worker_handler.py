"""Unit tests for src/worker/handler.py.

Mocks all sub-module functions and AWS clients. Tests cover:
- Happy path: processRecord returns item count
- S3 download failure raises
- Chunking failure raises
- Structural parse failure raises
- Bedrock failure raises
- DynamoDB write failure raises
- Zero-chunk ValueError raises

Requirements: 2.2, 3.1, 3.3, 5.3, 6.6, 7.5, 7.6, 8.5, 8.7
"""

import json
from unittest.mock import MagicMock, call, patch

import pytest

from src.worker.handler import processRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_S3_KEY = "raw-pdf-vault/middle-school/Sample-Set-13/2019-NSB-MSR-Round-10A.pdf"
_BUCKET = "eshaan-sci-bowl-paper"
_TABLE = "ScienceBowlQuestions"

_RECORD = {"body": json.dumps({"s3_key": _S3_KEY})}

_STRUCTURAL = {
    "question_number": "1",
    "category": "Life Science",
    "match_type": "TOSS-UP",
    "answer_format": "Short Answer",
}

_FREE_TEXT = {
    "question_stem": "What is mitosis?",
    "answer_choices": [],
    "answer": "Cell division",
}

_CHUNKS = [
    "TOSS-UP\n1) Life Science Short Answer\nWhat is mitosis?\nANSWER: Cell division\n",
    "BONUS\n2) Life Science Short Answer\nWhat is meiosis?\nANSWER: Gamete production\n",
]

_STRUCTURAL_BONUS = {
    "question_number": "2",
    "category": "Life Science",
    "match_type": "BONUS",
    "answer_format": "Short Answer",
}

_FREE_TEXT_BONUS = {
    "question_stem": "What is meiosis?",
    "answer_choices": [],
    "answer": "Gamete production",
}


def _makeClients() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (s3Client, bedrockClient, dynamoClient) mocks."""
    return MagicMock(), MagicMock(), MagicMock()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestProcessRecordHappyPath:
    """processRecord returns the count of items written on success."""

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_happyPathReturnsTwoItemCount(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """Happy path with two chunks returns count == 2 (Req 2.2, 3.1)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = _CHUNKS
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.side_effect = [_STRUCTURAL, _STRUCTURAL_BONUS]
        mockFreeText.side_effect = [_FREE_TEXT, _FREE_TEXT_BONUS]

        s3, bedrock, dynamo = _makeClients()
        count = processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

        assert count == 2
        assert mockWrite.call_count == 2

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_happyPathSingleChunkReturnsOne(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """Happy path with one chunk returns count == 1."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.return_value = _FREE_TEXT

        s3, bedrock, dynamo = _makeClients()
        count = processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

        assert count == 1
        mockWrite.assert_called_once()

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_happyPathPassesCorrectClientsToSubmodules(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """processRecord passes the correct clients and keys to sub-module calls."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.return_value = _FREE_TEXT

        s3, bedrock, dynamo = _makeClients()
        processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

        mockDownload.assert_called_once_with(s3, _BUCKET, _S3_KEY)
        mockFreeText.assert_called_once_with(
            bedrock, _CHUNKS[0], _STRUCTURAL["answer_format"], s3Key=_S3_KEY
        )
        mockWrite.assert_called_once()
        writeCallItem = mockWrite.call_args[0][2]
        assert writeCallItem["Set_Round"] == "Sample-Set-13_2019-NSB-MSR-Round-10A"
        assert writeCallItem["source_s3_key"] == _S3_KEY


# ---------------------------------------------------------------------------
# S3 download failure (Req 3.1)
# ---------------------------------------------------------------------------

class TestS3DownloadFailure:
    """S3 download errors propagate out of processRecord (Req 3.1)."""

    @patch("src.worker.handler.downloadPdf")
    def test_s3DownloadFailureRaises(self, mockDownload: MagicMock) -> None:
        """S3 ClientError from downloadPdf is re-raised (Req 3.1)."""
        mockDownload.side_effect = RuntimeError("S3 unavailable")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(RuntimeError, match="S3 unavailable"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.downloadPdf")
    def test_s3DownloadFailureDoesNotCallChunker(self, mockDownload: MagicMock) -> None:
        """When S3 download fails, no downstream functions are called."""
        mockDownload.side_effect = RuntimeError("S3 error")

        s3, bedrock, dynamo = _makeClients()
        with patch("src.worker.handler.chunkQuestions") as mockChunk:
            with pytest.raises(RuntimeError):
                processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)
            mockChunk.assert_not_called()


# ---------------------------------------------------------------------------
# Chunking failure (Req 5.3)
# ---------------------------------------------------------------------------

class TestChunkingFailure:
    """Chunking errors propagate out of processRecord (Req 5.3)."""

    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_chunkingValueErrorRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
    ) -> None:
        """ValueError from chunkQuestions is re-raised (Req 5.3)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "no headers here"
        mockChunk.side_effect = ValueError("no TOSS-UP/BONUS lines found")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ValueError, match="no TOSS-UP/BONUS lines found"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_chunkingFailureDoesNotCallBedrock(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
    ) -> None:
        """When chunking fails, Bedrock is never invoked."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "text"
        mockChunk.side_effect = ValueError("zero chunks")

        s3, bedrock, dynamo = _makeClients()
        with patch("src.worker.handler.extractFreeTextFields") as mockFreeText:
            with pytest.raises(ValueError):
                processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)
            mockFreeText.assert_not_called()


# ---------------------------------------------------------------------------
# Zero-chunk ValueError (Req 5.3, 10.6)
# ---------------------------------------------------------------------------

class TestZeroChunkValueError:
    """chunkQuestions returning an empty list triggers ValueError (Req 5.3)."""

    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_zeroChunksRaisesValueError(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
    ) -> None:
        """chunkQuestions raising ValueError for zero chunks propagates (Req 5.3)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "some text"
        mockChunk.side_effect = ValueError("Non-empty text produced zero chunks")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ValueError, match="zero chunks"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)


# ---------------------------------------------------------------------------
# Structural parse failure (Req 6.6)
# ---------------------------------------------------------------------------

class TestStructuralParseFailure:
    """parseStructuralFields errors propagate out of processRecord (Req 6.6)."""

    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_structuralParseValueErrorRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
    ) -> None:
        """ValueError from parseStructuralFields is re-raised (Req 6.6)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.side_effect = ValueError("Missing field: match_type")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ValueError, match="Missing field: match_type"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_structuralParseFailureDoesNotCallBedrock(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
    ) -> None:
        """When structural parse fails, Bedrock is never invoked."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.side_effect = ValueError("Missing field: answer_format")

        s3, bedrock, dynamo = _makeClients()
        with patch("src.worker.handler.extractFreeTextFields") as mockFreeText:
            with pytest.raises(ValueError):
                processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)
            mockFreeText.assert_not_called()


# ---------------------------------------------------------------------------
# Bedrock failure (Req 7.5, 7.6)
# ---------------------------------------------------------------------------

class TestBedrockFailure:
    """Bedrock errors propagate out of processRecord (Req 7.5, 7.6)."""

    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_bedrockThrottlingExceptionRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
    ) -> None:
        """ThrottlingException from Bedrock is re-raised for SQS backoff (Req 7.5)."""
        throttlingError = RuntimeError("ThrottlingException")
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.side_effect = throttlingError

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(RuntimeError, match="ThrottlingException"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_bedrockGenericExceptionRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
    ) -> None:
        """Generic Bedrock error is re-raised (Req 7.6)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.side_effect = ConnectionError("Bedrock unreachable")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ConnectionError, match="Bedrock unreachable"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_bedrockFailureDoesNotCallDynamo(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """When Bedrock fails, DynamoDB write is never attempted."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.side_effect = ValueError("Missing field: question_stem")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ValueError):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)
        mockWrite.assert_not_called()


# ---------------------------------------------------------------------------
# DynamoDB write failure (Req 8.5, 8.7)
# ---------------------------------------------------------------------------

class TestDynamoWriteFailure:
    """DynamoDB write errors propagate out of processRecord (Req 8.5, 8.7)."""

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_dynamoPutItemFailureRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """put_item failure from writeQuestion is re-raised (Req 8.5)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.return_value = _FREE_TEXT
        mockWrite.side_effect = RuntimeError("DynamoDB unavailable")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(RuntimeError, match="DynamoDB unavailable"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_dynamoMissingFieldValueErrorRaises(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """ValueError from writeQuestion (missing field) is re-raised (Req 8.7)."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = [_CHUNKS[0]]
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.return_value = _STRUCTURAL
        mockFreeText.return_value = _FREE_TEXT
        mockWrite.side_effect = ValueError("Missing required field 'answer'")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(ValueError, match="Missing required field"):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

    @patch("src.worker.handler.writeQuestion")
    @patch("src.worker.handler.extractFreeTextFields")
    @patch("src.worker.handler.parseStructuralFields")
    @patch("src.worker.handler.deriveSetRound")
    @patch("src.worker.handler.chunkQuestions")
    @patch("src.worker.handler.extractText")
    @patch("src.worker.handler.downloadPdf")
    def test_dynamoFailureOnFirstChunkStopsProcessing(
        self,
        mockDownload: MagicMock,
        mockExtract: MagicMock,
        mockChunk: MagicMock,
        mockDerive: MagicMock,
        mockParse: MagicMock,
        mockFreeText: MagicMock,
        mockWrite: MagicMock,
    ) -> None:
        """DynamoDB failure on the first chunk stops processing remaining chunks."""
        mockDownload.return_value = b"pdf-bytes"
        mockExtract.return_value = "raw text"
        mockChunk.return_value = _CHUNKS  # two chunks
        mockDerive.return_value = "Sample-Set-13_2019-NSB-MSR-Round-10A"
        mockParse.side_effect = [_STRUCTURAL, _STRUCTURAL_BONUS]
        mockFreeText.side_effect = [_FREE_TEXT, _FREE_TEXT_BONUS]
        mockWrite.side_effect = RuntimeError("DynamoDB error")

        s3, bedrock, dynamo = _makeClients()
        with pytest.raises(RuntimeError):
            processRecord(_RECORD, s3, bedrock, dynamo, _BUCKET, _TABLE)

        # Only the first write was attempted before the exception halted processing
        assert mockWrite.call_count == 1
