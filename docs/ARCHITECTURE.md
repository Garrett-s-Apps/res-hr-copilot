# Architecture — RES HR Copilot

Version: 1.0
Last updated: 2026-02-20

---

## Overview

The RES HR Copilot is a retrieval-augmented generation (RAG) system that answers employee HR questions using RES's official SharePoint documentation. It is composed of two independently deployable pipelines:

1. **Indexing pipeline** — Crawls SharePoint, extracts text (with OCR for scanned documents), chunks content, generates embeddings, resolves access control, and upserts records into Azure AI Search.
2. **Query pipeline** — Accepts employee questions via Copilot Studio, applies security trimming, retrieves the top-K semantically relevant chunks, and synthesizes a cited answer using GPT-4o.

---

## Components

### 1. Microsoft Copilot Studio (Agent Layer)

The user-facing agent. Employees interact via Microsoft Teams or an embedded SharePoint panel.

- **Authentication:** Entra ID single-sign-on. User identity is passed to every search query via the `allowed_groups` security filter. Employees never see documents they lack SharePoint access to.
- **System prompt:** Defines scope, citation requirements, fallback behavior, and sensitive-topic handling. Located at `copilot/system-prompt.md`.
- **Topics:**
  - `greeting` — Welcome message and starter suggestions.
  - `fallback` — Generative answers using Azure AI Search as knowledge source. Fires for all unrecognized input.
  - `escalation` — Routes to human HR team with contact info and App Insights logging.
  - `feedback` — Adaptive card (thumbs up/down + comment) emitted after every generative answer.
- **Knowledge source:** Azure AI Search index `hr-documents` with semantic ranking and security trimming enabled.

### 2. Azure AI Search (Retrieval Layer)

Stores chunked HR document content and provides hybrid (keyword + vector) retrieval with semantic reranking.

- **Index:** `hr-documents` (defined in `infra/search-config/index-schema.json`)
- **Vector field:** `chunk_vector` — 1536-dimensional embeddings from `text-embedding-3-small`, stored as HNSW with cosine similarity.
- **Semantic configuration:** `hr-semantic-config` — uses `title` as the title field, `chunk_content` as the primary content field, and `category`/`department`/`section_heading` as keyword fields for reranking.
- **Security trimming:** The `allowed_groups` field (`Collection(Edm.String)`) stores Entra group OIDs. Every query applies a filter: `allowed_groups/any(g: g eq '<user_group_oid>')`. Users only receive chunks their SharePoint permissions allow.
- **Scoring profile:** `freshness-boost` — linearly boosts recently modified documents over a 365-day window with a 2× multiplier, keeping policy updates surfaced ahead of stale content.

### 3. Azure OpenAI (Generation Layer)

- **Embeddings:** `text-embedding-3-small` (1536 dimensions). Used both at index time (via the AI Search skillset integrated vectorizer) and optionally at query time.
- **Completions:** GPT-4o. Synthesizes answers strictly grounded on retrieved chunks. The Copilot Studio system prompt explicitly prohibits hallucination and requires source citations.

### 4. Azure Functions (Indexing Pipeline)

Serverless functions that orchestrate the indexing pipeline on a timer trigger (e.g., every 4 hours) or on-demand via HTTP.

**Function: `IngestSharePoint`**
1. Enumerate new/modified files from SharePoint using the Microsoft Graph delta API.
2. Download file bytes.
3. Route to `OcrProcessor` (native text via PyMuPDF, or scanned via Document Intelligence).
4. Pass extracted text to `DocumentChunker` (2000-char max, 500-char overlap).
5. Resolve ACLs via `AclResolver` (Graph API → Entra group OIDs).
6. Upsert chunks into Azure AI Search with all metadata and security fields.

**Function: `CleanDeletedDocuments`**
- Detects SharePoint items deleted since last run.
- Issues delete operations against Azure AI Search by `document_id`.

### 5. Azure Document Intelligence (OCR Layer)

Used for scanned or image-heavy PDFs where PyMuPDF extracts fewer than 100 characters per page.

