# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from koinon_storage.cloud import CloudProfile
from pyfly.container import component
from pyfly.core import config_properties

from koinon.security.settings import _endpoint


@component(name="storage.attachments.profile")
@config_properties(prefix="koinon.storage.attachments")
@dataclass
class AttachmentStorageProfile:
    backend: str = "local"
    root: str | None = None
    s3_bucket: str = ""
    s3_prefix: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_kms_key_id: str = ""
    azure_account_url: str = ""
    azure_container: str = ""
    azure_prefix: str = ""
    gcs_bucket: str = ""
    gcs_project: str = ""
    gcs_prefix: str = ""
    gcs_endpoint_url: str = ""
    request_timeout_seconds: int = 10
    max_object_bytes: int = 64 * 1024 * 1024

    def __post_init__(self):
        if self.backend in {"azure", "gcs"}:
            self.cloud_profile()
        if self.root is not None and not isinstance(self.root, str):
            raise ValueError("Private storage root must be an explicit directory path")
        if self.backend not in {"local", "s3", "azure", "gcs"}:
            raise ValueError("Private attachment storage backend must be local, s3, azure or gcs")
        if type(self.request_timeout_seconds) is not int or not 1 <= self.request_timeout_seconds <= 60:
            raise ValueError("Private storage request timeout must be an integer from 1 to 60 seconds")
        if type(self.max_object_bytes) is not int or not 1 <= self.max_object_bytes <= 64 * 1024 * 1024:
            raise ValueError("Private object byte limit must be from 1 byte to 64 MiB")
        for value in (self.root or "", self.s3_bucket, self.s3_prefix, self.s3_region, self.s3_kms_key_id):
            if not isinstance(value, str) or any(char in value for char in ("\0", "\r", "\n")):
                raise ValueError("Private storage values must be plain configuration strings")
        if self.s3_prefix.startswith("/") or any(part in {".", ".."} for part in self.s3_prefix.split("/")):
            raise ValueError("Private storage S3 prefix must be a relative object prefix")
        if self.s3_endpoint_url:
            _endpoint(self.s3_endpoint_url)
            if urlsplit(self.s3_endpoint_url).query:
                raise ValueError("Private storage endpoint cannot contain a query")
        if self.backend == "s3" and not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.s3_bucket):
            raise ValueError("Private storage requires an explicit valid S3 bucket")

    def cloud_profile(self):
        return CloudProfile(
            backend=self.backend,
            **{
                "azure_account_url": self.azure_account_url,
                "azure_container": self.azure_container,
                "azure_prefix": self.azure_prefix,
                "gcs_bucket": self.gcs_bucket,
                "gcs_project": self.gcs_project,
                "gcs_prefix": self.gcs_prefix,
                "gcs_endpoint_url": self.gcs_endpoint_url,
                "request_timeout_seconds": self.request_timeout_seconds,
                "max_object_bytes": self.max_object_bytes,
            },
        )
