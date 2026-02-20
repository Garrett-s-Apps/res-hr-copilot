#!/usr/bin/env python3
"""
create-search-index.py — Creates or updates the Azure AI Search index for RES HR Copilot.

Usage:
    python3 scripts/create-search-index.py

Environment variables (or set in .env):
    AZURE_SEARCH_ENDPOINT   — e.g. https://my-search.search.windows.net
    AZURE_SEARCH_API_KEY    — admin key (optional; uses DefaultAzureCredential if absent)
"""

import json
import os
import sys
from pathlib import Path

# Allow running from project root or scripts/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "infra" / "search-config" / "index-schema.json"
SKILLSET_PATH = REPO_ROOT / "infra" / "search-config" / "skillset.json"


def load_env() -> None:
    """Load .env file from repo root if it exists (no external dependency needed)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_search_client():
    """Return an authenticated SearchIndexClient using key or DefaultAzureCredential."""
    try:
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print("ERROR: azure-search-documents and azure-identity packages are required.")
        print("       Run: pip install azure-search-documents azure-identity")
        sys.exit(1)

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    if not endpoint:
        print("ERROR: AZURE_SEARCH_ENDPOINT environment variable is not set.")
        sys.exit(1)

    api_key = os.environ.get("AZURE_SEARCH_API_KEY", "")
    if api_key:
        credential = AzureKeyCredential(api_key)
        auth_method = "API key"
    else:
        credential = DefaultAzureCredential()
        auth_method = "DefaultAzureCredential (managed identity / Azure CLI)"

    print(f"  Endpoint  : {endpoint}")
    print(f"  Auth      : {auth_method}")
    return SearchIndexClient(endpoint=endpoint, credential=credential)


def substitute_env_vars(obj: dict) -> dict:
    """Recursively replace ${VAR_NAME} placeholders with environment variable values."""
    text = json.dumps(obj)
    import re
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name, "")
        if not value:
            print(f"  WARNING: ${{{var_name}}} is not set in environment — leaving placeholder.")
            return match.group(0)
        return value
    text = re.sub(r"\$\{([^}]+)\}", replacer, text)
    return json.loads(text)


def create_or_update_index(client, schema: dict) -> None:
    """Create the index if it does not exist, or update it if it does."""
    try:
        from azure.search.documents.indexes.models import SearchIndex
    except ImportError:
        print("ERROR: azure-search-documents is required.")
        sys.exit(1)

    index_name = schema.get("name", "hr-documents")

    # Check if index already exists
    existing_names = [idx.name for idx in client.list_indexes()]
    verb = "Updating" if index_name in existing_names else "Creating"
    print(f"\n  {verb} index '{index_name}'...")

    # azure-search-documents accepts the schema dict directly via from_dict
    index = SearchIndex.from_dict(schema)
    result = client.create_or_update_index(index)
    print(f"  Index '{result.name}' {verb.lower().rstrip('ing')}d successfully.")
    print(f"  Fields: {len(result.fields)}")


def create_or_update_skillset(client, skillset_def: dict) -> None:
    """Create or update the enrichment skillset."""
    try:
        from azure.search.documents.indexes import SearchIndexerClient
        from azure.search.documents.indexes.models import SearchIndexerSkillset
        from azure.core.credentials import AzureKeyCredential
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return  # Already caught above

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_SEARCH_API_KEY", "")
    credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()

    indexer_client = SearchIndexerClient(endpoint=endpoint, credential=credential)
    skillset_name = skillset_def.get("name", "hr-enrichment-skillset")

    existing = [s.name for s in indexer_client.get_skillsets()]
    verb = "Updating" if skillset_name in existing else "Creating"
    print(f"\n  {verb} skillset '{skillset_name}'...")

    skillset = SearchIndexerSkillset.from_dict(skillset_def)
    result = indexer_client.create_or_update_skillset(skillset)
    print(f"  Skillset '{result.name}' {verb.lower().rstrip('ing')}d successfully.")
    print(f"  Skills: {len(result.skills)}")


def main() -> None:
    print("=" * 60)
    print("  RES HR Copilot — Azure AI Search Setup")
    print("=" * 60)

    load_env()

    # Load schema files
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema file not found: {SCHEMA_PATH}")
        sys.exit(1)

    print(f"\nLoading index schema from: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        raw_schema = json.load(f)
    schema = substitute_env_vars(raw_schema)

    skillset: dict | None = None
    if SKILLSET_PATH.exists():
        print(f"Loading skillset from: {SKILLSET_PATH}")
        with open(SKILLSET_PATH) as f:
            raw_skillset = json.load(f)
        skillset = substitute_env_vars(raw_skillset)
    else:
        print(f"WARNING: Skillset file not found at {SKILLSET_PATH} — skipping skillset.")

    print("\nConnecting to Azure AI Search...")
    client = get_search_client()

    # Create / update index
    create_or_update_index(client, schema)

    # Create / update skillset
    if skillset:
        create_or_update_skillset(client, skillset)

    print("\n" + "=" * 60)
    print("  Setup complete.")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run the indexer to populate the index:")
    print("     az search indexer run --name hr-indexer \\")
    print("       --service-name <your-search-service> \\")
    print("       -g <your-resource-group>")
    print("  2. Verify document count:")
    print("     az search index show --name hr-documents \\")
    print("       --service-name <your-search-service> \\")
    print("       -g <your-resource-group>")


if __name__ == "__main__":
    main()
