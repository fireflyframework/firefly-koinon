# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Azure Blob Storage using workload credentials in an existing container."""

import os
from urllib.parse import urlsplit

from koinon_storage.cloud import CloudProfile

from flyquery.core.services.storage.adapters.cloud import CloudObjectStore


class AzureBlobObjectStore(CloudObjectStore):
    def __init__(
        self,
        base: str,
        connection_string=None,
        encryption_scope=None,
        presign_ttl_s=86400,
        *,
        account_url="",
        request_timeout_seconds=10,
        max_object_bytes=64 * 1024 * 1024,
        client=None,
        owns_client=True,
    ):
        parsed = urlsplit(base)
        if parsed.scheme != "azure" or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("Azure base must identify an existing container and relative prefix")
        connection_string = connection_string or (
            os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "") if not account_url else ""
        )
        if not account_url:
            account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL", "")
        if connection_string and not account_url:
            parts = dict(part.split("=", 1) for part in connection_string.split(";") if "=" in part)
            account_url = parts.get("BlobEndpoint") or (
                parts.get("DefaultEndpointsProtocol", "https")
                + "://"
                + parts.get("AccountName", "")
                + ".blob."
                + parts.get("EndpointSuffix", "core.windows.net")
            )
        profile = CloudProfile(
            backend="azure",
            azure_account_url=account_url,
            azure_container=parsed.netloc,
            azure_prefix=parsed.path.lstrip("/"),
            request_timeout_seconds=request_timeout_seconds,
            max_object_bytes=max_object_bytes,
        )
        super().__init__(profile, presign_ttl_s=presign_ttl_s, client=client, owns_client=owns_client)
        self.native.connection_string = connection_string
        self.native.encryption_scope = encryption_scope
