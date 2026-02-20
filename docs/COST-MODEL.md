# Cost Model — RES HR Copilot

Version: 1.0
Last updated: 2026-02-20

---

## Assumptions

| Parameter | Value | Basis |
|---|---|---|
| Active employees | 500 | RES, LLC headcount |
| Daily active users (DAU) | 15% of employees | Conservative enterprise copilot adoption |
| Queries per DAU per day | 3 | Avg across HR use cases |
| Total queries per day | ~225 | 500 × 15% × 3 |
| Total queries per month | ~6,750 | 225 × 30 |
| Avg tokens per query (input) | 2,000 | System prompt + 5 chunks × ~300 tokens + user question |
| Avg tokens per query (output) | 400 | Typical cited HR answer |
| HR documents in SharePoint | 200 | Policies, handbooks, guides |
| Avg pages per document | 8 | Mix of 1-page policies and 50-page handbooks |
| Avg chunk size | 512 tokens | 2000 chars ÷ 4 chars/token |
| Total indexed chunks | ~3,200 | 200 docs × 8 pages × ~2 chunks/page |
| Embedding dimensions | 1,536 | text-embedding-3-small |
| Index size (vectors only) | ~24 MB | 3,200 chunks × 1,536 floats × 4 bytes |
| Indexer runs per day | 6 | Every 4 hours |
| Documents re-indexed per run | ~10 | Average daily SharePoint modifications |

---

## Monthly Cost Breakdown

### Azure AI Search — Standard S1

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Search unit (1 partition, 1 replica) | 1 SU | $245.00/mo | $245.00 |
| Semantic ranking calls | 6,750 queries | $1.00 / 1,000 | $6.75 |
| **Subtotal** | | | **$251.75** |

Notes:
- S1 includes 50 GB storage and 10,000 documents per index partition. Well within limits at current scale.
- Add a second replica ($245/mo) for production SLA of 99.9% query availability.

### Azure OpenAI — Embeddings (text-embedding-3-small)

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Index-time embeddings (initial) | 3,200 chunks × 512 tokens | $0.02 / 1M tokens | $0.03 (one-time) |
| Index-time embeddings (incremental) | 300 chunks/mo × 512 tokens | $0.02 / 1M tokens | $0.003/mo |
| **Subtotal** | | | **~$0.01/mo** |

Notes: Embedding cost is negligible at this document scale. Re-prices significantly only above 1M chunks.

### Azure OpenAI — Completions (GPT-4o)

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Input tokens | 6,750 queries × 2,000 tokens | $2.50 / 1M tokens | $33.75 |
| Output tokens | 6,750 queries × 400 tokens | $10.00 / 1M tokens | $27.00 |
| **Subtotal** | | | **$60.75** |

Notes: GPT-4o pricing as of 2026-02. Verify current pricing at https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/

### Azure Functions — Consumption Plan

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Executions | ~5,400/mo (6 runs/day × 30 days × ~30 fn calls/run) | $0.20 / 1M executions | $0.001 |
| Execution time | ~180 GB-s/mo | $0.000016 / GB-s | $0.003 |
| **Subtotal** | | | **~$1.00** |

Notes: Functions cost is effectively zero at this scale. Minimum charge of ~$1/mo applies.

### Azure Document Intelligence — Standard S0

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Pages analyzed (initial full index) | 1,600 pages (scanned subset ~25%) | $1.50 / 1,000 pages | $2.40 (one-time) |
| Pages analyzed (incremental) | ~60 pages/mo | $1.50 / 1,000 pages | $0.09/mo |
| **Subtotal** | | | **~$2.00/mo** |

Notes: Only scanned/image-heavy PDFs route to Document Intelligence. Text-native PDFs use PyMuPDF at zero cost.

### Application Insights

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| Data ingestion | ~500 MB/mo (conversation logs + custom events) | $2.30 / GB | $1.15 |
| Data retention (90 days default) | Included | — | $0.00 |
| **Subtotal** | | | **~$1.15** |

### Azure Storage (SharePoint indexer state)

| Item | Quantity | Unit Price | Monthly Cost |
|---|---|---|---|
| LRS blob storage | ~1 GB (indexer state, temp files) | $0.018 / GB | $0.02 |
| **Subtotal** | | | **~$0.02** |

---

## Total Monthly Cost

| Component | Monthly Cost |
|---|---|
| Azure AI Search S1 | $251.75 |
| Azure OpenAI Embeddings | $0.01 |
| Azure OpenAI GPT-4o | $60.75 |
| Azure Functions | $1.00 |
| Azure Document Intelligence | $2.00 |
| Application Insights | $1.15 |
| Azure Storage | $0.02 |
| **Total** | **$316.68** |
| **Per employee per month** | **$0.63** |
| **Per query** | **$0.047** |

---

## Cost at Scale

| Scenario | DAU | Queries/mo | Est. Monthly Cost |
|---|---|---|---|
| Pilot (50 users) | 50 | 450 | ~$260 (search dominates) |
| Current (500 users) | 75 | 6,750 | ~$317 |
| Growth (2,000 users) | 300 | 27,000 | ~$520 |
| Enterprise (10,000 users) | 1,500 | 135,000 | ~$1,650 |

Search cost is largely fixed (infrastructure). GPT-4o cost scales linearly with query volume.

---

## Optimization Levers

### High Impact

| Lever | Savings | Trade-off |
|---|---|---|
| Switch completions to GPT-4o-mini | ~60% on completion costs (~$36/mo saved) | Slightly lower answer quality on complex multi-part questions |
| Cache answers for identical queries | 20–40% on completion costs | Requires Redis or similar; stale cache risk on policy updates |
| Reduce retrieved chunks from 5 to 3 | ~40% on input tokens (~$13/mo saved) | May miss relevant context for multi-document questions |
| Shorten system prompt by 30% | ~15% on input tokens (~$5/mo saved) | Requires careful editing to preserve all guardrails |

### Medium Impact

| Lever | Savings | Trade-off |
|---|---|---|
| Downgrade Search to Basic (if <2M docs) | ~$180/mo | Loses semantic ranking; degrades answer quality |
| Reduce indexer frequency to 2x/day | Minimal ($0) | Increases indexing lag from 4h to 12h |
| Use text-embedding-3-large instead of small | -$0.10/mo (more expensive) | Marginally better retrieval recall; not worth the cost |

### Low Impact

| Lever | Savings | Trade-off |
|---|---|---|
| Move Functions to Premium | -$150/mo (more expensive) | Eliminates cold start latency; required if OBO function sees >10s cold starts |
| Enable App Insights sampling at 10% | ~$1/mo | Reduces telemetry fidelity; feedback events should be excluded from sampling |

---

## Cost Monitoring

Set up Azure Cost Management alerts:

```bash
# Alert if monthly forecast exceeds $500
az consumption budget create \
  --resource-group rg-res-hr-copilot \
  --budget-name hr-copilot-budget \
  --amount 500 \
  --time-grain Monthly \
  --start-date 2026-03-01 \
  --end-date 2027-03-01 \
  --category Cost \
  --notifications '[{"enabled":true,"operator":"GreaterThan","threshold":80,"contactEmails":["platform@resllc.com"],"thresholdType":"Forecasted"}]'
```

Track per-component costs using resource tags:

```bash
az group update \
  --name rg-res-hr-copilot \
  --tags project=hr-copilot environment=prod cost-center=HR-IT
```
