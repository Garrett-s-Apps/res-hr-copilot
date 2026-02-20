# RES LLC HR Intranet — Deployment Runbook

**Target environment:** Microsoft 365 + Azure tenant
**Estimated total setup time:** 2–3 hours with all prerequisites in place
**Last updated:** 2026-02-20

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1 — Entra App Registration](#step-1--entra-app-registration)
3. [Step 2 — Clone and Configure](#step-2--clone-and-configure)
4. [Step 3 — Deploy Azure Infrastructure](#step-3--deploy-azure-infrastructure)
5. [Step 4 — Seed Key Vault Secrets](#step-4--seed-key-vault-secrets)
6. [Step 5 — Create Search Index](#step-5--create-search-index)
7. [Step 6 — Deploy Azure Function](#step-6--deploy-azure-function)
8. [Step 7 — Configure Copilot Studio Agent](#step-7--configure-copilot-studio-agent)
9. [Step 8 — Deploy Portal to Vercel](#step-8--deploy-portal-to-vercel)
10. [Step 9 — Embed in SharePoint (Optional)](#step-9--embed-in-sharepoint-optional)
11. [Step 10 — Validate Permissions](#step-10--validate-permissions)
12. [Cost Summary](#cost-summary)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Complete every item before starting. Missing prerequisites are the most common cause of failed deployments.

**Azure**
- [ ] Azure subscription with **Contributor** role on the target resource group, or **Owner** on the subscription
- [ ] Azure CLI installed and authenticated — `az login` succeeds, `az account show` returns the correct subscription
- [ ] Azure Functions Core Tools v4 installed — `func --version` returns `4.x.x`
  ```bash
  npm install -g azure-functions-core-tools@4 --unsafe-perm true
  ```
- [ ] Python 3.11 or higher — `python3 --version` confirms
- [ ] Node.js 18 or higher — `node --version` confirms (required for the portal and Power Platform CLI)

**Microsoft 365 / Entra ID**
- [ ] M365 tenant with one of: **Microsoft 365 Copilot** license, **Copilot Studio** license, or **Power Virtual Agents Plan 2** assigned to the deploying admin account
- [ ] **Entra ID Application Administrator** or **Global Administrator** available to grant admin consent for Graph API permissions — one-time step in [Step 1](#step-1--entra-app-registration)
- [ ] **Teams Administrator** available to publish the bot to Teams in [Step 7](#step-7--configure-copilot-studio-agent)

**SharePoint**
- [ ] SharePoint Online site with document libraries containing HR PDFs and DOCX files
- [ ] The deploying admin has **Site Collection Administrator** access to the target SharePoint site
- [ ] Document libraries accessible from the Azure tenant (not blocked by a conditional access policy that prevents service principals)

---

## Step 1 — Entra App Registration

This service principal gives the Azure Function permission to read SharePoint documents and resolve group memberships via Microsoft Graph. Admin consent is required because the permissions are application-level — the function acts as itself, not as a signed-in user.

**Time: ~15 minutes**

### 1.1 Create the registration

1. Go to [portal.azure.com](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** → **App registrations** → **+ New registration**
3. Fill in:
   - **Name:** `RES-HR-Intranet-Sync`
   - **Supported account types:** Accounts in this organizational directory only (single tenant)
   - **Redirect URI:** leave blank
4. Click **Register**
5. On the **Overview** page, note the following values — you will need them in Steps 2 and 4:
   - **Application (client) ID** — this becomes `SHAREPOINT_CLIENT_ID`
   - **Directory (tenant) ID** — this becomes `SHAREPOINT_TENANT_ID`

### 1.2 Add API permissions

1. In the app registration, go to **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Application permissions**
2. Search for and add each permission below:

   | Permission | Type | Why it is needed |
   |---|---|---|
   | `Sites.Read.All` | Application | Read files from SharePoint document libraries |
   | `Group.Read.All` | Application | Resolve Entra group memberships for ACL population |
   | `User.Read.All` | Application | Look up user-to-group transitive memberships for security trimming |

3. Click **Add permissions**

### 1.3 Grant admin consent

Admin consent is required because application permissions grant the app access to all data of that type across the entire tenant. A **Global Administrator** or **Privileged Role Administrator** must complete this step.

1. In **API permissions**, click **Grant admin consent for \<your tenant name\>**
2. Confirm the dialog
3. Verify all three permissions show a green checkmark with status **Granted for \<tenant\>**

Without this step, the Function will receive `403 Forbidden` from every Graph API call.

### 1.4 Create a client secret

1. Go to **Certificates & secrets** → **Client secrets** → **+ New client secret**
2. **Description:** `res-hr-sync-prod`
3. **Expires:** 24 months — set a calendar reminder to rotate before expiry
4. Click **Add**
5. **Copy the secret Value immediately** — it is not shown again

### Summary of values to record

| Value | Where to find it | Used as |
|---|---|---|
| Application (client) ID | App registration Overview | `SHAREPOINT_CLIENT_ID` |
| Directory (tenant) ID | App registration Overview | `SHAREPOINT_TENANT_ID` |
| Client secret value | Certificates & secrets (copy at creation) | `SHAREPOINT_CLIENT_SECRET` |

---

## Step 2 — Clone and Configure

**Time: ~10 minutes**

```bash
git clone https://github.com/Garrett-s-Apps/res-hr-copilot
cd res-hr-copilot
cp infra/main.bicepparam infra/main.bicepparam.local
```

Open `infra/main.bicepparam.local` and fill in the required values. The file currently contains:

```bicep
using 'main.bicep'

// Azure region — eastus has the broadest Azure OpenAI model availability.
param location = 'eastus'

// Prefix applied to every resource name (e.g. res-hr-prod-search, res-hr-prod-kv).
// Must be 3–20 characters, lowercase alphanumeric and hyphens only.
param environmentName = 'res-hr-prod'

// AAD tenant ID for the target subscription.
// Find it: az account show --query tenantId -o tsv
param tenantId = ''  // TODO: fill in before deploying
```

Set `tenantId` to your Azure/M365 tenant ID. The `environmentName` value becomes a prefix for every resource name — the default `res-hr-prod` is appropriate for production.

> `infra/main.bicepparam.local` is git-ignored. Never commit it with real tenant IDs.

### Resource naming convention

With `environmentName = 'res-hr-prod'`, the Bicep modules create:

| Resource | Deployed name |
|---|---|
| User-assigned managed identity | `res-hr-prod-identity` |
| Storage account | derived from `res-hr-prod` (alphanumeric, truncated) |
| Key Vault | `res-hr-prod-kv` |
| Log Analytics workspace | `res-hr-prod-logs` |
| Application Insights | `res-hr-prod-appinsights` |
| Azure AI Search (S1) | `res-hr-prod-search` |
| Azure OpenAI (S0) | `res-hr-prod-openai` |
| Document Intelligence (S0) | `res-hr-prod-docintel` |
| App Service Plan (Consumption Y1, Linux) | `res-hr-prod-plan` |
| Function App (Python 3.11, Linux) | `res-hr-prod-func` |

---

## Step 3 — Deploy Azure Infrastructure

**Time: 8–12 minutes**

The Bicep template (`infra/main.bicep`) targets `resourceGroup` scope. Create the resource group first, then deploy into it.

```bash
az login
az account set --subscription "<your-subscription-id>"

# Create the resource group
az group create \
  --name rg-res-hr-copilot \
  --location eastus

# Deploy all infrastructure
az deployment group create \
  --resource-group rg-res-hr-copilot \
  --template-file infra/main.bicep \
  --parameters @infra/main.bicepparam.local \
  --name res-hr-intranet
```

Alternatively, use the deploy script which handles the resource group and parses outputs automatically:

```bash
./scripts/deploy.sh \
  --resource-group rg-res-hr-copilot \
  --location eastus \
  --env prod
```

### Expected outputs

A successful deployment produces a JSON object with these relevant values:

```
searchEndpoint           https://res-hr-prod-search.search.windows.net
openAiEndpoint           https://res-hr-prod-openai.openai.azure.com/
docIntelligenceEndpoint  https://res-hr-prod-docintel.cognitiveservices.azure.com/
keyVaultUri              https://res-hr-prod-kv.vault.azure.net/
functionAppHostname      res-hr-prod-func.azurewebsites.net
managedIdentityClientId  <guid>
appInsightsConnectionString  InstrumentationKey=...;IngestionEndpoint=...
```

Save these values — they are needed in Steps 4 through 8.

To retrieve outputs after the fact:

```bash
az deployment group show \
  --resource-group rg-res-hr-copilot \
  --name res-hr-intranet \
  --query properties.outputs \
  -o table
```

### Resources created (~10)

| Resource type | SKU / tier | Notes |
|---|---|---|
| User-Assigned Managed Identity | — | Used by Function App and Search for keyless auth |
| Storage Account | LRS | Functions runtime backing store + delta-link table |
| Key Vault | Standard, RBAC, soft-delete 90d | Holds SharePoint credentials |
| Log Analytics Workspace | Pay-per-GB | Central log sink |
| Application Insights | Pay-per-GB | Function telemetry + custom events |
| Azure AI Search | Standard S1 | Semantic ranker enabled |
| Azure OpenAI | S0 | Deploys `text-embedding-3-small` (120K TPM) and `gpt-4o-mini` (200K TPM) |
| Azure Document Intelligence | S0 | `prebuilt-read` model for OCR |
| App Service Plan | Consumption Y1, Linux | Scales to zero when idle |
| Function App | Python 3.11, Linux | `delta_sync` timer + `sharepoint_webhook` HTTP |

> The two OpenAI model deployments are created sequentially (the chat model depends on the embedding model completing first). This is expected and accounts for roughly 2 of the 8–12 minutes.

---

## Step 4 — Seed Key Vault Secrets

**Time: ~10 minutes**

The Bicep creates the Key Vault and grants the managed identity **Key Vault Secrets User** — but it does not populate the secrets. The Function App references these secrets at runtime using `@Microsoft.KeyVault(SecretUri=...)` app settings.

Replace all placeholder values with your actual values from Step 1 and your SharePoint environment.

```bash
KV_NAME="res-hr-prod-kv"

# Directory (tenant) ID of your M365 / Azure AD tenant
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "SHAREPOINT-TENANT-ID" \
  --value "<directory-tenant-id-from-step-1>"

# Application (client) ID of the RES-HR-Intranet-Sync app registration
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "SHAREPOINT-CLIENT-ID" \
  --value "<application-client-id-from-step-1>"

# Client secret value copied in Step 1.4
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "SHAREPOINT-CLIENT-SECRET" \
  --value "<client-secret-value-from-step-1>"
```

The Function App settings that reference these secrets are already wired by the Bicep:

```
SHAREPOINT_TENANT_ID     → @Microsoft.KeyVault(SecretUri=<kv-uri>secrets/SHAREPOINT-TENANT-ID/)
SHAREPOINT_CLIENT_ID     → @Microsoft.KeyVault(SecretUri=<kv-uri>secrets/SHAREPOINT-CLIENT-ID/)
SHAREPOINT_CLIENT_SECRET → @Microsoft.KeyVault(SecretUri=<kv-uri>secrets/SHAREPOINT-CLIENT-SECRET/)
```

### Verify Key Vault references resolved

After deploying the Function in Step 6, confirm the managed identity can read the secrets:

```bash
az functionapp config appsettings list \
  --name res-hr-prod-func \
  --resource-group rg-res-hr-copilot \
  --query "[?contains(name, 'SHAREPOINT')]" \
  -o table
```

The `value` column shows `@Microsoft.KeyVault(...)` — this is correct. The Function runtime resolves the actual value at execution time. If resolution fails, see [Troubleshooting](#key-vault-secret-reference-not-resolving).

### Note on Azure OpenAI and Search endpoints

The Azure OpenAI endpoint (`AZURE_OPENAI_ENDPOINT`) and Search endpoint (`AZURE_SEARCH_ENDPOINT`) are written directly from Bicep outputs into the Function App settings. No manual Key Vault entries are required for them. Both services are accessed via managed identity — there are no API keys in the configuration.

---

## Step 5 — Create Search Index

**Time: ~5 minutes**

This step creates the `hr-documents` index schema and the `hr-enrichment-skillset` in Azure AI Search. The index must exist before the Function can push documents.

```bash
# From the repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r functions/requirements.txt

# Set the Search endpoint from Step 3 output
export AZURE_SEARCH_ENDPOINT="https://res-hr-prod-search.search.windows.net"

# Option A — authenticate with your Azure CLI identity (recommended)
python3 scripts/create-search-index.py

# Option B — authenticate with an admin API key
export AZURE_SEARCH_API_KEY="<admin-key-from-portal>"
python3 scripts/create-search-index.py
```

To retrieve the admin key: **Azure AI Search resource** → **Keys** → copy **Primary admin key**.

### Expected output

```
============================================================
  RES HR Copilot — Azure AI Search Setup
============================================================

Loading index schema from: .../infra/search-config/index-schema.json
Loading skillset from: .../infra/search-config/skillset.json

Connecting to Azure AI Search...
  Endpoint  : https://res-hr-prod-search.search.windows.net
  Auth      : DefaultAzureCredential (managed identity / Azure CLI)

  Creating index 'hr-documents'...
  Index 'hr-documents' created successfully.
  Fields: 17

  Creating skillset 'hr-enrichment-skillset'...
  Skillset 'hr-enrichment-skillset' created successfully.

============================================================
  Setup complete.
============================================================
```

### Verify the index exists

```bash
az search index show \
  --name hr-documents \
  --service-name res-hr-prod-search \
  --resource-group rg-res-hr-copilot
```

---

## Step 6 — Deploy Azure Function

**Time: ~10 minutes to deploy + 5–60 minutes for initial index (depends on document count and OCR load)**

### 6.1 Set the SharePoint libraries to sync

Before deploying, configure which SharePoint drives the timer trigger crawls. The format is comma-separated `siteId|driveId` pairs.

Find your SharePoint site ID and drive ID:

```bash
# Get site ID (requires Graph access — az rest uses your CLI identity)
az rest \
  --method GET \
  --url "https://graph.microsoft.com/v1.0/sites/resllc.sharepoint.com:/sites/HR?select=id"

# Get drive IDs for the site
az rest \
  --method GET \
  --url "https://graph.microsoft.com/v1.0/sites/<site-id>/drives?select=id,name"
```

Then set the app setting:

```bash
az functionapp config appsettings set \
  --name res-hr-prod-func \
  --resource-group rg-res-hr-copilot \
  --settings "SHAREPOINT_LIBRARIES=<site-id>|<drive-id>"
```

For multiple libraries, comma-separate the pairs:

```bash
--settings "SHAREPOINT_LIBRARIES=siteId1|driveId1,siteId2|driveId2"
```

### 6.2 Deploy the function code

```bash
cd functions
func azure functionapp publish res-hr-prod-func --python
```

Expected output:

```
Getting site publishing info...
Creating archive for current directory...
Performing remote build for functions project.
...
Deployment successful.
Remote build succeeded!
Syncing triggers...
Functions in res-hr-prod-func:
    delta_sync - [timerTrigger]
    sharepoint_webhook - [httpTrigger]
```

### 6.3 Trigger the initial full sync

The timer runs automatically every 15 minutes (schedule: `0 */15 * * * *`). On first run with no stored delta link, it performs a full crawl of all configured drives. To start immediately rather than waiting:

1. In Azure Portal → **Function App** → `res-hr-prod-func` → **Functions** → `delta_sync`
2. Click **Code + Test** → **Test/Run** → **Run**

Or via the webhook endpoint (validates the Graph handshake but does not trigger a crawl):

```bash
FUNC_KEY=$(az functionapp keys list \
  --name res-hr-prod-func \
  --resource-group rg-res-hr-copilot \
  --query functionKeys.default -o tsv)

# Webhook validation handshake — confirms the endpoint is reachable
curl "https://res-hr-prod-func.azurewebsites.net/api/webhook?code=${FUNC_KEY}&validationToken=test"
```

**Expected processing times:**

| Document count | Estimated time |
|---|---|
| ~100 documents (text-native PDFs) | 5–15 minutes |
| ~100 documents (scanned PDFs with OCR) | 15–30 minutes |
| ~500 documents (mixed) | 30–60 minutes |

### 6.4 Monitor indexing progress

```bash
# Stream live logs from the Function
func azure functionapp logstream res-hr-prod-func

# Query Application Insights for processing traces
az monitor app-insights query \
  --app res-hr-prod-appinsights \
  --analytics-query "traces | where timestamp > ago(30m) | order by timestamp desc | take 50" \
  --resource-group rg-res-hr-copilot
```

Check document count in the index:

```bash
az search index show \
  --name hr-documents \
  --service-name res-hr-prod-search \
  --resource-group rg-res-hr-copilot \
  --query documentCount
```

---

## Step 7 — Configure Copilot Studio Agent

**Time: ~30 minutes**

### 7.1 Create the agent

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Confirm the environment selector (top-right) shows your M365 tenant — not a trial or default environment
3. Click **Create** → **New agent** → **Blank agent**
4. Fill in:
   - **Name:** `RES HR Assistant`
   - **Description:** `Answers HR policy and procedure questions for RES, LLC employees using official HR documentation.`
5. In the **Instructions** field, paste the full contents of `copilot/system-prompt.md`
6. **Language:** English (United States)
7. Click **Create**

### 7.2 Add Azure AI Search as a knowledge source

1. In the agent editor, select **Knowledge** in the left navigation
2. Click **+ Add knowledge** → **Azure AI Search**
3. Enter the connection details from your Step 3 outputs:
   - **Endpoint:** `https://res-hr-prod-search.search.windows.net`
   - **Index name:** `hr-documents`
   - **Semantic configuration:** `hr-semantic-config`
4. Under **Advanced settings**:
   - **Query type:** Semantic
   - **Top results:** 5
   - **Enable security trimming:** On
   - **Security trimming filter:** `allowed_groups/any(g: g eq '{User.EntraGroupOids}')`
5. Click **Save**

> **Why security trimming matters:** This filter runs server-side in Azure AI Search on every query. Users only receive chunks from documents their SharePoint group memberships permit. The `allowed_groups` field on each indexed document contains the Entra group OIDs that can access it — populated by the `AclResolver` during indexing.

### 7.3 Configure Entra ID authentication

Authentication enables SSO and provides the user identity needed to apply the `allowed_groups` security filter.

1. Go to **Settings** → **Security** → **Authentication**
2. Select **Authenticate with Microsoft**
3. Enter your app registration details from Step 1:
   - **Client ID:** `<application-client-id-from-step-1>`
   - **Tenant ID:** `<directory-tenant-id-from-step-1>`
   - **Client secret:** the value saved in Step 1.4
4. **Scopes:** `openid profile email User.Read`
5. Click **Save**
6. In the test pane, click **Sign in** and verify the authentication flow completes without error

> The app registration requires the Copilot Studio callback URI in its redirect URIs. In Azure Portal → **Entra ID** → **App registrations** → `RES-HR-Intranet-Sync` → **Authentication** → **Add a platform** → **Web** → paste the redirect URI shown in the Copilot Studio authentication panel.

### 7.4 Import topics

Copilot Studio does not natively import YAML. Use the Power Platform CLI or recreate topics manually.

**Option A — Power Platform CLI (recommended)**

```bash
npm install -g @microsoft/powerplatform-cli

# Authenticate to your Power Platform environment
pac auth create --environment <your-environment-id>

# Import solution package if available
pac solution import --path ./copilot/solution.zip
```

**Option B — Manual recreation**

Recreate topics in this order (Fallback depends on Feedback):

| YAML file | Topic name | Topic type | Trigger phrases |
|---|---|---|---|
| `copilot/topics/greeting.yaml` | Greeting | Trigger | hello, hi, help, what can you do, get started |
| `copilot/topics/escalation.yaml` | Escalation | Trigger | talk to HR, speak to a person, escalate, contact HR |
| `copilot/topics/feedback.yaml` | Feedback | Child dialog | (none — called by Fallback) |
| `copilot/topics/fallback.yaml` | Fallback | System topic | (set as Fallback in Settings → System topics → Fallback) |

For each topic: **Topics** → **+ Add topic** → **From blank** → name it per the YAML `name` field → add trigger phrases → recreate the action flow using the YAML as specification.

### 7.5 Configure Application Insights

1. Go to **Settings** → **Advanced** → **Application Insights**
2. Paste the `appInsightsConnectionString` from your Step 3 deployment output
3. Enable **Conversation logging**
4. Click **Save**

Custom events emitted by the topics:

| Event | Emitted by | Key properties |
|---|---|---|
| `hr_copilot_feedback` | Feedback topic | userId, feedbackValue, feedbackComment, queryText |
| `hr_copilot_escalation` | Escalation topic | userId, timestamp, channel, conversationId |

### 7.6 Test before publishing

Run these queries in the **Test** panel:

| Query | Expected result |
|---|---|
| "What is our PTO policy?" | Policy details with source citation |
| "How do I enroll in health insurance?" | Benefits enrollment steps with source |
| "Can you help me with my sales quota?" | Polite redirect — out of scope |
| "Talk to HR" | Escalation topic triggers, HR contact info shown |
| "asdfghjkl" | Fallback with no-result message and HR contact info |

Verify: sources are cited with URLs, the feedback card appears after generative answers, and out-of-scope queries are declined.

### 7.7 Publish to Microsoft Teams

1. In the agent editor, click **Publish** → **Publish agent** → **Publish**
2. Go to **Channels** → **Microsoft Teams** → **Turn on Teams**
3. In [Teams Admin Center](https://admin.teams.microsoft.com):
   - **Teams apps** → **Manage apps** → search `RES HR Assistant` → set **Status** to **Allowed**
   - **Teams apps** → **Setup policies** → assign to target users or groups, or deploy org-wide
4. Employees find the bot by searching `RES HR Assistant` in Teams

---

## Step 8 — Deploy Portal to Vercel

**Time: ~10 minutes**

The portal is a Next.js 14 intranet frontend (see `portal/package.json`).

### 8.1 Install and deploy

```bash
cd portal
npm install

# Install Vercel CLI if not already present
npm install -g vercel

vercel --prod
```

Follow the prompts to link to your Vercel account and project.

### 8.2 Set environment variables in the Vercel dashboard

Go to [vercel.com](https://vercel.com) → your project → **Settings** → **Environment Variables** and add:

| Variable | Value | Where to find it |
|---|---|---|
| `AZURE_SEARCH_ENDPOINT` | `https://res-hr-prod-search.search.windows.net` | Step 3 deployment output |
| `AZURE_SEARCH_KEY` | `<search-query-key>` | Azure Portal → AI Search → **Keys** → Query key |
| `AZURE_SEARCH_INDEX` | `hr-documents` | Fixed — matches the index schema name |
| `AZURE_OPENAI_ENDPOINT` | `https://res-hr-prod-openai.openai.azure.com/` | Step 3 deployment output |
| `AZURE_OPENAI_KEY` | `<openai-api-key>` | Azure Portal → Azure OpenAI → **Keys and Endpoint** |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o-mini` | Fixed — matches the Bicep deployment name |
| `NEXT_PUBLIC_COMPANY_NAME` | `RES, LLC` | Fixed |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | `it@res-llc.com` | Fixed |

> Use the **query key** (read-only) for `AZURE_SEARCH_KEY`, not the admin key.

After setting variables, trigger a redeployment:

```bash
vercel --prod
```

### 8.3 Verify

```bash
vercel ls
```

The output shows the production URL. Open it and run a test search to confirm the portal connects to Azure AI Search.

---

## Step 9 — Embed in SharePoint (Optional)

Surface the Copilot Studio chat widget directly on a SharePoint modern page.

### Option A — Copilot Studio embed snippet

1. In Copilot Studio → **Channels** → **Custom website**
2. Copy the `<script>` embed snippet
3. In SharePoint, edit the target page
4. Add an **Embed** web part (search "Embed" in the web part picker)
5. Paste the script snippet into the Embed web part code box
6. Publish the page

### Option B — SharePoint channel in Copilot Studio

1. In Copilot Studio → **Channels** → **SharePoint**
2. Follow the wizard — it generates an embed snippet preconfigured for SharePoint
3. Add it to the SharePoint page as in Option A

### Option C — SPFx Application Customizer (persistent side panel)

For a persistent side panel across all SharePoint pages, implement an SPFx Application Customizer that injects the embed script. This requires a separate SPFx solution and is outside the scope of this runbook. Reference: [Build your first SharePoint Framework Extension](https://learn.microsoft.com/sharepoint/dev/spfx/extensions/get-started/build-a-hello-world-extension).

---

## Step 10 — Validate Permissions

Run this after the initial index completes, before enabling the bot for employees. This confirms that security trimming is working — users see only documents their SharePoint permissions allow.

```bash
# From the repo root with .venv active
source .venv/bin/activate

export AZURE_SEARCH_ENDPOINT="https://res-hr-prod-search.search.windows.net"
export AZURE_SEARCH_INDEX="hr-documents"
export GRAPH_TENANT_ID="<directory-tenant-id>"
export GRAPH_CLIENT_ID="<application-client-id-from-step-1>"
export GRAPH_CLIENT_SECRET="<client-secret-value-from-step-1>"

python3 scripts/validate-permissions.py \
  --user <entra-object-id-of-test-employee> \
  --expected-docs "Employee Handbook" "PTO Policy" \
  --denied-docs "Executive Compensation Guide"
```

Find a user's Entra object ID:

```bash
az ad user show --id user@resllc.com --query id -o tsv
```

### Expected output

```
============================================================
  RES HR Copilot — Permission Validation
============================================================
  User OID        : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Expected visible: ['Employee Handbook', 'PTO Policy']
  Expected denied : ['Executive Compensation Guide']

Resolving Entra groups for user: xxxxxxxx-...
  Resolved 4 group(s) for user xxxxxxxx-...
  Searching for: 'Employee Handbook'...
  Searching for: 'PTO Policy'...
  Searching for: 'Executive Compensation Guide'...

============================================================
  Results
============================================================
  [PASS] 'Employee Handbook' — expected visible, got visible
  [PASS] 'PTO Policy' — expected visible, got visible
  [PASS] 'Executive Compensation Guide' — expected hidden, got hidden

----------------------------------------------------------
  Total: 3  |  Passed: 3  |  Failed: 0
============================================================

SUCCESS: All permission checks passed.
```

If any test fails, see [Security trimming FAIL](#security-trimming-validation-fails) in Troubleshooting.

### Run the post-deployment checklist

```bash
# Manually trigger the search indexer (if using the built-in indexer)
az search indexer run \
  --name hr-indexer \
  --service-name res-hr-prod-search \
  --resource-group rg-res-hr-copilot

# Confirm document count is non-zero
az search index show \
  --name hr-documents \
  --service-name res-hr-prod-search \
  --resource-group rg-res-hr-copilot \
  --query documentCount

# Confirm Application Insights is receiving function telemetry
az monitor app-insights query \
  --app res-hr-prod-appinsights \
  --analytics-query "requests | where timestamp > ago(1h) | summarize count() by name" \
  --resource-group rg-res-hr-copilot
```

---

## Cost Summary

Estimates for a small HR corpus (~500 documents, ~25 concurrent users). Actual costs vary with document volume, OCR usage, and query frequency.

| Service | SKU | Est. Monthly |
|---|---|---|
| Azure AI Search | Standard S1 (1 replica, 1 partition) | ~$250 |
| Azure OpenAI | Pay-per-use — `text-embedding-3-small` + `gpt-4o-mini` | ~$30–50 |
| Azure Document Intelligence | S0 — `prebuilt-read` | ~$10 (after initial OCR batch) |
| Azure Functions | Consumption (Y1) | ~$5 |
| Storage Account | LRS | ~$2 |
| Key Vault | Standard | ~$1 |
| Application Insights / Log Analytics | Pay-per-GB | ~$5–10 |
| Copilot Studio | 25K messages/month pack | ~$200 |
| **Total** | | **~$500–530/mo** |

**Cost levers:**
- Azure AI Search S1 is the largest fixed cost. If you have fewer than 2 GB of indexed content and can tolerate no semantic ranker, Basic tier (~$75/mo) is viable.
- Copilot Studio pricing is session/message-based. If employee usage is low, pay-as-you-go may be cheaper than the 25K pack.
- Azure OpenAI costs scale with document count at index time (embeddings) and query volume at runtime (`gpt-4o-mini`). Initial cost is low — it grows with adoption.
- Document Intelligence cost is primarily incurred during initial OCR of scanned documents. Ongoing incremental sync cost is minimal.

---

## Troubleshooting

### "Insufficient privileges to complete the operation"

**Cause:** Admin consent was not granted in Step 1.3, or the account performing the action lacks the required Entra ID role.

**Fix:** A Global Administrator must go to **Entra ID** → **App registrations** → `RES-HR-Intranet-Sync` → **API permissions** → **Grant admin consent**. Wait 2–5 minutes for permission propagation.

---

### Function returns 403 on SharePoint API calls

**Symptom:** Function logs show `403 Forbidden` from `graph.microsoft.com`.

**Cause:** One or more of the three application permissions is missing or admin consent was not granted.

**Fix:**
1. In Azure Portal → **Entra ID** → **App registrations** → `RES-HR-Intranet-Sync` → **API permissions**
2. Verify all three permissions are present with **Granted** status (green checkmark)
3. If any show **Not granted**, click **Grant admin consent** again
4. Wait 2–5 minutes, then restart the Function App:
   ```bash
   az functionapp restart \
     --name res-hr-prod-func \
     --resource-group rg-res-hr-copilot
   ```

---

### Search returns 0 results after indexing

**Symptom:** Copilot Studio returns the fallback message for every question. `documentCount` is 0.

**Cause A:** Initial sync has not run yet.

**Fix:** In Azure Portal → **Function App** → `res-hr-prod-func` → **Functions** → `delta_sync` → **Code + Test** → **Test/Run**. Wait 5–15 minutes and recheck document count.

**Cause B:** `SHAREPOINT_LIBRARIES` app setting is empty or incorrectly formatted.

**Fix:** Verify the setting is in `siteId|driveId` format with no extra spaces:
```bash
az functionapp config appsettings list \
  --name res-hr-prod-func \
  --resource-group rg-res-hr-copilot \
  --query "[?name=='SHAREPOINT_LIBRARIES']" \
  -o table
```

---

### Index schema mismatch — Function returns 400 pushing documents

**Symptom:** Function logs show `400 Bad Request` with a field type error when pushing chunks.

**Cause:** The index was created with an older schema from a previous attempt.

**Fix:** Delete and recreate the index:

```bash
# Retrieve admin key
SEARCH_KEY=$(az search admin-key show \
  --service-name res-hr-prod-search \
  --resource-group rg-res-hr-copilot \
  --query primaryKey -o tsv)

# Delete the index
az rest \
  --method DELETE \
  --url "https://res-hr-prod-search.search.windows.net/indexes/hr-documents?api-version=2024-03-01-preview" \
  --headers "api-key=$SEARCH_KEY"

# Recreate from schema
export AZURE_SEARCH_ENDPOINT="https://res-hr-prod-search.search.windows.net"
export AZURE_SEARCH_API_KEY="$SEARCH_KEY"
python3 scripts/create-search-index.py
```

---

### Copilot Studio returns "I couldn't find an answer" for all queries

**Cause A — SSO not configured or not working.** Without authentication, the user identity is unknown. The `allowed_groups` security filter resolves to no groups and no documents pass.

**Fix:** Complete Step 7.3. In the test pane, verify the user appears as signed in. Check that the app registration redirect URI is correctly set (see [Authentication loop](#copilot-studio-authentication-loop)).

**Cause B — Permission trimming too restrictive.** The `allowed_groups` field is empty on indexed documents, so no document matches any user's groups.

**Fix:** Run `scripts/validate-permissions.py` against a known user and document. If the script shows `FAIL` for expected-visible documents, check Function logs for `AclResolver` errors during the last sync run.

---

### Security trimming validation fails

**Symptom:** `validate-permissions.py` shows `[FAIL]` for a document that should be visible.

**Cause:** The `allowed_groups` field on the indexed document does not contain the user's Entra group OIDs.

**Diagnosis:**

```bash
# Check the raw allowed_groups values on a specific document
curl -s \
  -H "api-key: $AZURE_SEARCH_API_KEY" \
  "https://res-hr-prod-search.search.windows.net/indexes/hr-documents/docs?search=Employee+Handbook&select=title,allowed_groups&api-version=2024-03-01-preview" \
  | python3 -m json.tool
```

If `allowed_groups` is `[]` or missing, the AclResolver failed silently during indexing. Check the Function App logs from the last sync for errors containing `AclResolver`.

---

### Key Vault secret reference not resolving

**Symptom:** `az functionapp config appsettings list` shows `(null)` for a `SHAREPOINT_*` setting, and the Function fails with `KeyError: 'SHAREPOINT_TENANT_ID'`.

**Cause:** The managed identity is missing the **Key Vault Secrets User** role on the vault.

**Fix:**

```bash
IDENTITY_PID=$(az identity show \
  --name res-hr-prod-identity \
  --resource-group rg-res-hr-copilot \
  --query principalId -o tsv)

KV_ID=$(az keyvault show \
  --name res-hr-prod-kv \
  --resource-group rg-res-hr-copilot \
  --query id -o tsv)

az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee-object-id "$IDENTITY_PID" \
  --assignee-principal-type ServicePrincipal \
  --scope "$KV_ID"
```

Wait 2–5 minutes, then restart the Function App:

```bash
az functionapp restart \
  --name res-hr-prod-func \
  --resource-group rg-res-hr-copilot
```

---

### Copilot Studio authentication loop

**Symptom:** The bot repeatedly prompts sign-in or shows an authentication error after the user signs in.

**Cause:** The Entra app registration is missing the Copilot Studio redirect URI.

**Fix:**
1. In the Copilot Studio authentication settings panel, copy the **Redirect URI** displayed
2. In Azure Portal → **Entra ID** → **App registrations** → `RES-HR-Intranet-Sync` → **Authentication**
3. Click **+ Add a platform** → **Web**
4. Paste the redirect URI → **Configure**
5. Click **Save**
6. Re-test sign-in in the Copilot Studio test pane

---

### OCR quality is poor — garbled text in search results

**Cause A:** Document Intelligence free tier (F0) has rate limits that cause partial extractions.

**Fix:** Verify the Bicep deployed the S0 tier:
```bash
az cognitiveservices account show \
  --name res-hr-prod-docintel \
  --resource-group rg-res-hr-copilot \
  --query sku
```
Should return `{"name": "S0"}`. If it shows `F0`, redeploy.

**Cause B:** Source PDFs are password-protected or heavily skewed.

**Fix:** Pre-process source documents — remove passwords and run PDF optimizer (e.g., Adobe Acrobat "Optimize PDF") before uploading to SharePoint. Document Intelligence's `prebuilt-read` model handles moderate skew but not extreme angles.

---

### `hr_copilot_feedback` events not appearing in Application Insights

**Symptom:** The feedback adaptive card appears in Teams, but no `hr_copilot_feedback` events show in App Insights Logs.

**Fix:**
1. Allow up to 5 minutes — Application Insights batches telemetry before ingestion
2. In Azure Portal → **Application Insights** → **Logs**, run:
   ```kusto
   customEvents
   | where name == "hr_copilot_feedback"
   | order by timestamp desc
   | take 20
   ```
3. If still empty, verify the connection string in Copilot Studio → **Settings** → **Advanced** → **Application Insights** matches the `appInsightsConnectionString` output from Step 3 exactly, including the `InstrumentationKey=` prefix
4. Confirm **Conversation logging** is enabled in that same panel
