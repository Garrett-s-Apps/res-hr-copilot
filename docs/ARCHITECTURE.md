# RES LLC HR Intranet — Architecture

## Overview

The RES HR Intranet is an AI-powered knowledge base and Q&A system for ~120 employees. It allows staff to ask natural language questions about HR policies, contracts, and procedures, and receive accurate answers with source citations — respecting each user's document access permissions.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EMPLOYEE DEVICES                                 │
│                                                                             │
│  ┌─────────────────────┐        ┌─────────────────────────────────────┐    │
│  │   Microsoft Teams   │        │    RES Connect Portal (Vercel)      │    │
│  │                     │        │    Next.js intranet frontend         │    │
│  │  [Copilot Studio    │        │    - Homepage / announcements        │    │
│  │   chat widget]      │        │    - Semantic search UI              │    │
│  │                     │        │    - AI chat with citations          │    │
│  └──────────┬──────────┘        └──────────────┬──────────────────────┘    │
│             │ SSO (Entra ID)                    │ REST                       │
└─────────────┼───────────────────────────────────┼────────────────────────── ┘
              │                                   │
              ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MICROSOFT AZURE                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    QUERY LAYER                                       │   │
│  │                                                                      │   │
│  │  ┌──────────────────────┐     ┌──────────────────────────────────┐  │   │
│  │  │   Copilot Studio     │     │   Next.js API Routes             │  │   │
│  │  │   Standalone Agent   │     │   /api/search  /api/chat         │  │   │
│  │  │                      │     │                                  │  │   │
│  │  │  - System prompt     │     │  - Proxies to Azure Search       │  │   │
│  │  │  - Greeting topic    │     │  - Streams GPT-4o responses      │  │   │
│  │  │  - Fallback topic    │     │  - Returns source citations      │  │   │
│  │  │  - Escalation topic  │     │                                  │  │   │
│  │  │  - Feedback topic    │     └──────────────┬───────────────────┘  │   │
│  │  └──────────┬───────────┘                    │                      │   │
│  │             │                                │                      │   │
│  │             └────────────────┬───────────────┘                      │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │                 ┌────────────────────────┐                           │   │
│  │                 │   Azure AI Search (S1) │                           │   │
│  │                 │                        │                           │   │
│  │                 │  res-hr-index          │                           │   │
│  │                 │  ├── id (key)          │                           │   │
│  │                 │  ├── content (text)    │                           │   │
│  │                 │  ├── content_vector    │◄── HNSW cosine            │   │
│  │                 │  │   (1536-dim)        │    1536-dim               │   │
│  │                 │  ├── source_url        │                           │   │
│  │                 │  ├── page_number       │                           │   │
│  │                 │  ├── department        │                           │   │
│  │                 │  ├── doc_type          │                           │   │
│  │                 │  └── allowed_groups[]  │◄── permission trimming    │   │
│  │                 │                        │                           │   │
│  │                 │  Semantic ranker:      │                           │   │
│  │                 │  res-semantic-config   │                           │   │
│  │                 └────────────────────────┘                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INGESTION LAYER                                   │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │              Azure Function App (Python 3.11)                 │  │   │
│  │  │              Consumption Plan                                  │  │   │
│  │  │                                                                │  │   │
│  │  │  Triggers:                                                     │  │   │
│  │  │  ├── Timer (every 15 min) ──► delta sync                      │  │   │
│  │  │  └── HTTP webhook ──────────► full sync / manual trigger      │  │   │
│  │  │                                                                │  │   │
│  │  │  Pipeline per document:                                        │  │   │
│  │  │  1. acl_resolver.py  ──► fetch user groups from Graph API     │  │   │
│  │  │  2. ocr_processor.py ──► Doc Intelligence (prebuilt-read)     │  │   │
│  │  │     (handles skewed/scanned PDFs, extracts text + layout)     │  │   │
│  │  │  3. chunker.py       ──► split into ~512-token overlapping    │  │   │
│  │  │     chunks with metadata (page, section, doc title)           │  │   │
│  │  │  4. embedder.py      ──► Azure OpenAI text-embedding-ada-002  │  │   │
│  │  │     (1536-dim vectors per chunk)                              │  │   │
│  │  │  5. index_pusher.py  ──► upsert chunks into Azure AI Search   │  │   │
│  │  │     with allowed_groups[] from step 1                         │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────────┐ │
│  │   Key Vault      │  │  Azure OpenAI    │  │  App Insights + Log       │ │
│  │                  │  │                  │  │  Analytics                │ │
│  │  All secrets:    │  │  - ada-002       │  │                           │ │
│  │  SP client creds │  │    (embeddings)  │  │  - Function traces        │ │
│  │  Search keys     │  │  - gpt-4o        │  │  - Search query logs      │ │
│  │  OAI keys        │  │    (chat)        │  │  - Error alerting         │ │
│  └──────────────────┘  └──────────────────┘  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              │ Microsoft Graph API (app identity)
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MICROSOFT 365                                         │
│                                                                             │
│  ┌──────────────────────────────────┐   ┌───────────────────────────────┐  │
│  │     SharePoint Online            │   │     Microsoft Entra ID        │  │
│  │                                  │   │                               │  │
│  │  Document Libraries:             │   │  - User identities            │  │
│  │  ├── HR Documents                │   │  - Security groups            │  │
│  │  ├── Contracts (scanned PDFs)    │   │  - App registration           │  │
│  │  ├── Policies                    │   │    RES-HR-Intranet-Sync       │  │
│  │  └── Procedures                  │   │  - SSO for Copilot Studio     │  │
│  │                                  │   │                               │  │
│  │  Change tracking via             │   │  Permissions:                 │  │
│  │  MS Graph delta queries          │   │  Sites.Read.All               │  │
│  │  (15-min polling)                │   │  Group.Read.All               │  │
│  │                                  │   │  User.Read.All                │  │
│  └──────────────────────────────────┘   └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Ingestion (background, continuous)