- **Model:** `prebuilt-read` — optimized for dense text extraction from business documents.
- **Output:** Per-page text with line-level confidence, assembled into the same `PageResult` format as native extraction so downstream processing is uniform.

### 6. Microsoft Graph API (ACL Resolution)

`AclResolver` calls Graph to:
- Retrieve item-level and inherited SharePoint permissions.
- Expand user permissions to the user's transitive group memberships.
- Return a deduplicated list of Entra group OIDs for the `allowed_groups` field.

Results are cached in-memory per function invocation to avoid redundant API calls when the same user or group appears across multiple documents.

### 7. Application Insights (Observability)

All telemetry is routed to a single Application Insights workspace.

| Custom Event | Emitted By | Key Properties |
|---|---|---|
| `hr_copilot_feedback` | Feedback topic | userId, feedbackValue, feedbackComment, queryText |
| `hr_copilot_escalation` | Escalation topic | userId, timestamp, channel, conversationId |

Standard Copilot Studio conversation logs are also forwarded (enable in Copilot Studio → Settings → Advanced → Application Insights).

Recommended dashboards:
- Feedback ratio (positive / total) over time
- Escalation rate per day
- Search latency p50/p95
- Indexer run duration and document counts

---

## Data Flow

### Query Flow (real-time)

```
Employee message
    │
    ▼
Copilot Studio
    │ 1. Authenticate user (Entra ID)
    │ 2. Resolve user's group OIDs (via OBO function or token claims)
    ▼
Azure AI Search
    │ 3. Hybrid search: BM25 keyword + HNSW vector (text-embedding-3-small)
    │ 4. Security filter: allowed_groups/any(g: g eq '<oid>')
    │ 5. Semantic reranking (hr-semantic-config)
    │ 6. Return top-5 chunks with titles, URLs, page numbers
    ▼
GPT-4o (via Copilot Studio generative answers)
    │ 7. Synthesize answer grounded on retrieved chunks
    │ 8. Format with Sources section
    ▼
Employee receives answer + citations
    │
    ▼
Feedback adaptive card
    │ 9. Log hr_copilot_feedback event to App Insights
```

### Indexing Flow (async, timer-triggered)

```
SharePoint Online
    │ Graph delta API (new/modified/deleted files)
    ▼
Azure Function: IngestSharePoint
    │
    ├─► OcrProcessor
    │       ├─ PyMuPDF (text-native PDFs)
    │       └─ Document Intelligence (scanned PDFs, images)
    │
    ├─► DocumentChunker
    │       └─ 2000-char chunks, 500-char overlap, section heading extraction
    │
    ├─► AclResolver
    │       └─ Graph API → Entra group OIDs → allowed_groups[]
    │
    └─► Azure AI Search
            └─ Upsert chunks with vectors (integrated vectorizer)
                or pre-computed embeddings
```

---

## Security Model

- **Authentication:** All Copilot Studio sessions require Entra ID sign-in. Unauthenticated requests are rejected.
- **Authorization:** Security trimming on every search query ensures users only see documents their SharePoint ACLs permit. The filter is applied server-side in Azure AI Search and cannot be bypassed by the client.
- **Secrets:** All credentials stored in Azure Key Vault. Function apps reference Key Vault via managed identity — no secrets in code or environment variables.
- **Network:** Azure AI Search and Azure OpenAI are accessed over private endpoints where possible. Functions run in a VNet-integrated App Service Plan for production.
- **Data residency:** All resources deployed to the same Azure region (default: eastus2) to keep HR data within the configured geography.

---

## Scalability

- Azure AI Search Standard S1 supports up to 50 GB of index storage and 3 replicas for query HA.
- The Functions consumption plan scales to zero when idle and scales out automatically under indexing load.
- The HNSW index supports sub-100ms p95 vector query latency at the current document scale (<100K chunks).
- If the corpus grows beyond 1M chunks, upgrade to S2 and consider index partitioning by department or document category.
