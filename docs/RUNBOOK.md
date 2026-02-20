# Runbook — RES HR Copilot

Operational procedures for the platform team. For architecture context see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Re-index All Documents from Scratch

Use this when the index schema changes, after a major policy update batch, or to recover from index corruption.

```bash
# Step 1: Delete the existing index (this removes all documents)
az search index delete \
  --name hr-documents \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  --yes

# Step 2: Re-create the index from the schema definition
python3 scripts/create-search-index.py

# Step 3: Reset the indexer so it re-crawls all SharePoint documents
az search indexer reset \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot

# Step 4: Trigger an immediate indexer run
az search indexer run \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot

# Step 5: Monitor progress
az search indexer show \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  --query "lastResult"
```

Expected duration: 5–30 minutes depending on document count. The indexer processes documents in parallel batches of 10.

---

## 2. Add a New SharePoint Library

When HR uploads documents to a new SharePoint library that should be included in search.

**Step 1: Update the indexer data source**

```bash
# Get the current data source definition
az search datasource show \
  --name hr-sharepoint-datasource \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  > datasource.json

# Edit datasource.json to add the new library path under "container.query"
# Example: add "/sites/HR/Shared Documents/NewLibrary" to the query path list

# Update the data source
az search datasource create-or-update \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  --name hr-sharepoint-datasource \
  --body @datasource.json
```

**Step 2: Re-run the indexer**

```bash
az search indexer run \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot
```

**Step 3: Verify new documents appear**

```bash
az search index documents count \
  --index-name hr-documents \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot
```

**Step 4: Validate permissions on a document from the new library**

```bash
python3 scripts/validate-permissions.py \
  --user <test-user-entra-oid> \
  --expected-docs "New Library Document Title"
```

---

## 3. Update the System Prompt

The system prompt defines the agent's behavior, scope, tone, and fallback responses.

**Step 1: Edit the source file**

```bash
# Edit with your preferred editor
code copilot/system-prompt.md
```

**Step 2: Copy updated content into Copilot Studio**

1. Open [https://copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Select the **RES HR Assistant** agent
3. Click **Settings** → **Agent details**
4. Paste the updated content into the **Instructions** field
5. Click **Save**

**Step 3: Publish the updated agent**

1. Click **Publish** in the top nav
2. Click **Publish** on the confirmation dialog
3. Propagation to Teams takes 2–5 minutes

**Step 4: Test the change**

Send a test message that exercises the updated behavior. For fallback or citation format changes, test with a known HR question and verify the response format matches expectations.

---

## 4. Check Indexing Lag

Indexing lag is the time between a document being modified in SharePoint and appearing in search results.

**Using Azure Portal**

1. Navigate to your Azure AI Search resource
2. Go to **Indexers** → **hr-indexer**
3. Review **Last run status**, **Items processed**, **Items failed**, and **Last run time**

**Using Azure CLI**

```bash
az search indexer show \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  --query "{status: lastResult.status, itemsProcessed: lastResult.itemsProcessed, itemsFailed: lastResult.itemsFailed, startTime: lastResult.startTime, endTime: lastResult.endTime}"
```

**Using Application Insights**

Query for indexer run metrics:

```kusto
customEvents
| where name == "indexer_run_complete"
| project timestamp, documents_processed = tolong(customDimensions.documents_processed), duration_seconds = tolong(customDimensions.duration_seconds)
| order by timestamp desc
| take 20
```

Target SLA: documents should appear in search within 4 hours of modification in SharePoint (one indexer cycle).

---

## 5. Common Issues and Resolutions

### OCR Failures

**Symptom:** Documents from a specific SharePoint library return empty or garbled content in search results.

**Diagnosis:**
```bash
# Check for failed items in the indexer run
az search indexer show \
  --name hr-indexer \
  --service-name <search-service-name> \
  --resource-group rg-res-hr-copilot \
  --query "lastResult.errors"
```

**Resolution:**
- If error is `DocumentIntelligenceQuotaExceeded`: increase Document Intelligence tier or throttle the indexer batch size.
- If error is `PageExtractionFailed` on a specific file: download the file and test with `python3 -c "from scripts.ocr_test import test_file; test_file('<path>')"`.
- If the file is password-protected: coordinate with the document owner to remove the password before re-indexing.

---

### Authentication Errors (Users Cannot Sign In)

**Symptom:** Users see a sign-in loop or "We couldn't sign you in" in the Teams bot.

**Diagnosis:**
1. In Azure Portal, open the Entra ID app registration
2. Check **Authentication** → **Redirect URIs** — the Copilot Studio callback URI must be present
3. Check **API permissions** — `User.Read` must be granted and admin-consented

**Resolution:**
- Add the missing redirect URI (format: `https://token.botframework.com/.auth/web/redirect`)
- Grant admin consent for API permissions
- Verify the client secret has not expired (check **Certificates & secrets** → expiry date)

---

### Latency Spikes (P95 > 5 seconds)

**Symptom:** Employee queries take more than 5 seconds to return an answer.

**Diagnosis:**
```kusto
-- Application Insights KQL
requests
| where name == "CopilotQueryHandler"
| summarize p50=percentile(duration, 50), p95=percentile(duration, 95), p99=percentile(duration, 99) by bin(timestamp, 1h)
| order by timestamp desc
```

**Resolution:**
- If search latency is the bottleneck: add a replica to the Azure AI Search service (increases query throughput and reduces latency).
- If GPT-4o is the bottleneck: check Azure OpenAI token-per-minute quota in Azure Portal → Deployments. Request a quota increase if needed.
- If Functions cold start is the bottleneck (OBO token exchange): switch from Consumption to Premium plan to eliminate cold starts.

---

### Security Trimming Not Working (User Sees Unauthorized Documents)

**Symptom:** `scripts/validate-permissions.py` reports FAIL for a denied document.

**Diagnosis:**
1. Query the index directly for the document:
   ```bash
   # Using Azure Portal search explorer with admin key
   # Filter: search=<document title>, select=title,allowed_groups
   ```
2. Verify the `allowed_groups` field contains only the correct group OIDs.
3. Check whether the indexer ran after the SharePoint permission change.

**Resolution:**
- If `allowed_groups` is empty: the AclResolver may have failed for this document. Check Function logs in App Insights for `AclResolutionFailed` events.
- If `allowed_groups` contains incorrect OIDs: clear the document from the index and re-index it:
  ```bash
  # Delete specific document by document_id
  az search index documents delete \
    --index-name hr-documents \
    --service-name <search-service-name> \
    --resource-group rg-res-hr-copilot \
    --key-field id \
    --key-value <chunk-id>
  ```
- Run `scripts/validate-permissions.py` again after re-indexing to confirm the fix.

---

### Index Quota Exceeded

**Symptom:** Indexer fails with `IndexStorageQuotaExceeded`.

**Resolution:**
1. Check current index size:
   ```bash
   az search index show \
     --name hr-documents \
     --service-name <search-service-name> \
     --resource-group rg-res-hr-copilot \
     --query "statistics"
   ```
2. If approaching the 50 GB S1 limit, either:
   - Upgrade to S2 (250 GB): `az search service update --sku Standard2`
   - Archive and delete documents older than 3 years that are no longer policy-relevant
