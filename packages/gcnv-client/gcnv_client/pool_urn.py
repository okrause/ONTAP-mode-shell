"""Parse Google Cloud NetApp Volumes storage pool resource names."""

from __future__ import annotations

import re
from dataclasses import dataclass

_FULL_POOL_URN_RE = re.compile(
    r"projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/storagePools/(?P<pool>[^/]+)"
)
_SHORT_POOL_URN_RE = re.compile(
    r"locations/(?P<location>[^/]+)/storagePools/(?P<pool>[^/]+)"
)


@dataclass(frozen=True)
class ParsedStoragePoolUrn:
    """Components extracted from a storage pool resource name."""

    location: str
    pool_name: str
    project: str | None = None

    @property
    def api_path(self) -> str:
        """Relative API path appended to ``/projects/{project}``."""
        return f"/locations/{self.location}/storagePools/{self.pool_name}"

    def full_resource_name(self, project: str) -> str:
        """Return ``projects/{project}/locations/.../storagePools/...``."""
        if self.project:
            return f"projects/{self.project}/locations/{self.location}/storagePools/{self.pool_name}"
        return f"projects/{project}/locations/{self.location}/storagePools/{self.pool_name}"


def format_storage_pool_urn(project: str, api_path: str) -> str:
    """Build a full pool resource name from project ID and API path."""
    path = api_path.lstrip("/")
    if path.startswith("projects/"):
        return path
    return f"projects/{project}/{path}"


def parse_storage_pool_urn(urn: str) -> ParsedStoragePoolUrn:
    """Extract project, location, and pool name from a storage pool URN.

    Accepts full resource names such as::

        projects/my-project/locations/us-east1-b/storagePools/my-pool

    Short forms without a project segment are also accepted::

        locations/us-east1-b/storagePools/my-pool
        /locations/us-east1-b/storagePools/my-pool

    Full HTTPS resource URLs are accepted as well.
    """
    normalized = urn.strip().rstrip("/")
    if not normalized:
        raise ValueError("Storage pool URN must not be empty")

    if "://" in normalized:
        normalized = normalized.split("://", 1)[1]
        if "/" in normalized:
            normalized = normalized.split("/", 1)[1]
        if normalized.startswith(("v1beta1/", "v1/")):
            normalized = normalized.split("/", 1)[1]

    normalized = normalized.lstrip("/")

    match = _FULL_POOL_URN_RE.search(normalized)
    if match:
        return ParsedStoragePoolUrn(
            project=match.group("project"),
            location=match.group("location"),
            pool_name=match.group("pool"),
        )

    match = _SHORT_POOL_URN_RE.search(normalized)
    if match:
        return ParsedStoragePoolUrn(
            location=match.group("location"),
            pool_name=match.group("pool"),
        )

    raise ValueError(
        "Invalid storage pool URN. Expected "
        "projects/{project}/locations/{location}/storagePools/{pool} "
        "or locations/{location}/storagePools/{pool}: "
        f"{urn!r}"
    )
