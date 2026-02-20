# RES LLC HR Intranet — Deployment Runbook

> **Estimated setup time:** 2–3 hours with all prerequisites in place.

---

## Prerequisites Checklist

Before starting, confirm you have all of the following:

- [ ] **Azure subscription** — Contributor role on a resource group (or ability to create one)
- [ ] **Microsoft 365 tenant** — with one of:
  - Microsoft 365 Copilot licenses, OR
  - Power Platform Premium ($20/user) + Copilot Studio Messages Pack ($200/mo)
- [ ] **Entra ID admin** — Global Admin or Cloud App Admin (needed for Graph API consent in Step 1)
- [ ] **SharePoint Online** — document libraries containing HR docs/PDFs already in place
- [ ] **Azure CLI** — `az --version` ≥ 2.55
- [ ] **Azure Functions Core Tools v4** — `func --version` ≥ 4.0
- [ ] **Python 3.11+** — `python3 --version`
- [ ] **Node.js 18+** — `node --version` (for portal)
- [ ] **Git** — cloned this repo

---

## Step 1: Entra App Registration

This gives the Azure Function a service identity to read SharePoint documents and resolve user group memberships for permission trimming.

**Navigation:** `portal.azure.com` → **Microsoft Entra ID** → **App registrations** → **+ New registration**

1. **Name:** `RES-HR-Intranet-Sync`
2. **Supported account types:** `Accounts in this organizational directory only (Single tenant)`
3. **Redirect URI:** leave blank
4. Click **Register**

