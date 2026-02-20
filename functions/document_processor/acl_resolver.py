"""Resolve SharePoint item permissions to Entra ID group OIDs.

Uses the Microsoft Graph SDK with a service-principal ClientSecretCredential.
Group OID resolution results are cached for 5 minutes to limit Graph API traffic
during bulk delta-sync runs.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph import GraphServiceClient
from msgraph.generated.models.permission import Permission

from .config import get_graph_credential

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes


class AclResolver:
    """Resolve a SharePoint drive item's effective permission list to group OIDs."""

    def __init__(self) -> None:
        credential = get_graph_credential()
        # Scope required: Sites.Read.All (to read permissions)
        self._graph = GraphServiceClient(
            credentials=credential,
            scopes=["https://graph.microsoft.com/.default"],
        )
        # {user_id: (group_oids, expiry_timestamp)}
        self._user_group_cache: dict[str, tuple[list[str], float]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_allowed_groups(
        self,
        site_id: str,
        drive_id: str,
        item_id: str,
    ) -> list[str]:
        """Return Entra ID group OIDs that have access to the given drive item.

        Inspects all permissions (direct + inherited) and:
          - Includes group grantees directly.
          - Resolves user grantees to their Entra group memberships via
            /users/{id}/memberOf (cached).
        """
        permissions = await self._get_permissions(site_id, drive_id, item_id)
        group_oids: set[str] = set()

        for perm in permissions:
            granted_to = getattr(perm, "granted_to", None)
            granted_to_identities = getattr(perm, "granted_to_identities", None) or []

            # Normalise: single grantee or list of grantees
            identities: list[Any] = []
            if granted_to:
                identities.append(granted_to)
            identities.extend(granted_to_identities)

            for identity_set in identities:
                group = getattr(identity_set, "group", None)
                user = getattr(identity_set, "user", None)

                if group and getattr(group, "id", None):
                    group_oids.add(group.id)

                if user and getattr(user, "id", None):
                    # Resolve user -> groups (with caching)
                    user_groups = await self._resolve_user_groups(user.id)
                    group_oids.update(user_groups)

        return sorted(group_oids)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_permissions(
        self,
        site_id: str,
        drive_id: str,
        item_id: str,
    ) -> list[Permission]:
        """Fetch all permission entries for a drive item from Graph."""
        try:
            result = await (
                self._graph.sites.by_site_id(site_id)
                .drives.by_drive_id(drive_id)
                .items.by_drive_item_id(item_id)
                .permissions.get()
            )
            return result.value if result and result.value else []
        except Exception:
            logger.exception(
                "Failed to fetch permissions for item %s in drive %s", item_id, drive_id
            )
            return []

    async def _resolve_user_groups(self, user_id: str) -> list[str]:
        """Return group OIDs for a user, using the 5-minute in-process cache."""
        cached = self._user_group_cache.get(user_id)
        if cached is not None:
            group_oids, expiry = cached
            if time.monotonic() < expiry:
                return group_oids

        group_oids = await self._fetch_user_groups(user_id)
        self._user_group_cache[user_id] = (group_oids, time.monotonic() + _CACHE_TTL_SECONDS)
        return group_oids

    async def _fetch_user_groups(self, user_id: str) -> list[str]:
        """Call Graph /users/{id}/memberOf and extract group OIDs."""
        try:
            result = await (
                self._graph.users.by_user_id(user_id)
                .member_of.get()
            )
            if not result or not result.value:
                return []
            oids: list[str] = []
            for obj in result.value:
                # memberOf returns directoryObject; group objects have @odata.type
                odata_type = getattr(obj, "odata_type", "") or ""
                obj_id = getattr(obj, "id", None)
                if obj_id and "#microsoft.graph.group" in odata_type:
                    oids.append(obj_id)
            return oids
        except Exception:
            logger.exception("Failed to resolve group membership for user %s", user_id)
            return []
