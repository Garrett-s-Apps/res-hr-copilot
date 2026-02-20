"""Sliding-window, paragraph-aware text chunker with section heading extraction.

Strategy:
  1. Split on double-newlines (paragraph boundaries) first.
  2. If a paragraph overflows the token budget, split on sentences.
  3. Slide a 512-token window with 128-token overlap across the stream of
     paragraphs, keeping paragraph boundaries intact where possible.
  4. Detect section headings (Markdown '#' prefix or short ALL-CAPS lines)
     and carry the current heading forward into each chunk's metadata.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import tiktoken

_ENCODING_NAME = "cl100k_base"
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 128

# A line is treated as a section heading when it:
#   - starts with one or more '#' characters (Markdown heading), or
#   - is short (≤ 60 chars) and ALL CAPS (common in HR policy docs)
_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 &/\-,:]{2,59})$")


class DocumentChunker:
    """Split a document into overlapping token-budget chunks with rich metadata."""

    def __init__(self) -> None:
        self._enc = tiktoken.get_encoding(_ENCODING_NAME)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        title: str,
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return a list of chunk dicts ready for embedding and indexing.

        Each dict contains:
            id, chunk_content, chunk_index, total_chunks,
            title, section_heading, page_number,
            + all keys from *metadata*
        """
        paragraphs = self._split_paragraphs(text)
        token_segments = self._paragraphs_to_token_segments(paragraphs)
        windows = self._sliding_windows(token_segments)

        chunks: list[dict[str, Any]] = []
        current_heading = ""
        current_page = 1

        for idx, (token_ids, source_paragraphs) in enumerate(windows):
            # Track the last detected heading and page from contributing paragraphs
            for para in source_paragraphs:
                if self._is_heading(para):
                    current_heading = para.lstrip("#").strip()
                page_match = re.search(r"--- Page (\d+) ---", para)
                if page_match:
                    current_page = int(page_match.group(1))

            raw_text = self._enc.decode(token_ids)
            # Prepend structured metadata prefix so the embedding captures context
            prefix = f"Title: {title} | Section: {current_heading} | "
            chunk_text = prefix + raw_text

            chunks.append(
                {
                    "id": str(uuid.uuid4()),
                    "chunk_content": chunk_text,
                    "chunk_index": idx,
                    # total_chunks backfilled after full enumeration
                    "total_chunks": 0,
                    "title": title,
                    "section_heading": current_heading,
                    "page_number": current_page,
                    **metadata,
                }
            )

        total = len(chunks)
        for chunk in chunks:
            chunk["total_chunks"] = total

        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split on double newlines; keep page markers as their own segments."""
        raw = re.split(r"\n{2,}", text)
        paragraphs: list[str] = []
        for block in raw:
            block = block.strip()
            if block:
                paragraphs.append(block)
        return paragraphs

    def _paragraphs_to_token_segments(
        self, paragraphs: list[str]
    ) -> list[tuple[list[int], str]]:
        """Encode each paragraph, splitting oversized ones on sentence boundaries."""
        segments: list[tuple[list[int], str]] = []
        for para in paragraphs:
            tokens = self._enc.encode(para)
            if len(tokens) <= _CHUNK_TOKENS:
                segments.append((tokens, para))
            else:
                # Split on sentence boundaries (period/question/exclamation + space)
                sentences = re.split(r"(?<=[.?!])\s+", para)
                acc_tokens: list[int] = []
                acc_text: list[str] = []
                for sentence in sentences:
                    s_tokens = self._enc.encode(sentence)
                    if len(acc_tokens) + len(s_tokens) > _CHUNK_TOKENS and acc_tokens:
                        segments.append((acc_tokens, " ".join(acc_text)))
                        acc_tokens = []
                        acc_text = []
                    acc_tokens.extend(s_tokens)
                    acc_text.append(sentence)
                if acc_tokens:
                    segments.append((acc_tokens, " ".join(acc_text)))
        return segments

    def _sliding_windows(
        self, segments: list[tuple[list[int], str]]
    ) -> list[tuple[list[int], list[str]]]:
        """Build overlapping windows over the flat token stream.

        Returns list of (token_ids, source_paragraph_texts) per window.
        """
        windows: list[tuple[list[int], list[str]]] = []
        i = 0
        while i < len(segments):
            window_tokens: list[int] = []
            window_paras: list[str] = []
            j = i
            while j < len(segments) and len(window_tokens) + len(segments[j][0]) <= _CHUNK_TOKENS:
                window_tokens.extend(segments[j][0])
                window_paras.append(segments[j][1])
                j += 1
            if not window_tokens:
                # Single segment larger than budget — force include and advance
                window_tokens = segments[i][0][:_CHUNK_TOKENS]
                window_paras = [segments[i][1]]
                j = i + 1

            windows.append((window_tokens, window_paras))

            # Step forward, keeping _OVERLAP_TOKENS worth of previous content
            overlap_budget = _OVERLAP_TOKENS
            step = j - i
            while step > 1 and overlap_budget > 0:
                step -= 1
                overlap_budget -= len(segments[i + step - 1][0])
            i += max(1, step)

        return windows

    @staticmethod
    def _is_heading(text: str) -> bool:
        """Return True if the paragraph looks like a section heading."""
        first_line = text.split("\n")[0].strip()
        return bool(_HEADING_RE.match(first_line)) and len(first_line) <= 120
