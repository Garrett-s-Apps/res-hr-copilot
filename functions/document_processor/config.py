"""Central configuration — all env vars and shared Azure credential instances."""

import os
from azure.identity import DefaultAzureCredential, ClientSecretCredential

# ---------------------------------------------------------------------------
# Azure AI Search
# ---------------------------------------------------------------------------
AZURE_SEARCH_ENDPOINT: str = os.environ["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_INDEX_NAME: str = os.environ["AZURE_SEARCH_INDEX_NAME"]

# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT: str = os.environ["AZURE_OPENAI_ENDPOINT"]
OPENAI_EMBEDDING_DEPLOYMENT: str = os.environ["OPENAI_EMBEDDING_DEPLOYMENT"]
OPENAI_CHAT_DEPLOYMENT: str = os.environ["OPENAI_CHAT_DEPLOYMENT"]

# ---------------------------------------------------------------------------
# Azure Document Intelligence (Form Recognizer)
# ---------------------------------------------------------------------------
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.environ[
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
]

# ---------------------------------------------------------------------------
# SharePoint / Graph API — service principal (client credentials)
# ---------------------------------------------------------------------------
SHAREPOINT_TENANT_ID: str = os.environ["SHAREPOINT_TENANT_ID"]
SHAREPOINT_CLIENT_ID: str = os.environ["SHAREPOINT_CLIENT_ID"]
SHAREPOINT_CLIENT_SECRET: str = os.environ["SHAREPOINT_CLIENT_SECRET"]

# ---------------------------------------------------------------------------
# Azure Table Storage (delta-link persistence)
# ---------------------------------------------------------------------------
AZURE_STORAGE_CONNECTION_STRING: str = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING", ""
)
DELTA_LINK_TABLE_NAME: str = os.getenv("DELTA_LINK_TABLE_NAME", "deltalinks")

# ---------------------------------------------------------------------------
# SharePoint libraries to sync (comma-separated site:drive pairs)
# Format: "siteId1|driveId1,siteId2|driveId2"
# ---------------------------------------------------------------------------
SHAREPOINT_LIBRARIES: str = os.getenv("SHAREPOINT_LIBRARIES", "")


def get_default_credential() -> DefaultAzureCredential:
    """Return a DefaultAzureCredential suitable for Azure SDK clients.

    Relies on managed identity in production; falls back to env-var chain
    or Azure CLI locally.
    """
    return DefaultAzureCredential()


def get_graph_credential() -> ClientSecretCredential:
    """Return a ClientSecretCredential for Microsoft Graph API calls.

    Graph does not support managed identity scopes in all tenants, so we use
    a dedicated service principal with least-privilege Graph permissions.
    """
    return ClientSecretCredential(
        tenant_id=SHAREPOINT_TENANT_ID,
        client_id=SHAREPOINT_CLIENT_ID,
        client_secret=SHAREPOINT_CLIENT_SECRET,
    )
