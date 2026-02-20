"""Azure Functions v2 entry point for the RES HR Copilot ingestion pipeline.

Functions:
  - sharepoint_webhook: HTTP POST /api/webhook — receives Graph change notifications
  - delta_sync: Timer trigger every 15 minutes — full delta sync of configured libraries

Both converge on process_document() which orchestrates:
  download -> extract -> chunk -> embed -> ACL resolve -> index push
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

from document_processor.acl_resolver import AclResolver
from document_processor.chunker import DocumentChunker
from document_processor.config import (
    AZURE_STORAGE_CONNECTION_STRING,
    DELTA_LINK_TABLE_NAME,
    SHAREPOINT_LIBRARIES,
    get_graph_credential,
)
from document_processor.embedder import TextEmbedder
from document_processor.index_pusher import IndexPusher
from document_processor.ocr_processor import OcrProcessor

logger = logging.getLogger(__name__)

# Secret used to validate incoming Graph webhook notifications — prevents spoofed payloads
GRAPH_WEBHOOK_CLIENT_STATE = os.environ.get("GRAPH_WEBHOOK_CLIENT_STATE", "")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# ---------------------------------------------------------------------------
# Module-level singletons — instantiated once per worker process to reuse
# HTTP connection pools and credential token caches across invocations.
# ---------------------------------------------------------------------------
_ocr = OcrProcessor()
_chunker = DocumentChunker()
_embedder = TextEmbedder()
_acl_resolver = AclResolver()
_index_pusher = IndexPusher()


# ===========================================================================
# Function 1: SharePoint Graph webhook receiver
# ===========================================================================

@app.route(route="webhook", methods=["GET", "POST"])
async def sharepoint_webhook(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Microsoft Graph change notification webhooks for SharePoint.

    GET  — Graph lifecycle validation handshake (return validationToken as-is).
    POST — Change notification payload; triggers document processing for each
           changed drive item listed in the notification.
    """
    # --- Validation handshake (Graph sends GET with ?validationToken=...) ---
    validation_token = req.params.get("validationToken")
    if validation_token:
        logger.info("Responding to Graph webhook validation handshake")
        return func.HttpResponse(
            body=validation_token,
            status_code=200,
            mimetype="text/plain",
        )

    # --- Change notification (POST) ---
    try:
        body: dict[str, Any] = req.get_json()
    except ValueError:
        logger.warning("Webhook received non-JSON body")
        return func.HttpResponse("Bad Request", status_code=400)

    notifications: list[dict[str, Any]] = body.get("value", [])
    logger.info("Received %d notification(s) from Graph", len(notifications))

    # Reject any notification whose clientState does not match our secret —
    # prevents replay attacks from unauthorized senders
    if GRAPH_WEBHOOK_CLIENT_STATE:
        for notification in notifications:
            received_state = notification.get("clientState", "")
            if received_state != GRAPH_WEBHOOK_CLIENT_STATE:
                logger.warning(
                    "Webhook clientState mismatch — rejecting notification batch"
                )
                return func.HttpResponse("Forbidden", status_code=403)

    for notification in notifications:
        resource_data: dict[str, Any] = notification.get("resourceData", {})
        # Graph resource format: /sites/{siteId}/drives/{driveId}/items/{itemId}
        resource: str = notification.get("resource", "")
        site_id, drive_id, item_id = _parse_resource_path(resource)

        if not all([site_id, drive_id, item_id]):
            logger.warning("Could not parse resource path: %s", resource)
            continue

        change_type: str = notification.get("changeType", "updated")
        if change_type == "deleted":
            document_id = _make_document_id(site_id, drive_id, item_id)
            logger.info("Deleting document %s from index", document_id)
            _index_pusher.delete_document(document_id)
        else:
            try:
                await process_document(site_id, drive_id, item_id)
            except Exception:
                logger.exception(
                    "Failed to process item %s (drive %s)", item_id, drive_id
                )

    # Graph expects a 202 Accepted response within 3 seconds; heavy work above
    # should be offloaded to a queue in very high-volume scenarios.
    return func.HttpResponse(status_code=202)


# ===========================================================================
# Function 2: 15-minute delta sync timer
# ===========================================================================

