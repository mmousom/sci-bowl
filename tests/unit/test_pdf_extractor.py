"""Unit and property-based tests for src/worker/pdf_extractor.py."""

import io
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.worker.pdf_extractor import downloadPdf, extractText


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: sci-bowl-pdf-etl, Property 3: Page Text Concatenation
@given(st.lists(st.one_of(st.none(), st.text())))
def test_extractTextConcatenatesPages(pageTexts: list) -> None:
    """Property 3: Page Text Concatenation — Validates: Requirements 3.2

    For any list of page texts (None, empty string, or non-empty string),
    extractText SHALL return the concatenation of all pages treated as empty
    string when None, in page order.
    """
    # Build mock pages
    mockPages = []
    for text in pageTexts:
        page = MagicMock()
        page.extract_text.return_value = text
        mockPages.append(page)

    mockPdf = MagicMock()
    mockPdf.pages = mockPages
    mockPdf.__enter__ = MagicMock(return_value=mockPdf)
    mockPdf.__exit__ = MagicMock(return_value=False)

    with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
        result = extractText(b"fake-pdf-bytes")

    expected = "".join(text if text else "" for text in pageTexts)
    assert result == expected


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestExtractText:
    """Unit tests for extractText."""

    def _makeExtractTextMock(self, pageTexts: list) -> MagicMock:
        """Build a pdfplumber context-manager mock from a list of page texts."""
        mockPages = []
        for text in pageTexts:
            page = MagicMock()
            page.extract_text.return_value = text
            mockPages.append(page)

        mockPdf = MagicMock()
        mockPdf.pages = mockPages
        mockPdf.__enter__ = MagicMock(return_value=mockPdf)
        mockPdf.__exit__ = MagicMock(return_value=False)
        return mockPdf

    def test_nonePageTreatedAsEmpty(self) -> None:
        """A page returning None is treated as an empty string (Req 3.2)."""
        mockPdf = self._makeExtractTextMock([None])
        with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
            assert extractText(b"bytes") == ""

    def test_emptyPageTreatedAsEmpty(self) -> None:
        """A page returning '' is treated as an empty string (Req 3.2)."""
        mockPdf = self._makeExtractTextMock([""])
        with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
            assert extractText(b"bytes") == ""

    def test_multiPageConcatenationInOrder(self) -> None:
        """Pages are concatenated in page order (Req 3.2)."""
        mockPdf = self._makeExtractTextMock(["hello ", "world"])
        with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
            assert extractText(b"bytes") == "hello world"

    def test_mixedNoneAndTextPages(self) -> None:
        """None pages interspersed with text pages are handled correctly (Req 3.2)."""
        mockPdf = self._makeExtractTextMock(["first", None, "third"])
        with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
            assert extractText(b"bytes") == "firstthird"

    def test_zeroPagesReturnsEmptyString(self) -> None:
        """A PDF with no pages returns an empty string."""
        mockPdf = self._makeExtractTextMock([])
        with patch("src.worker.pdf_extractor.pdfplumber.open", return_value=mockPdf):
            assert extractText(b"bytes") == ""

    def test_pdfplumberExceptionPropagates(self) -> None:
        """pdfplumber exceptions are re-raised (Req 3.3)."""
        with patch(
            "src.worker.pdf_extractor.pdfplumber.open",
            side_effect=Exception("corrupt pdf"),
        ):
            with pytest.raises(Exception, match="corrupt pdf"):
                extractText(b"bad-bytes")

    def test_passesBytesAsIoBytesIO(self) -> None:
        """extractText wraps pdfBytes in io.BytesIO before passing to pdfplumber."""
        mockPdf = self._makeExtractTextMock(["text"])
        capturedArgs = []

        def capturingOpen(arg):
            capturedArgs.append(arg)
            return mockPdf

        with patch("src.worker.pdf_extractor.pdfplumber.open", side_effect=capturingOpen):
            extractText(b"my-bytes")

        assert len(capturedArgs) == 1
        assert isinstance(capturedArgs[0], io.BytesIO)
        assert capturedArgs[0].read() == b"my-bytes"


class TestDownloadPdf:
    """Unit tests for downloadPdf."""

    def test_returnsBodyBytes(self) -> None:
        """downloadPdf returns the bytes from the S3 Body (Req 3.1)."""
        mockBody = MagicMock()
        mockBody.read.return_value = b"pdf-content"
        mockS3 = MagicMock()
        mockS3.get_object.return_value = {"Body": mockBody}

        result = downloadPdf(mockS3, "my-bucket", "my/key.pdf")

        assert result == b"pdf-content"
        mockS3.get_object.assert_called_once_with(Bucket="my-bucket", Key="my/key.pdf")

    def test_s3ExceptionPropagates(self) -> None:
        """S3 exceptions are re-raised (Req 3.1)."""
        mockS3 = MagicMock()
        mockS3.get_object.side_effect = RuntimeError("S3 unavailable")

        with pytest.raises(RuntimeError, match="S3 unavailable"):
            downloadPdf(mockS3, "bucket", "key.pdf")

    def test_s3ExceptionLogsKeyAndError(self, caplog: pytest.LogCaptureFixture) -> None:
        """S3 failure is logged with the key before re-raising (Req 3.1)."""
        import logging

        mockS3 = MagicMock()
        mockS3.get_object.side_effect = RuntimeError("timeout")

        with caplog.at_level(logging.ERROR, logger="src.worker.pdf_extractor"):
            with pytest.raises(RuntimeError):
                downloadPdf(mockS3, "bucket", "some/key.pdf")

        assert any("some/key.pdf" in record.message for record in caplog.records)
