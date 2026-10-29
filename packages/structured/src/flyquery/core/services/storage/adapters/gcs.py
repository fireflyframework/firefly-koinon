# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Google Cloud Storage using application-default or workload credentials."""

from urllib.parse import urlsplit

from koinon_storage.cloud import CloudProfile

from flyquery.core.services.storage.adapters.cloud import CloudObjectStore


class GcsObjectStore(CloudObjectStore):
    def __init__(
        self,
        base: str,
        endpoint_url=None,
        service_file=None,
        presign_ttl_s=86400,
        *,
        project="",
        request_timeout_seconds=10,
        max_object_bytes=64 * 1024 * 1024,
        client=None,
    ):
        parsed = urlsplit(base)
        if parsed.scheme != "gs" or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("GCS base must identify an existing bucket and relative prefix")
        profile = CloudProfile(
            backend="gcs",
            gcs_bucket=parsed.netloc,
            gcs_prefix=parsed.path.lstrip("/"),
            gcs_project=project,
            gcs_endpoint_url=endpoint_url or "",
            request_timeout_seconds=request_timeout_seconds,
            max_object_bytes=max_object_bytes,
        )
        super().__init__(profile, presign_ttl_s=presign_ttl_s, client=client)
        self.native.service_file = service_file