@app.timer_trigger(
    schedule="0 */15 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
async def delta_sync(timer: func.TimerRequest) -> None:
    """Poll Graph delta API for all configured SharePoint libraries every 15 min.

    Delta links are persisted in Azure Table Storage between runs so only new
    changes are fetched (not a full crawl each time).
    """
    if timer.past_due:
        logger.warning("Delta sync timer is running late")

    if not SHAREPOINT_LIBRARIES:
        logger.info("SHAREPOINT_LIBRARIES not configured — skipping delta sync")
        return

    table_client = _get_table_client()

    libraries = [lib.strip() for lib in SHAREPOINT_LIBRARIES.split(",") if lib.strip()]
    for lib_spec in libraries:
        parts = lib_spec.split("|")
        if len(parts) != 2:
            logger.warning("Invalid SHAREPOINT_LIBRARIES entry (expected siteId|driveId): %s", lib_spec)
            continue
        site_id, drive_id = parts
        await _sync_library(site_id, drive_id, table_client)


# ===========================================================================
# Shared document processing pipeline
# ===========================================================================

async def process_document(site_id: str, drive_id: str, item_id: str) -> None:
    """Download, extract, chunk, embed, resolve ACLs, and index a drive item.

    This is the single processing path used by both the webhook and the timer
    so behaviour is identical regardless of how a change was detected.
    """
    graph_credential = get_graph_credential()

    # --- Download content and metadata via Graph ---
    content_bytes, filename, metadata = await _download_item(
        site_id, drive_id, item_id, graph_credential
    )
    if content_bytes is None:
        logger.warning("Skipping item %s — could not download content", item_id)
        return

    document_id = _make_document_id(site_id, drive_id, item_id)
    base_metadata = {
        "document_id": document_id,
        "site_id": site_id,
        "drive_id": drive_id,
        "item_id": item_id,
        "filename": filename,
        **metadata,
    }

    # --- Extract text (native PDF / OCR / DOCX) ---
    logger.info("Extracting text from %s", filename)
    text = _ocr.extract_text(content_bytes, filename)
    if not text.strip():
        logger.warning("No text extracted from %s — skipping indexing", filename)
        return

    # --- Resolve ACLs ---
    logger.info("Resolving ACLs for item %s", item_id)
    allowed_groups = await _acl_resolver.get_allowed_groups(site_id, drive_id, item_id)
    base_metadata["allowed_groups"] = allowed_groups

    # --- Chunk ---
    logger.info("Chunking document %s", document_id)
    title = metadata.get("title", filename)
    chunks = _chunker.chunk(text, title=title, metadata=base_metadata)
    logger.info("Produced %d chunks for %s", len(chunks), document_id)

    # --- Collect existing chunk IDs before overwriting ---
    # Query now so we know which stale chunks to remove after upserting new ones.
    # This prevents a window of data loss that would occur if we deleted first.
    old_chunk_ids: set[str] = _index_pusher.get_chunk_ids(document_id)

    # --- Embed ---
    logger.info("Embedding %d chunks", len(chunks))
    texts_to_embed = [chunk["chunk_content"] for chunk in chunks]
    vectors = _embedder.embed_batch(texts_to_embed)
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["content_vector"] = vector

    # --- Push to index (upsert first to avoid data-loss window) ---
    logger.info("Pushing %d chunks to search index", len(chunks))
    _index_pusher.upsert_chunks(chunks)

    # --- Delete only chunks that no longer exist in the new version ---
    new_chunk_ids: set[str] = {chunk["id"] for chunk in chunks}
    stale_ids = old_chunk_ids - new_chunk_ids
    if stale_ids:
        logger.info("Removing %d stale chunk(s) for document %s", len(stale_ids), document_id)
        _index_pusher.delete_chunks(stale_ids)

    logger.info("Completed processing for document %s", document_id)


# ===========================================================================
# Delta sync helpers
# ===========================================================================

async def _sync_library(
    site_id: str,
    drive_id: str,
    table_client: TableServiceClient | None,
) -> None:
    """Run one delta sync cycle for a single SharePoint drive."""
    from msgraph import GraphServiceClient  # local import to keep module top clean

    graph = GraphServiceClient(
        credentials=get_graph_credential(),
        scopes=["https://graph.microsoft.com/.default"],
    )

    delta_link_key = f"{site_id}_{drive_id}"
    stored_delta_link = _load_delta_link(table_client, delta_link_key)

    try:
        if stored_delta_link:
            # Fetch only changes since last run
            response = await graph.drives.by_drive_id(drive_id).root.delta.with_url(
                stored_delta_link
            ).get()
        else:
            # First run — fetch entire drive
            response = await graph.drives.by_drive_id(drive_id).root.delta.get()
    except Exception:
        logger.exception("Graph delta call failed for drive %s", drive_id)
        return

    page = response
    while page:
        items = page.value or []
        for item in items:
            item_id: str = item.id or ""
            deleted = getattr(item, "deleted", None)

            if deleted:
                document_id = _make_document_id(site_id, drive_id, item_id)
                logger.info("Delta sync: deleting document %s", document_id)
                _index_pusher.delete_document(document_id)
            else:
                # Only process files (skip folders)
                file_facet = getattr(item, "file", None)
                if file_facet and item_id:
                    try:
                        await process_document(site_id, drive_id, item_id)
                    except Exception:
                        logger.exception(
                            "Delta sync: failed to process item %s", item_id
                        )

        # Follow @odata.nextLink if present, otherwise persist deltaLink and stop
        next_link = getattr(page, "odata_next_link", None)
        delta_link = getattr(page, "odata_delta_link", None)

        if delta_link:
            _save_delta_link(table_client, delta_link_key, delta_link)

        if next_link:
            page = await graph.drives.by_drive_id(drive_id).root.delta.with_url(
                next_link
            ).get()
        else:
            break


# ===========================================================================
# Graph download helper
# ===========================================================================

async def _download_item(
    site_id: str,
    drive_id: str,
    item_id: str,
    credential: Any,
) -> tuple[bytes | None, str, dict[str, Any]]:
    """Return (content_bytes, filename, metadata_dict) for a drive item.

    Returns (None, '', {}) when the item cannot be downloaded (e.g. folders,
    unsupported types, or transient Graph errors).
    """
    from msgraph import GraphServiceClient

    graph = GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/.default"],
    )

    try:
        item = await (
            graph.sites.by_site_id(site_id)
            .drives.by_drive_id(drive_id)
            .items.by_drive_item_id(item_id)
            .get()
        )
    except Exception:
        logger.exception("Failed to fetch metadata for item %s", item_id)
        return None, "", {}

    if not item:
        return None, "", {}

    # Folders have no file facet
    if not getattr(item, "file", None):
        logger.debug("Skipping non-file item %s", item_id)
        return None, "", {}

    filename: str = item.name or item_id
    lower = filename.lower()
    if not (lower.endswith(".pdf") or lower.endswith(".docx")):
        logger.info("Skipping unsupported file type: %s", filename)
        return None, filename, {}

    # Download raw content
    try:
        content_stream = await (
            graph.sites.by_site_id(site_id)
            .drives.by_drive_id(drive_id)
            .items.by_drive_item_id(item_id)
            .content.get()
        )
        content_bytes = content_stream if isinstance(content_stream, bytes) else bytes(content_stream)  # type: ignore[arg-type]
    except Exception:
        logger.exception("Failed to download content for item %s", item_id)
        return None, filename, {}

    metadata: dict[str, Any] = {
        "title": item.name or filename,
        "web_url": getattr(item, "web_url", ""),
        "last_modified": str(getattr(item, "last_modified_date_time", "")),
        "created_by": _extract_created_by(item),
    }
    return content_bytes, filename, metadata


