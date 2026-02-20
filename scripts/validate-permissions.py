#!/usr/bin/env python3
"""
validate-permissions.py — Validates Azure AI Search security trimming for the RES HR Copilot.

Queries the search index using a user's Entra group OIDs and verifies that:
  - Documents the user is allowed to see appear in results
  - Documents the user is NOT allowed to see are absent from results

Usage:
    python3 scripts/validate-permissions.py \\
        --user <entra-user-oid> \\
        --expected-docs "Employee Handbook" "PTO Policy" \\
        --denied-docs "Executive Compensation Guide"

Environment variables:
    AZURE_SEARCH_ENDPOINT   — e.g. https://my-search.search.windows.net
    AZURE_SEARCH_INDEX      — defaults to hr-documents
    AZURE_SEARCH_API_KEY    — admin/query key (or uses DefaultAzureCredential)
    GRAPH_TENANT_ID         — required for group resolution via Microsoft Graph
    GRAPH_CLIENT_ID         — app registration client ID
    GRAPH_CLIENT_SECRET     — app registration client secret
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class ValidationResult(NamedTuple):
    document_title: str
    expected_visible: bool
    actually_visible: bool

    @property
    def passed(self) -> bool:
        return self.expected_visible == self.actually_visible

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        expectation = "visible" if self.expected_visible else "hidden"
        reality = "visible" if self.actually_visible else "hidden"
        return f"[{status}] '{self.document_title}' — expected {expectation}, got {reality}"


def resolve_user_groups(user_oid: str) -> list[str]:
    """Resolve the Entra group OIDs for a user via Microsoft Graph memberOf endpoint."""
    try:
        import urllib.request
        import urllib.parse
        import urllib.error
    except ImportError:
        print("ERROR: urllib is unavailable — cannot resolve groups.")
        sys.exit(1)

    tenant_id = os.environ.get("GRAPH_TENANT_ID", "")
    client_id = os.environ.get("GRAPH_CLIENT_ID", "")
    client_secret = os.environ.get("GRAPH_CLIENT_SECRET", "")

    if not all([tenant_id, client_id, client_secret]):
        print("WARNING: GRAPH_TENANT_ID, GRAPH_CLIENT_ID, or GRAPH_CLIENT_SECRET not set.")
        print("         Cannot resolve groups from Entra ID. Using user OID as group OID.")
        return [user_oid]

    # Acquire token via client credentials
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()

    try:
        req = urllib.request.Request(token_url, data=token_data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_resp = json.loads(resp.read())
        access_token = token_resp["access_token"]
    except Exception as exc:
        print(f"ERROR: Failed to acquire Graph token: {exc}")
        sys.exit(1)

    # Get transitive member-of groups
    graph_url = f"https://graph.microsoft.com/v1.0/users/{user_oid}/transitiveMemberOf/microsoft.graph.group?$select=id,displayName"
    req = urllib.request.Request(graph_url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        group_oids = [g["id"] for g in data.get("value", [])]
        print(f"  Resolved {len(group_oids)} group(s) for user {user_oid}")
        return group_oids
    except Exception as exc:
        print(f"ERROR: Failed to query Graph for user groups: {exc}")
        sys.exit(1)


def search_with_filter(query: str, group_oids: list[str], top: int = 50) -> list[str]:
    """Run a search query filtered to the user's groups. Returns list of document titles."""
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print("ERROR: azure-search-documents and azure-identity are required.")
        print("       Run: pip install azure-search-documents azure-identity")
        sys.exit(1)

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index_name = os.environ.get("AZURE_SEARCH_INDEX", "hr-documents")
    api_key = os.environ.get("AZURE_SEARCH_API_KEY", "")

    if not endpoint:
        print("ERROR: AZURE_SEARCH_ENDPOINT is not set.")
        sys.exit(1)

    credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    # Build security trim filter: allowed_groups must contain at least one of the user's groups
    if group_oids:
        group_filters = " or ".join(
            f"allowed_groups/any(g: g eq '{oid}')" for oid in group_oids
        )
        filter_expr = f"({group_filters})"
    else:
        # No groups resolved — user should see nothing
        filter_expr = "allowed_groups/any(g: g eq 'NO_GROUPS_RESOLVED')"

    results = client.search(
        search_text=query,
        filter=filter_expr,
        select=["title", "document_id", "source_path"],
        top=top,
    )

    titles = []
    for result in results:
        title = result.get("title", "")
        if title:
            titles.append(title)

    return titles


def run_validation(
    user_oid: str,
    expected_docs: list[str],
    denied_docs: list[str],
) -> list[ValidationResult]:
    """Resolve groups, run searches, and return per-document validation results."""
    print(f"\nResolving Entra groups for user: {user_oid}")
    group_oids = resolve_user_groups(user_oid)

    all_docs_to_check = list(set(expected_docs + denied_docs))
    results: list[ValidationResult] = []

    for doc_title in all_docs_to_check:
        print(f"  Searching for: '{doc_title}'...")
        visible_titles = search_with_filter(query=doc_title, group_oids=group_oids)
        # Case-insensitive partial match
        actually_visible = any(
            doc_title.lower() in t.lower() or t.lower() in doc_title.lower()
            for t in visible_titles
        )
        expected_visible = doc_title in expected_docs
        results.append(ValidationResult(
            document_title=doc_title,
            expected_visible=expected_visible,
            actually_visible=actually_visible,
        ))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Azure AI Search security trimming for RES HR Copilot."
    )
    parser.add_argument(
        "--user",
        required=True,
        help="Entra ID user OID to validate permissions for.",
    )
    parser.add_argument(
        "--expected-docs",
        nargs="*",
        default=[],
        metavar="DOC",
        help="Document titles the user SHOULD be able to see.",
    )
    parser.add_argument(
        "--denied-docs",
        nargs="*",
        default=[],
        metavar="DOC",
        help="Document titles the user should NOT be able to see.",
    )
    args = parser.parse_args()

    if not args.expected_docs and not args.denied_docs:
        parser.error("Provide at least one --expected-docs or --denied-docs document title.")

    load_env()

    print("=" * 60)
    print("  RES HR Copilot — Permission Validation")
    print("=" * 60)
    print(f"  User OID       : {args.user}")
    print(f"  Expected visible: {args.expected_docs or '(none)'}")
    print(f"  Expected denied : {args.denied_docs or '(none)'}")

    results = run_validation(
        user_oid=args.user,
        expected_docs=args.expected_docs,
        denied_docs=args.denied_docs,
    )

    print("\n" + "=" * 60)
    print("  Results")
    print("=" * 60)
    passed = 0
    failed = 0
    for result in results:
        print(f"  {result}")
        if result.passed:
            passed += 1
        else:
            failed += 1

    print("\n" + "-" * 60)
    print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")
    print("=" * 60)

    if failed > 0:
        print("\nFAILURE: Security trimming validation did not pass.")
        print("  Check that 'allowed_groups' is populated correctly on indexed documents.")
        sys.exit(1)
    else:
        print("\nSUCCESS: All permission checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
