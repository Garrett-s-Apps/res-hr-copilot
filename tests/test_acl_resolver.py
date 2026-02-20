"""
test_acl_resolver.py — Unit tests for AclResolver.

AclResolver resolves SharePoint item permissions into Entra group OIDs suitable
for populating the `allowed_groups` field in Azure AI Search. It handles:
  - Direct group permissions on an item
  - Inherited permissions from parent site/library
  - User permissions resolved to the user's group memberships
  - In-memory caching to avoid redundant Graph API calls
"""

import pytest
from unittest.mock import MagicMock, call, patch
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Minimal in-process implementation of AclResolver for self-contained tests.
# ---------------------------------------------------------------------------

@dataclass
class PermissionEntry:
    principal_type: str   # "group" | "user" | "everyone"
    principal_id: str     # Entra OID or special value
    role: str             # "read" | "write" | "owner"


@dataclass
class ResolvedAcl:
    item_id: str
    allowed_groups: list[str]  # Entra group OIDs


class AclResolver:
    """
    Resolves SharePoint item ACLs to a flat list of Entra group OIDs.

    Parameters
    ----------
    graph_client : any
        Microsoft Graph client (or mock) with methods:
          - get_item_permissions(site_id, item_id) -> list[PermissionEntry]
          - get_parent_permissions(site_id, item_id) -> list[PermissionEntry]
          - get_user_groups(user_oid) -> list[str]  (returns group OIDs)
    """

    def __init__(self, graph_client: Any) -> None:
        self._graph = graph_client
        # Cache keyed by (site_id, item_id) -> list[str] (resolved group OIDs)
        self._cache: dict[tuple[str, str], list[str]] = {}
        # Cache keyed by user_oid -> list[str] (group OIDs)
        self._user_group_cache: dict[str, list[str]] = {}

    def _resolve_permission_to_groups(self, entry: PermissionEntry) -> list[str]:
        """Convert a single permission entry to a list of Entra group OIDs."""
        if entry.principal_type == "group":
            return [entry.principal_id]
        elif entry.principal_type == "user":
            return self._get_user_groups_cached(entry.principal_id)
        elif entry.principal_type == "everyone":
            # Represents the "all authenticated users" sentinel
            return ["00000000-0000-0000-0000-000000000001"]
        return []

    def _get_user_groups_cached(self, user_oid: str) -> list[str]:
        """Return the group OIDs for a user, using cache to avoid repeat calls."""
        if user_oid not in self._user_group_cache:
            self._user_group_cache[user_oid] = self._graph.get_user_groups(user_oid)
        return self._user_group_cache[user_oid]

    def resolve(self, site_id: str, item_id: str, inherit: bool = True) -> ResolvedAcl:
        """
        Resolve all allowed groups for a SharePoint item.

        Parameters
        ----------
        site_id : str
            SharePoint site ID.
        item_id : str
            SharePoint item/file ID.
        inherit : bool
            If True, include permissions inherited from the parent library.
        """
        cache_key = (site_id, item_id)
        if cache_key in self._cache:
            return ResolvedAcl(item_id=item_id, allowed_groups=self._cache[cache_key])

        permissions = self._graph.get_item_permissions(site_id, item_id)

        if inherit:
            parent_perms = self._graph.get_parent_permissions(site_id, item_id)
            permissions = permissions + parent_perms

        group_oids: list[str] = []
        for entry in permissions:
            resolved = self._resolve_permission_to_groups(entry)
            for oid in resolved:
                if oid not in group_oids:
                    group_oids.append(oid)

        self._cache[cache_key] = group_oids
        return ResolvedAcl(item_id=item_id, allowed_groups=group_oids)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph_client(
    item_perms: list[PermissionEntry] | None = None,
    parent_perms: list[PermissionEntry] | None = None,
    user_groups: dict[str, list[str]] | None = None,
) -> MagicMock:
    """Return a mock Graph client pre-configured with the given data."""
    client = MagicMock()
    client.get_item_permissions.return_value = item_perms or []
    client.get_parent_permissions.return_value = parent_perms or []

    def _get_user_groups(user_oid: str) -> list[str]:
        return (user_groups or {}).get(user_oid, [])

    client.get_user_groups.side_effect = _get_user_groups
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

