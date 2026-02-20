"""Push document chunks to Azure AI Search with merge-or-upload semantics.

Uses DefaultAzureCredential (SearchIndexDataContributor role required on the
search resource).  Deletions purge all chunks for a given document_id using a
filter query against the stored document_id field.
"""

from __future__ import annotations

import logging

from azure.search.documents import SearchClient
from azure.search.documents.models import IndexingResult

from .config import (
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX_NAME,
    get_default_credential,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


class IndexPusher:
    """Upsert and delete document chunks in Azure AI Search."""

    def __init__(self) -> None:
        self._client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX_NAME,
            credential=get_default_credential(),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def upsert_chunks(self, chunks: list[dict]) -> None:
        """Merge-or-upload *chunks* into the search index in batches of 100.

        Each chunk dict must contain at minimum an 'id' field (the index key).
        Failed documents within a batch are logged but do not raise so that a
        single bad chunk does not abort the whole batch.
        """
        if not chunks:
            return

        for batch_start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            logger.info(
                "Upserting batch of %d chunks (offset %d)", len(batch), batch_start
            )
            results: list[IndexingResult] = self._client.merge_or_upload_documents(
                documents=batch
            )
            self._log_results(results)

    def get_chunk_ids(self, document_id: str) -> set[str]:
        """Return the set of all chunk IDs currently indexed for *document_id*.

        Used before upserting a new version so we can compute which old chunks
        are no longer present and delete only those (avoids delete-all data-loss window).
        """
        chunk_ids: set[str] = set()
        results = self._client.search(
            search_text="*",
            filter=f"document_id eq '{_escape_odata(document_id)}'",
            select=["id"],
            top=1000,
        )
        for r in results:
            chunk_ids.add(r["id"])
        return chunk_ids

    def delete_chunks(self, chunk_ids: set[str]) -> None:
        """Delete a specific set of chunks by their IDs."""
        if not chunk_ids:
            return
        ids_list = list(chunk_ids)
        for batch_start in range(0, len(ids_list), _BATCH_SIZE):
            batch = [{"id": cid} for cid in ids_list[batch_start : batch_start + _BATCH_SIZE]]
            self._client.delete_documents(documents=batch)
            logger.info("Deleted %d stale chunk(s)", len(batch))

    def delete_document(self, document_id: str) -> None:
        """Remove every chunk belonging to *document_id* from the index.

        Searches for all chunks where the 'document_id' field matches, then
        issues a batch delete.  The loop continues until no results remain to
        handle indexes with more than 1 000 matching chunks.
        """
        deleted_total = 0
        while True:
            results = self._client.search(
                search_text="*",
                filter=f"document_id eq '{_escape_odata(document_id)}'",
                select=["id"],
                top=_BATCH_SIZE,
            )
            batch = [{"id": r["id"]} for r in results]
            if not batch:
                break
            self._client.delete_documents(documents=batch)
            deleted_total += len(batch)
            logger.info(
                "Deleted %d chunks for document_id=%s (running total: %d)",
                len(batch),
                document_id,
                deleted_total,
            )
            if len(batch) < _BATCH_SIZE:
                # Fewer than a full batch returned — we've reached the end
                break

        logger.info(
            "Finished deleting %d total chunks for document_id=%s",
            deleted_total,
            document_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_results(results: list[IndexingResult]) -> None:
        for result in results:
            if not result.succeeded:
                logger.error(
                    "Index upsert failed for key=%s: status=%s error=%s",
                    result.key,
                    result.status_code,
                    result.error_message,
                )


def _escape_odata(value: str) -> str:
    """Escape single quotes in OData filter string values."""
    return value.replace("'", "''")
