"""
test_chunker.py — Unit tests for DocumentChunker.

DocumentChunker is responsible for splitting extracted document text into
overlapping chunks suitable for Azure AI Search ingestion. Each chunk carries
metadata (title, section_heading, page_number, chunk_index, total_chunks) and
is prepended with a "Title: ..." header so the embedding model has full context.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Minimal in-process implementation of DocumentChunker so tests run without
# the full project installed. Replace with a real import once src/ is wired up.
# ---------------------------------------------------------------------------

@dataclass
class ChunkMetadata:
    title: str = ""
    section_heading: str = ""
    page_number: int = 1
    chunk_index: int = 0
    total_chunks: int = 1
    document_id: str = ""
    source_url: str = ""
    category: str = ""
    department: str = ""
    allowed_groups: list[str] = field(default_factory=list)


@dataclass
class DocumentChunk:
    chunk_content: str
    metadata: ChunkMetadata


class DocumentChunker:
    """
    Splits a document body into overlapping token-approximate chunks.

    Parameters
    ----------
    max_tokens : int
        Target maximum tokens per chunk. Approximated as chars / 4.
    overlap_tokens : int
        Number of tokens shared between consecutive chunks.
    min_tokens : int
        Minimum chunk size; chunks smaller than this are discarded.
    """

    CHARS_PER_TOKEN = 4  # rough approximation

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 128,
        min_tokens: int = 32,
    ) -> None:
        self.max_chars = max_tokens * self.CHARS_PER_TOKEN
        self.overlap_chars = overlap_tokens * self.CHARS_PER_TOKEN
        self.min_chars = min_tokens * self.CHARS_PER_TOKEN

    def _extract_section_heading(self, text: str) -> str:
        """Return the first markdown-style heading found in the text, or empty string."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            # Also detect ALL-CAPS lines as headings (common in HR PDFs)
            words = stripped.split()
            if len(words) >= 2 and stripped.isupper() and len(stripped) < 80:
                return stripped.title()
        return ""

    def chunk(
        self,
        text: str,
        title: str = "",
        page_number: int = 1,
        document_id: str = "",
        source_url: str = "",
        category: str = "",
        department: str = "",
        allowed_groups: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Split *text* into overlapping chunks and return them with metadata."""
        if not text or not text.strip():
            return []

        allowed_groups = allowed_groups or []
        heading = self._extract_section_heading(text)

        # Build raw chunks by sliding window over characters
        raw_chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            raw_chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - self.overlap_chars

        # Filter out chunks that are too small
        raw_chunks = [c for c in raw_chunks if len(c.strip()) >= self.min_chars]

        if not raw_chunks:
            return []

        total = len(raw_chunks)
        chunks: list[DocumentChunk] = []
        for idx, raw in enumerate(raw_chunks):
            # Prepend title context so the embedding model always has document identity
            content = f"Title: {title}\n\n{raw.strip()}" if title else raw.strip()
            meta = ChunkMetadata(
                title=title,
                section_heading=heading,
                page_number=page_number,
                chunk_index=idx,
                total_chunks=total,
                document_id=document_id,
                source_url=source_url,
                category=category,
                department=department,
                allowed_groups=allowed_groups,
            )
            chunks.append(DocumentChunk(chunk_content=content, metadata=meta))

        return chunks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDocumentChunker:
    """Tests for DocumentChunker behavior."""

    def setup_method(self) -> None:
        # 512-token max, 128-token overlap, 8-token minimum (32 chars).
        # A small min_tokens lets short single-chunk documents pass while still
        # filtering out pathologically tiny fragments in test_min_chunk_size_filter.
        self.chunker = DocumentChunker(max_tokens=512, overlap_tokens=128, min_tokens=8)

    # ------------------------------------------------------------------
    # test_basic_chunking
    # ------------------------------------------------------------------
    def test_basic_chunking(self) -> None:
        """A short document that fits in one chunk produces exactly one chunk."""
        text = "This is a short HR policy document about PTO. Employees accrue 15 days per year."
        chunks = self.chunker.chunk(text, title="PTO Policy")

        assert len(chunks) == 1
        assert "PTO Policy" in chunks[0].chunk_content
        assert chunks[0].metadata.chunk_index == 0
        assert chunks[0].metadata.total_chunks == 1

    # ------------------------------------------------------------------
    # test_long_doc_produces_multiple_chunks
    # ------------------------------------------------------------------
    def test_long_doc_produces_multiple_chunks(self) -> None:
        """A ~2000-word document is split into multiple chunks."""
        # ~2000 words × 5 chars avg = ~10 000 chars >> 512 tokens × 4 chars = 2048 chars
        word = "policy "
        text = word * 2000
        chunks = self.chunker.chunk(text, title="Employee Handbook")

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata.total_chunks == len(chunks)

    # ------------------------------------------------------------------
    # test_overlap_preserved
    # ------------------------------------------------------------------
    def test_overlap_preserved(self) -> None:
        """Consecutive chunks share approximately overlap_tokens worth of content."""
        # 3 × max_chars of repeating text guarantees multiple chunks with clear boundaries
        max_chars = self.chunker.max_chars
        overlap_chars = self.chunker.overlap_chars
        segment = "A" * max_chars
        text = segment * 3

        chunks = self.chunker.chunk(text, title="Overlap Test Doc")
        assert len(chunks) >= 2

        # The tail of chunk 0 and the head of chunk 1 must share content
        # (after stripping the "Title: ..." prefix)
        raw_0 = chunks[0].chunk_content.split("\n\n", 1)[-1]
        raw_1 = chunks[1].chunk_content.split("\n\n", 1)[-1]

        tail_of_0 = raw_0[-overlap_chars:]
        head_of_1 = raw_1[:overlap_chars]

        assert tail_of_0 == head_of_1, (
            f"Expected {overlap_chars} overlapping chars between chunk 0 and chunk 1"
        )

    # ------------------------------------------------------------------
    # test_section_heading_extracted
    # ------------------------------------------------------------------
    def test_section_heading_extracted(self) -> None:
        """Markdown headings in the document body are captured in chunk metadata."""
        text = "# Benefits Enrollment\n\nEmployees may enroll during the annual open enrollment period."
        chunks = self.chunker.chunk(text, title="Benefits Guide")

        assert len(chunks) >= 1
        assert chunks[0].metadata.section_heading == "Benefits Enrollment"

    # ------------------------------------------------------------------
    # test_metadata_prepended
    # ------------------------------------------------------------------
    def test_metadata_prepended(self) -> None:
        """chunk_content starts with 'Title: <document title>' when a title is given."""
        text = "PTO accrues at 1.25 days per month for full-time employees."
        chunks = self.chunker.chunk(text, title="PTO Policy v3")

        assert len(chunks) == 1
        assert chunks[0].chunk_content.startswith("Title: PTO Policy v3")

    # ------------------------------------------------------------------
    # test_min_chunk_size_filter
    # ------------------------------------------------------------------
    def test_min_chunk_size_filter(self) -> None:
        """Text shorter than min_tokens does not produce a chunk."""
        # min_tokens=32 → min_chars=128; give it only 10 chars
        very_short_text = "Hi there."
        chunks = self.chunker.chunk(very_short_text, title="Stub Doc")

        assert len(chunks) == 0, (
            f"Expected 0 chunks for text shorter than min_tokens, got {len(chunks)}"
        )

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------
    def test_empty_text_returns_no_chunks(self) -> None:
        chunks = self.chunker.chunk("", title="Empty")
        assert chunks == []

    def test_whitespace_only_returns_no_chunks(self) -> None:
        chunks = self.chunker.chunk("   \n\t  ", title="Whitespace")
        assert chunks == []

    def test_metadata_fields_propagated(self) -> None:
        """Metadata fields passed to chunk() appear on all returned chunks."""
        text = "Remote work policy details. " * 100
        chunks = self.chunker.chunk(
            text,
            title="Remote Work Policy",
            page_number=3,
            document_id="doc-abc-123",
            source_url="https://resllc.sharepoint.com/remote-policy",
            category="Work Arrangements",
            department="HR",
            allowed_groups=["grp-all-employees"],
        )
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.metadata.page_number == 3
            assert chunk.metadata.document_id == "doc-abc-123"
            assert chunk.metadata.source_url == "https://resllc.sharepoint.com/remote-policy"
            assert chunk.metadata.category == "Work Arrangements"
            assert chunk.metadata.department == "HR"
            assert "grp-all-employees" in chunk.metadata.allowed_groups

    def test_all_caps_heading_detected(self) -> None:
        """ALL CAPS lines (common in HR PDFs) are recognized as section headings."""
        text = "PERFORMANCE REVIEW PROCESS\n\nEmployees are reviewed annually in December."
        chunks = self.chunker.chunk(text, title="HR Handbook")
        assert len(chunks) >= 1
        assert chunks[0].metadata.section_heading == "Performance Review Process"