SITE_ID = "site-abc-123"
ITEM_ID = "item-xyz-456"
GROUP_OID_A = "aaaa-bbbb-cccc-dddd"
GROUP_OID_B = "bbbb-cccc-dddd-eeee"
USER_OID = "user-1111-2222-3333"


class TestAclResolver:

    # ------------------------------------------------------------------
    # test_group_permission_extracted
    # ------------------------------------------------------------------
    def test_group_permission_extracted(self) -> None:
        """A direct group permission on an item returns that group's OID."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")]
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)

        assert GROUP_OID_A in acl.allowed_groups
        assert len(acl.allowed_groups) == 1

    # ------------------------------------------------------------------
    # test_inherited_permissions_included
    # ------------------------------------------------------------------
    def test_inherited_permissions_included(self) -> None:
        """Permissions from the parent library are merged with item-level permissions."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")],
            parent_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_B, role="read")],
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=True)

        assert GROUP_OID_A in acl.allowed_groups
        assert GROUP_OID_B in acl.allowed_groups
        assert len(acl.allowed_groups) == 2

    # ------------------------------------------------------------------
    # test_user_permission_resolves_to_groups
    # ------------------------------------------------------------------
    def test_user_permission_resolves_to_groups(self) -> None:
        """A user-level permission is expanded to the user's group memberships."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="user", principal_id=USER_OID, role="read")],
            user_groups={USER_OID: [GROUP_OID_A, GROUP_OID_B]},
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)

        # Both groups the user belongs to should appear in allowed_groups
        assert GROUP_OID_A in acl.allowed_groups
        assert GROUP_OID_B in acl.allowed_groups
        graph.get_user_groups.assert_called_once_with(USER_OID)

    # ------------------------------------------------------------------
    # test_cache_prevents_duplicate_calls
    # ------------------------------------------------------------------
    def test_cache_prevents_duplicate_calls(self) -> None:
        """Resolving the same item twice uses the cache and does not call Graph again."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")]
        )
        resolver = AclResolver(graph_client=graph)

        acl_first = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)
        acl_second = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)

        # Graph should only have been called once
        assert graph.get_item_permissions.call_count == 1
        assert acl_first.allowed_groups == acl_second.allowed_groups

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------
    def test_no_permissions_returns_empty_list(self) -> None:
        """An item with no permissions returns an empty allowed_groups list."""
        graph = _make_graph_client(item_perms=[], parent_perms=[])
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID)

        assert acl.allowed_groups == []

    def test_deduplication_of_groups(self) -> None:
        """The same group OID appearing in both item and parent perms is deduplicated."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")],
            parent_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")],
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=True)

        assert acl.allowed_groups.count(GROUP_OID_A) == 1

    def test_everyone_permission_maps_to_sentinel(self) -> None:
        """An 'everyone' permission maps to the all-authenticated-users sentinel OID."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="everyone", principal_id="", role="read")]
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)

        assert "00000000-0000-0000-0000-000000000001" in acl.allowed_groups

    def test_user_group_cache_avoids_duplicate_graph_calls(self) -> None:
        """Resolving two items that both have the same user permission only calls get_user_groups once."""
        perm = PermissionEntry(principal_type="user", principal_id=USER_OID, role="read")
        graph = _make_graph_client(
            item_perms=[perm],
            user_groups={USER_OID: [GROUP_OID_A]},
        )
        resolver = AclResolver(graph_client=graph)

        resolver.resolve(SITE_ID, "item-001", inherit=False)
        # Manually clear the item cache to force a second resolution pass
        resolver._cache.clear()
        resolver.resolve(SITE_ID, "item-002", inherit=False)

        # get_user_groups should still only have been called once (user_group_cache hit)
        assert graph.get_user_groups.call_count == 1

    def test_inherit_false_excludes_parent_permissions(self) -> None:
        """When inherit=False, parent permissions are not fetched."""
        graph = _make_graph_client(
            item_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_A, role="read")],
            parent_perms=[PermissionEntry(principal_type="group", principal_id=GROUP_OID_B, role="read")],
        )
        resolver = AclResolver(graph_client=graph)
        acl = resolver.resolve(SITE_ID, ITEM_ID, inherit=False)

        assert GROUP_OID_A in acl.allowed_groups
        assert GROUP_OID_B not in acl.allowed_groups
        graph.get_parent_permissions.assert_not_called()
