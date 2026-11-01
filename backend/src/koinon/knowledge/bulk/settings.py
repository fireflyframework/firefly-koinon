# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="knowledge.bulk.settings")
@config_properties(prefix="koinon.knowledge.bulk")
@dataclass
class BulkSettings:
    storage_root: str | None = None
    storage_backend: str = "local"
    azure_account_url: str = ""
    azure_container: str = ""
    azure_prefix: str = ""
    gcs_bucket: str = ""
    gcs_project: str = ""
    gcs_prefix: str = ""
    gcs_endpoint_url: str = ""
    storage_request_timeout_seconds: int = 10
    max_local_storage_operations: int = 1
    upload_lease_seconds: int = 180
    recovery_lease_seconds: int = 90
    max_recoveries_per_tenant: int = 2
    max_recoveries_global: int = 8
    worker_enabled: bool = False
    query_worker_enabled: bool = False
    max_files: int = 100
    max_file_bytes: int = 128 * 1024 * 1024
    max_batch_bytes: int = 512 * 1024 * 1024
    max_staged_bytes_per_tenant: int = 16 * 1024 * 1024 * 1024
    max_uploads_per_tenant: int = 2
    max_uploads_global: int = 8
    max_workers_per_tenant: int = 2
    max_workers_global: int = 8
    processing_timeout_seconds: int = 240
    lease_seconds: int = 300
    staging_hours: int = 24
    max_active_batches_per_tenant: int = 8
    max_active_batches_per_subject: int = 2
    max_batches_per_tenant: int = 1000
    max_upload_attempts_per_item: int = 4

    def validate(self) -> None:
        limits = (
            (self.storage_request_timeout_seconds, 60),
            (self.max_local_storage_operations, 32),
            (self.upload_lease_seconds, 600),
            (self.recovery_lease_seconds, 300),
            (self.max_recoveries_per_tenant, 8),
            (self.max_recoveries_global, 32),
            (self.max_files, 100),
            (self.max_file_bytes, 128 * 1024 * 1024),
            (self.max_batch_bytes, 512 * 1024 * 1024),
            (self.max_staged_bytes_per_tenant, 16 * 1024 * 1024 * 1024),
            (self.max_uploads_per_tenant, 2),
            (self.max_uploads_global, 8),
            (self.max_workers_per_tenant, 2),
            (self.max_workers_global, 8),
            (self.processing_timeout_seconds, 240),
            (self.lease_seconds, 3600),
            (self.staging_hours, 24),
            (self.max_active_batches_per_tenant, 8),
            (self.max_active_batches_per_subject, 2),
            (self.max_batches_per_tenant, 1000),
            (self.max_upload_attempts_per_item, 4),
        )
        if (
            self.storage_backend not in {"local", "azure", "gcs"}
            or any(type(v) is not int or not 1 <= v <= maximum for v, maximum in limits)
            or self.lease_seconds < self.processing_timeout_seconds + 60
        ):
            raise ValueError("Bulk configuration exceeds its resource or lease bounds")