**Record these values** (you'll need them in Step 4):
- Application (client) ID
- Directory (tenant) ID

### Add API Permissions

In the app registration → **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Application permissions**:

| Permission | Type | Purpose |
|---|---|---|
| `Sites.Read.All` | Application | Read SharePoint document libraries |
| `Group.Read.All` | Application | Resolve Entra group memberships |
| `User.Read.All` | Application | Look up user identities for ACL trimming |

> **Admin consent required.** A Global Admin or Cloud App Admin must click **Grant admin consent for [tenant]**. Without this, the function will receive 403 errors from Graph API. This is a one-time step.

### Create Client Secret

In the app registration → **Certificates & secrets** → **+ New client secret**:
- Description: `res-hr-intranet-sync`
- Expires: `24 months` (set a calendar reminder to rotate)
- Click **Add** → **copy the Value immediately** (shown only once)

---

## Step 2: Clone & Configure

```bash
git clone https://github.com/Garrett-s-Apps/res-hr-copilot
cd res-hr-copilot
cp infra/main.bicepparam infra/main.bicepparam.local
```

Edit `infra/main.bicepparam.local` and fill in all required values:

| Parameter | Description | Example |
|---|---|---|
| `environmentName` | Short env label | `prod` |
| `location` | Azure region | `eastus` |
| `sharepointTenantId` | Directory (tenant) ID from Step 1 | `xxxxxxxx-...` |
| `sharepointClientId` | Application (client) ID from Step 1 | `xxxxxxxx-...` |
| `sharepointSiteUrl` | Full URL of the SharePoint site | `https://resllc.sharepoint.com/sites/HR` |
| `sharepointLibraryNames` | Comma-separated library names | `HR Documents,Contracts,Policies` |
| `allowedGroups` | Entra group IDs allowed to search | `["xxxxxxxx-...","yyyyyyyy-..."]` |
| `companyName` | Display name | `RES, LLC` |

> **Never commit** `main.bicepparam.local` — it's already in `.gitignore`.

---

## Step 3: Deploy Azure Infrastructure

```bash
az login
az account set --subscription "<your-subscription-id>"

az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters @infra/main.bicepparam.local \
  --name res-hr-intranet-$(date +%Y%m%d)
```

**Expected duration:** 8–12 minutes

**Resources created (~10):**
- Resource Group: `rg-res-hr-intranet-prod`
- Azure AI Search: `srch-res-hr-intranet-prod` (S1)
- Azure OpenAI: `oai-res-hr-intranet-prod` (text-embedding-ada-002)
- Azure AI Document Intelligence: `docintel-res-hr-intranet-prod`
- Azure Function App: `func-res-hr-intranet-prod`
- Storage Account: `streshr...`
- Key Vault: `kv-res-hr-...`
- App Insights: `appi-res-hr-...`
- Log Analytics Workspace: `log-res-hr-...`
- Managed Identity: `id-res-hr-...`

**Save the deployment outputs** — you'll need the endpoints:
```bash
az deployment sub show \
  --name res-hr-intranet-$(date +%Y%m%d) \
  --query properties.outputs
```

---

## Step 4: Seed Key Vault Secrets

```bash
KV_NAME=$(az keyvault list -g rg-res-hr-intranet-prod --query "[0].name" -o tsv)

# Entra app credentials (from Step 1)
az keyvault secret set --vault-name $KV_NAME \
  --name SharePointTenantId --value "<directory-tenant-id>"

az keyvault secret set --vault-name $KV_NAME \
  --name SharePointClientId --value "<application-client-id>"

az keyvault secret set --vault-name $KV_NAME \
  --name SharePointClientSecret --value "<client-secret-value>"

# SharePoint target
az keyvault secret set --vault-name $KV_NAME \
  --name SharePointSiteUrl --value "https://resllc.sharepoint.com/sites/HR"
```

> The Azure OpenAI and Search keys are automatically written to Key Vault by the Bicep deployment. You don't need to set them manually.

---

## Step 5: Create Search Index

```bash
# Get the search endpoint and admin key
SEARCH_ENDPOINT=$(az search service show \
  -g rg-res-hr-intranet-prod \
  -n srch-res-hr-intranet-prod \
  --query "properties.endpoint" -o tsv)

SEARCH_KEY=$(az search admin-key show \
  -g rg-res-hr-intranet-prod \
  --service-name srch-res-hr-intranet-prod \
  --query primaryKey -o tsv)

# Create venv and install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r functions/requirements.txt

# Create the search index with vector + semantic config
python scripts/create-search-index.py \
  --endpoint "$SEARCH_ENDPOINT" \
  --key "$SEARCH_KEY"
```

Expected output: `✓ Index 'res-hr-index' created with semantic config 'res-semantic-config'`

---

## Step 6: Deploy Azure Function

```bash
cd functions

# Deploy to Azure
func azure functionapp publish func-res-hr-intranet-prod --python

# Trigger initial full sync (indexes all existing SharePoint documents)
FUNC_KEY=$(az functionapp keys list \
  -g rg-res-hr-intranet-prod \
  -n func-res-hr-intranet-prod \
  --query "functionKeys.default" -o tsv)

curl -X POST \
  "https://func-res-hr-intranet-prod.azurewebsites.net/api/sync?code=$FUNC_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "full"}'
```

**Initial sync duration:** 5–20 minutes depending on number of documents and OCR complexity (scanned PDFs take longer).

Monitor progress:
```bash
az monitor app-insights query \
  --app appi-res-hr-intranet-prod \
  --analytics-query "traces | where message contains 'Processed' | order by timestamp desc | take 20"
```

After initial sync, the function runs on a 15-minute timer automatically to pick up new/changed documents.

---

## Step 7: Configure Copilot Studio Agent

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. **Create** → **New agent** → **Blank**
   - Name: `RES HR Assistant`
   - Language: English
3. **Knowledge** → **+ Add knowledge** → **Azure AI Search**
   - Endpoint: `https://srch-res-hr-intranet-prod.search.windows.net`
   - Index name: `res-hr-index`
   - Semantic configuration: `res-semantic-config`
   - Enable: **Semantic ranking**, **Vector search**
4. **Settings** → **Security** → **Authentication**
   - Select: **Authenticate with Microsoft**
   - Enable: **Require users to sign in**
   - This enables SSO — users' Entra tokens pass through so search results are automatically filtered to documents their groups can access
5. **Instructions** → paste contents of `copilot/system-prompt.md`
6. **Topics** → import each YAML file from `copilot/topics/`
7. **Test** using the built-in test panel — ask "What is the PTO policy?"
8. **Publish** → **Channels** → **Microsoft Teams**

> **Why SSO matters:** Without authentication, all 120 users see all documents regardless of permissions. With SSO + the `allowed_groups` field in the search index, each user only sees documents their Entra group membership allows.

---

## Step 8: Deploy Portal to Vercel

```bash
cd portal
npm install
cp .env.local.example .env.local
# Fill in .env.local with Azure endpoints from Step 3 outputs

# Test locally first
npm run dev
# Visit http://localhost:3000

# Deploy to Vercel
npx vercel --prod
```

**Set environment variables in Vercel dashboard** (`vercel.com/[your-team]/res-hr-portal/settings/environment-variables`):

| Variable | Value |
|---|---|
| `AZURE_SEARCH_ENDPOINT` | From deployment outputs |
| `AZURE_SEARCH_KEY` | From Step 5 |
| `AZURE_SEARCH_INDEX` | `res-hr-index` |
| `AZURE_OPENAI_ENDPOINT` | From deployment outputs |
| `AZURE_OPENAI_KEY` | From Azure portal |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` |
| `NEXT_PUBLIC_COMPANY_NAME` | `RES, LLC` |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | IT support email |

> The portal runs in **mock mode** when Azure env vars are absent — useful for demos without live credentials.

---

## Step 9: Embed in SharePoint (Optional)

To surface the Copilot Studio agent directly on the RES intranet SharePoint site:

1. In Copilot Studio → **Channels** → **Custom website** → copy the embed script
2. In SharePoint → edit the intranet home page → **+ Add web part** → **Embed**
3. Paste the embed script

Alternatively, pin the Teams app so employees access it from the Teams sidebar — no SharePoint modification needed.

---

## Cost Summary

| Service | SKU | Est. Monthly |
|---|---|---|
| Azure AI Search | S1 (1 replica, 1 partition) | ~$250 |
| Azure OpenAI | Embeddings (ada-002) + GPT-4o inference | ~$30–50 |
| Azure AI Document Intelligence | S0 (pay-per-page after free tier) | ~$10 |
| Azure Functions | Consumption plan | ~$5 |
| Storage Account | LRS, hot tier | ~$2 |
| Application Insights | Pay-per-GB | ~$3 |
| Copilot Studio | 25,000 messages/mo pack | ~$200 |
| **Total** | | **~$500–520/mo** |

**Cost levers if you need to reduce OpEx:**
- Downgrade Search to B (Basic) if <1M documents: saves ~$200/mo but loses semantic ranker
- Switch Copilot Studio to per-message billing if usage is low
- Azure OpenAI costs scale with query volume — low initial cost

---

## Troubleshooting

### "Insufficient privileges to complete the operation"
**Cause:** Admin consent not granted for the app registration.
**Fix:** A Global Admin must go to **Entra ID → App registrations → RES-HR-Intranet-Sync → API permissions** and click **Grant admin consent**.

### Function returns 403 on SharePoint API calls
**Cause:** App registration missing `Sites.Read.All` permission or admin consent not granted.
**Fix:** Verify permissions in Entra ID, re-grant consent, restart the Function App.

### Search returns 0 results
**Cause 1:** Initial sync not triggered.
**Fix:** Run the full sync curl command from Step 6.

**Cause 2:** Index schema mismatch.
**Fix:** Delete the index and re-run `create-search-index.py`, then re-sync.

### Copilot Studio "I couldn't find an answer"
**Cause 1:** SSO configured but user isn't in any `allowed_groups`.
**Fix:** Run `python scripts/validate-permissions.py --user <email>` to check group membership.

**Cause 2:** Azure AI Search knowledge source not connected.
**Fix:** In Copilot Studio → Knowledge → verify the search connection status shows green.

### OCR quality is poor / text not extracted
**Cause:** Document Intelligence not handling skewed scans well.
**Fix:** Check `functions/document_processor/ocr_processor.py` — the `readResult` uses `prebuilt-read` model which handles skew. Ensure PDFs aren't password-protected.

### Portal shows mock data in production
**Cause:** Azure env vars not set in Vercel.
**Fix:** Verify all `AZURE_*` environment variables are set in the Vercel dashboard and redeploy.

---

## Post-Deployment Verification

```bash
# Validate permissions are resolving correctly
python scripts/validate-permissions.py \
  --user employee@resllc.com \
  --search-endpoint $SEARCH_ENDPOINT \
  --search-key $SEARCH_KEY

# Check index document count
curl -H "api-key: $SEARCH_KEY" \
  "$SEARCH_ENDPOINT/indexes/res-hr-index/docs/\$count?api-version=2024-03-01-Preview"
```

Expected: document count matches number of files in SharePoint library × average chunks per document.