def _extract_created_by(item: Any) -> str:
    """Pull created-by display name from a driveItem safely."""
    try:
        return item.created_by.user.display_name or ""
    except AttributeError:
        return ""


# ===========================================================================
# Delta link persistence (Azure Table Storage)
# ===========================================================================

def _get_table_client() -> TableServiceClient | None:
    """Return a TableServiceClient if storage is configured, else None."""
    if not AZURE_STORAGE_CONNECTION_STRING:
        logger.warning(
            "AZURE_STORAGE_CONNECTION_STRING not set — delta links will not persist"
        )
        return None
    client = TableServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    # Ensure the table exists (idempotent)
    client.create_table_if_not_exists(DELTA_LINK_TABLE_NAME)
    return client


def _load_delta_link(
    client: TableServiceClient | None, key: str
) -> str | None:
    if client is None:
        return None
    table = client.get_table_client(DELTA_LINK_TABLE_NAME)
    try:
        entity = table.get_entity(partition_key="deltalink", row_key=key)
        return entity.get("delta_link")
    except ResourceNotFoundError:
        # No stored delta link yet — trigger a full crawl on first run
        return None


def _save_delta_link(
    client: TableServiceClient | None, key: str, link: str
) -> None:
    if client is None:
        return
    table = client.get_table_client(DELTA_LINK_TABLE_NAME)
    try:
        table.upsert_entity(
            entity={
                "PartitionKey": "deltalink",
                "RowKey": key,
                "delta_link": link,
            }
        )
    except Exception:
        logger.exception("Failed to persist delta link for key %s", key)


# ===========================================================================
# Utility helpers
# ===========================================================================

def _parse_resource_path(resource: str) -> tuple[str, str, str]:
    """Extract siteId, driveId, itemId from a Graph resource path string.

    Expected format: /sites/{siteId}/drives/{driveId}/items/{itemId}
    Returns ('', '', '') on parse failure.
    """
    import re
    match = re.search(
        r"/sites/([^/]+)/drives/([^/]+)/items/([^/]+)", resource
    )
    if match:
        return match.group(1), match.group(2), match.group(3)
    return "", "", ""


def _make_document_id(site_id: str, drive_id: str, item_id: str) -> str:
    """Stable, unique document identifier combining site + drive + item IDs."""
    return f"{site_id}_{drive_id}_{item_id}"