```
SharePoint document changed/added
        │
        ▼ (15-min timer or webhook)
Azure Function triggered
        │
        ├─► Graph API: resolve document's site permissions → Entra group IDs
        │
        ├─► Document Intelligence: extract text from PDF
        │       └── prebuilt-read model handles skewed/imaged scans
        │
        ├─► Chunker: split text into 512-token overlapping chunks
        │       └── preserves page number, section heading, doc metadata
        │
        ├─► Azure OpenAI (ada-002): generate 1536-dim embedding per chunk
        │
        └─► Azure AI Search: upsert chunk with vector + allowed_groups[]
```

### Query (real-time, per user message)

```
User types question in Teams or Portal
        │
        ▼
Copilot Studio / Next.js API
        │
        ├─► User's Entra token passed to Azure AI Search
        │
        ├─► Search request: hybrid query (keyword + vector)
        │       ├── Vector: embed question → cosine similarity vs. index
        │       ├── Keyword: BM25 full-text
        │       ├── Semantic reranker: reorders top-50 by semantic relevance
        │       └── Security filter: allowed_groups[] ∩ user's groups
        │
        ├─► Top-K results returned (chunk text + source_url + page_number)
        │
        ├─► Azure OpenAI GPT-4o: grounded response using retrieved chunks
        │       └── system prompt instructs: cite sources, stay grounded
        │
        └─► Response with inline citations delivered to user
                └── each citation: [Doc Title, page N, link to SharePoint]
```

---

## Permission Trimming

The `allowed_groups[]` field is the core security mechanism:

1. When a document is indexed, the function resolves which Entra groups have access to that SharePoint library/file
2. Those group IDs are stored in `allowed_groups[]` on every chunk from that document
3. At query time, Azure AI Search automatically filters results to chunks where `allowed_groups` intersects with the querying user's group memberships
4. Users never see documents their SharePoint permissions don't allow — even if the AI "knows" about them

SharePoint permissions are the source of truth, synced into the index at ingest time. No separate permission database needed.

---

## Infrastructure (Bicep IaC)

All Azure resources are declared in `infra/`:

```
infra/
├── main.bicep              # Orchestrator — passes params to all modules
├── main.bicepparam         # Parameter template (copy to .local, never commit)
└── modules/
    ├── managed-identity.bicep  # User-assigned identity for Function → Key Vault
    ├── storage.bicep            # Blob storage for Function state + doc staging
    ├── key-vault.bicep          # All secrets, RBAC access for managed identity
    ├── monitoring.bicep         # App Insights + Log Analytics workspace
    ├── search.bicep             # Azure AI Search S1 + semantic config
    ├── openai.bicep             # Azure OpenAI (ada-002 + gpt-4o deployments)
    ├── doc-intelligence.bicep   # Azure AI Document Intelligence S0
    └── function-app.bicep       # Python 3.11 Consumption, Key Vault refs
```

`az deployment sub create` deploys everything in one command (~10 minutes).

---

## Technology Choices & Rationale

| Decision | Choice | Why |
|---|---|---|
| Search | Azure AI Search S1 | Native SharePoint connector, semantic ranker, vector HNSW, security trimming built-in |
| Embeddings | text-embedding-ada-002 | Best cost/quality ratio, 1536-dim, widely supported |
| Chat | GPT-4o | Best instruction-following for grounded RAG with citations |
| OCR | Azure AI Document Intelligence prebuilt-read | Handles skewed/imaged scans, extracts layout, paragraph-aware |
| Copilot surface | Copilot Studio | Zero Teams integration work, SSO out-of-box, no custom auth code |
| Portal | Next.js + Vercel | Fast, deployable without Azure, mock mode for demos |
| IaC | Bicep | Native Azure, no Terraform license, readable, idempotent |
| Sync | Azure Functions Consumption | No idle cost, scales to zero, 15-min timer sufficient for HR docs |

---

## Key Design Constraints

- **OpEx target ~$500/mo** — S1 Search is the dominant cost; downgrade to Basic if doc count stays low
- **No custom auth code** — Copilot Studio SSO + Azure Search security trimming handles access control entirely
- **One agent, not many** — single Copilot Studio agent with topic routing vs. multi-agent complexity
- **Declarative infra** — Bicep ensures repeatable deployments; no click-ops
- **OCR for scanned contracts** — hundreds of imaged PDFs, potentially askew; Document Intelligence handles this without preprocessing
