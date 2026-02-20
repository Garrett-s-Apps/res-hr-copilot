# Copilot Studio Setup Guide — RES HR Assistant

Step-by-step instructions for deploying the RES HR Assistant in Microsoft Copilot Studio.

---

## Prerequisites

- Microsoft 365 tenant with Copilot Studio license (Power Virtual Agents Plan 2 or Microsoft 365 Copilot)
- Azure AI Search index deployed (see `infra/search-config/` and `scripts/deploy.sh`)
- Azure OpenAI resource with `text-embedding-3-small` deployed
- Entra ID app registration for authentication (see Step 3)
- Teams admin access to publish the bot

---

## Step 1: Create a Standalone Agent

1. Navigate to [https://copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Select your environment (ensure it matches your M365 tenant)
3. Click **Create** → **New agent**
4. Choose **Blank agent** (not a template)
5. Configure:
   - **Name:** `RES HR Assistant`
   - **Description:** `Answers HR policy and procedure questions for RES, LLC employees using official HR documentation.`
   - **Instructions:** Paste the full contents of `copilot/system-prompt.md`
   - **Language:** English (United States)
6. Click **Create**

---

## Step 2: Connect Azure AI Search as Knowledge Source

1. In the agent editor, go to **Knowledge** in the left nav
2. Click **Add knowledge** → **Azure AI Search**
3. Enter connection details:
   - **Endpoint:** `https://<your-search-service>.search.windows.net`
   - **Index name:** `hr-documents`
   - **Semantic configuration:** `hr-semantic-config`
   - **Authentication:** Managed Identity (preferred) or API Key
4. Under **Advanced settings**:
   - Set **Query type** to `Semantic`
   - Set **Top results** to `5`
   - Enable **Security trimming** and set the filter expression:
     ```
     allowed_groups/any(g: g eq '{user_group_oid}')
     ```
5. Click **Save**
6. Test retrieval by clicking **Test** and entering a sample HR question

---

## Step 3: Configure Entra ID Authentication

1. In the agent editor, go to **Settings** → **Security** → **Authentication**
2. Select **Authenticate with Microsoft** (Entra ID)
3. Enter your Entra ID app registration details:
   - **Client ID:** from your app registration in Azure Portal
   - **Client Secret:** store in Azure Key Vault; reference via the Key Vault URL
   - **Tenant ID:** your M365 tenant ID
4. Set **Token exchange URL** to your Azure Function endpoint for OBO flow (if using on-behalf-of for Graph API group resolution)
5. Set **Scopes:** `openid profile email User.Read`
6. Under **Manual authentication**, map:
   - `User.Id` → Entra user OID
   - `User.DisplayName` → display name claim
   - `User.EntraGroupOids` → resolved group memberships (requires OBO function)
7. Click **Save** and verify sign-in works in the test pane

---

## Step 4: Import Topics

Import each topic YAML file from `copilot/topics/` into Copilot Studio.

**Note:** Copilot Studio does not natively import YAML files directly. Use the Power Platform CLI or manually recreate each topic:

### Using Power Platform CLI (recommended)

```bash
# Install CLI
npm install -g @microsoft/powerplatform-cli

# Authenticate
pac auth create --environment <your-environment-id>

# Import solution package (wrap topics in a solution first)
pac solution import --path ./copilot/solution.zip
```

### Manual recreation order

1. **Greeting** (`topics/greeting.yaml`) — triggers on: hello, hi, help, what can you do, get started
2. **Escalation** (`topics/escalation.yaml`) — triggers on: talk to HR, speak to a person, escalate, contact HR
3. **Feedback** (`topics/feedback.yaml`) — called as a child dialog from Fallback; no trigger phrases
4. **Fallback** (`topics/fallback.yaml`) — set as the **Fallback topic** in Settings → System topics → Fallback

For each topic:
1. Click **Topics** → **Add topic** → **From blank**
2. Name the topic per the YAML `name` field
3. Add trigger phrases from the YAML `triggerPhrases` list
4. Recreate the action flow using the YAML as the specification

---

## Step 5: Configure Application Insights Logging

1. In Azure Portal, create an Application Insights resource (or use existing)
2. Copy the **Connection String**
3. In Copilot Studio → **Settings** → **Advanced** → **Application Insights**:
   - Paste the connection string
   - Enable conversation logging
4. The Feedback and Escalation topics emit custom events:
   - `hr_copilot_feedback` — thumbs rating + optional comment
   - `hr_copilot_escalation` — escalation trigger details

---

## Step 6: Publish to Microsoft Teams

1. In the agent editor, go to **Publish** → **Publish agent**
2. Click **Publish** to push the latest version
3. Go to **Channels** → **Microsoft Teams**
4. Click **Turn on Teams**
5. In Teams Admin Center ([https://admin.teams.microsoft.com](https://admin.teams.microsoft.com)):
   - Go to **Teams apps** → **Manage apps**
   - Find `RES HR Assistant` and set **Status** to Allowed
   - Go to **Teams apps** → **Setup policies** → assign to target users or groups
6. Employees can find the bot by searching "RES HR Assistant" in Teams

---

## Step 7: Publish to SharePoint (Optional)

1. In Copilot Studio → **Channels** → **SharePoint**
2. Copy the embed code snippet
3. In SharePoint:
   - Edit the target page
   - Add an **Embed** web part
   - Paste the Copilot Studio embed snippet
4. Optionally add the bot to the SharePoint global navigation as a side panel

---

## Step 8: Test with Sample Questions

Use these questions to validate end-to-end functionality after publishing:

| Question | Expected behavior |
|---|---|
| "What is our PTO policy?" | Returns policy details with source citation |
| "How do I enroll in health insurance?" | Returns benefits enrollment steps with source |
| "What's on the new hire checklist?" | Returns onboarding list with source |
| "Can you help me with my sales quota?" | Redirects — out of scope |
| "Talk to HR" | Triggers escalation topic |
| "asdfghjkl" | Triggers fallback with no-result message |

After each answer, verify:
- [ ] Sources are cited with URLs
- [ ] Security trimming prevents cross-group document leakage (use `scripts/validate-permissions.py`)
- [ ] Feedback card appears after generative answers
- [ ] Application Insights receives `hr_copilot_feedback` events

---

## Troubleshooting

**Bot returns no results:** Check that the Azure AI Search index has documents. Run `scripts/create-search-index.py` and verify the indexer has run.

**Authentication loop:** Verify the Entra ID app registration redirect URIs include the Copilot Studio callback URL shown in the authentication settings panel.

**Security trimming not working:** Confirm the `allowed_groups` field is populated on indexed documents. Run `scripts/validate-permissions.py` to verify.

**Feedback events not appearing in App Insights:** Allow up to 5 minutes for event ingestion. Check the connection string is correct in Copilot Studio settings.
