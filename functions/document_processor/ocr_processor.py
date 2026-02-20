"""Text extraction for native PDFs, scanned PDFs (OCR), and DOCX files.

Decision tree:
  - DOCX          -> python-docx
  - Native PDF     -> PyMuPDF (fast, no API cost)
  - Scanned PDF    -> Azure Document Intelligence prebuilt-read (OCR)
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from docx import Document as DocxDocument

from .config import AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT, get_default_credential

logger = logging.getLogger(__name__)

# Heuristic threshold: fewer than this many chars/page → treat as scanned
_CHARS_PER_PAGE_THRESHOLD = 100


class OcrProcessor:
    """Extract text from PDF and DOCX documents, routing to OCR when needed."""

    def __init__(self) -> None:
        self._doc_intelligence_client: DocumentIntelligenceClient | None = None

    @property
    def _client(self) -> DocumentIntelligenceClient:
        """Lazy-initialise the Document Intelligence client (avoids cold-start cost)."""
        if self._doc_intelligence_client is None:
            self._doc_intelligence_client = DocumentIntelligenceClient(
                endpoint=AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
                credential=get_default_credential(),
            )
        return self._doc_intelligence_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_scanned_pdf(self, content: bytes) -> bool:
        """Return True when the PDF likely contains no selectable text.

        Uses PyMuPDF to read text; if the average chars-per-page falls below
        the threshold the document is assumed to be a scanned image PDF.
        """
        try:
            doc = fitz.open(stream=content, filetype="pdf")  # type: ignore[call-arg]
            if doc.page_count == 0:
                return True
            total_chars = sum(len(page.get_text()) for page in doc)
            avg_chars = total_chars / doc.page_count
            doc.close()
            return avg_chars < _CHARS_PER_PAGE_THRESHOLD
        except Exception:
            logger.exception("PyMuPDF failed during scanned-PDF heuristic")
            # Fall back to OCR if we cannot determine the type
            return True

    def extract_text(self, content: bytes, filename: str) -> str:
        """Return structured text with '--- Page N ---' markers.

        Routing:
          *.docx  -> python-docx
          *.pdf with native text -> PyMuPDF
          *.pdf scanned/image   -> Document Intelligence
        """
        lower = filename.lower()

        if lower.endswith(".docx"):
            return self._extract_docx(content)

        if lower.endswith(".pdf"):
            if self.is_scanned_pdf(content):
                logger.info("Routing %s to Document Intelligence OCR", filename)
                return self._extract_pdf_ocr(content)
            logger.info("Routing %s to PyMuPDF native extraction", filename)
            return self._extract_pdf_native(content)

        # Unsupported format — return raw bytes decoded best-effort
        logger.warning("Unsupported file type for '%s'; attempting UTF-8 decode", filename)
        return content.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_pdf_native(self, content: bytes) -> str:
        """Extract text from a native (searchable) PDF using PyMuPDF."""
        doc = fitz.open(stream=content, filetype="pdf")  # type: ignore[call-arg]
        try:
            pages: list[str] = []
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if text:
                    pages.append(f"--- Page {page_num} ---\n{text}")
            return "\n\n".join(pages)
        finally:
            doc.close()

    def _extract_pdf_ocr(self, content: bytes) -> str:
        """Send a scanned PDF to Document Intelligence and return page-marked text."""
        poller = self._client.begin_analyze_document(
            "prebuilt-read",
            AnalyzeDocumentRequest(bytes_source=content),
        )
        result = poller.result()

        if not result.pages:
            return ""

        pages: list[str] = []
        for page in result.pages:
            page_num = page.page_number
            lines = [line.content for line in (page.lines or [])]
            text = "\n".join(lines).strip()
            if text:
                pages.append(f"--- Page {page_num} ---\n{text}")

        return "\n\n".join(pages)

    def _extract_docx(self, content: bytes) -> str:
        """Extract text from a DOCX file using python-docx.

        DOCX files do not have meaningful page numbers at the paragraph level,
        so we emit a single Page 1 marker.
        """
        doc = DocxDocument(io.BytesIO(content))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        body = "\n\n".join(paragraphs)
        return f"--- Page 1 ---\n{body}" if body else ""
