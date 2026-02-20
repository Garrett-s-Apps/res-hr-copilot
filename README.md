# RES HR Copilot

An AI-powered HR assistant for RES, LLC employees. Employees ask natural language questions about HR policies, benefits, onboarding, and procedures. The assistant retrieves answers from official HR documentation in SharePoint and returns grounded, cited responses — no hallucination, no guessing.

Built on Microsoft Copilot Studio, Azure AI Search (vector + semantic), Azure OpenAI, and SharePoint Online.

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Python | 3.11+ |
| Azure CLI | Latest (`az --version`) |
| Azure Functions Core Tools | v4 (`func --version`) |
| Microsoft 365 tenant | With Copilot Studio license |
| Azure subscription | Contributor access to target resource group |
| Entra ID app registration | For user authentication and Graph API access |

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/resllc/res-hr-copilot.git
cd res-hr-copilot

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your Azure resource details

# 3. Deploy infrastructure and create the search index
chmod +x scripts/deploy.sh
./scripts/deploy.sh --resource-group rg-res-hr-copilot --location eastus2 --env prod

# 4. Complete Copilot Studio setup
# Follow the step-by-step guide in copilot/README.md
open copilot/README.md
```

---

## Architecture Overview

```
 Employees (Teams / SharePoint)
          │
          ▼
  ┌───────────────────┐
  │  Copilot Studio   │  ← System prompt, topics, Entra ID auth
  │  (HR Assistant)   │
  └────────┬──────────┘
           │  Semantic search query + security filter
           ▼
  ┌───────────────────┐
  │  Azure AI Search  │  ← hr-documents index
  │  (Vector + BM25)  │     HNSW cosine, text-embedding-3-small
  └────────┬──────────┘     allowed_groups security trimming
           │  Matched chunks with citations
           ▼
  ┌───────────────────┐
  │  Azure OpenAI     │  ← GPT-4o for answer synthesis
  │  (GPT-4o)         │     grounded on retrieved chunks only
  └───────────────────┘

  ┌───────────────────────────────────────────────┐
  │  Indexing Pipeline (Azure Functions)          │
  │                                               │
  │  SharePoint Online ──► Document Intelligence  │
  │  (HR documents)         (OCR for scanned PDFs)│
  │                     ──► DocumentChunker       │
  │                         (2000-char chunks,    │
  │                          500-char overlap)    │
  │                     ──► AclResolver           │
  │                         (Graph API → group    │
  │                          OIDs for ACL field)  │
  │                     ──► Azure AI Search       │
  │                         (upsert with vectors) │
  └───────────────────────────────────────────────┘

  ┌────────────────────────────────┐
  │  Observability                 │
  │  Application Insights          │
  │  - hr_copilot_feedback events  │
  │  - hr_copilot_escalation events│
  │  - Indexer lag metrics         │
  └────────────────────────────────┘
```

---

## Cost Estimate

Assumptions: 500 employees, 50 queries/day average, 10 documents/query retrieved, ~2000 indexed HR document chunks.

| Component | SKU / Tier | Est. Monthly Cost |
|---|---|---|
| Azure AI Search | Standard S1 | ~$250 |
| Azure OpenAI — Embeddings | text-embedding-3-small | ~$5 |
| Azure OpenAI — Completions | GPT-4o (input + output) | ~$180 |
| Azure Functions | Consumption plan | ~$5 |
| Azure Document Intelligence | S0 (500 pages/mo) | ~$8 |
| Application Insights | Pay-as-you-go | ~$10 |
| Storage (SharePoint indexer) | LRS | ~$2 |
| **Total** | | **~$460/mo** |

See [docs/COST-MODEL.md](docs/COST-MODEL.md) for full assumptions and optimization levers.

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Documentation

| Document | Description |
|---|---|
| [copilot/README.md](copilot/README.md) | Copilot Studio setup guide (step-by-step) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture with component details |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operational runbook — re-indexing, troubleshooting |
| [docs/COST-MODEL.md](docs/COST-MODEL.md) | Detailed cost model with optimization options |
| [infra/search-config/](infra/search-config/) | Azure AI Search index and skillset definitions |

---

## Contributing

All changes must pass:
- `ruff check src/` (linting)
- `mypy src/` (type checking)
- `pytest tests/` (all tests green)

Branch from `main`, open a PR, and request review from the platform team.
