# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.core import Config

from koinon.operations.configuration import configure_storage
from koinon.storage.settings import AttachmentStorageProfile


@pytest.mark.parametrize(
    "changes",
    [
        {"backend": "unknown"},
        {"backend": "s3"},
        {"s3_prefix": "../escape"},
        {"s3_endpoint_url": "http://public.example"},
        {"s3_endpoint_url": "https://example.test/?key=value"},
        {"request_timeout_seconds": 0},
        {"max_object_bytes": True},
        {"max_object_bytes": 268435457},
        {"root": False},
    ],
)
def test_private_profile_rejects_invalid_backend_bounds_endpoints_and_paths(changes):
    with pytest.raises(ValueError):
        AttachmentStorageProfile(**changes)


def test_explicit_storage_aliases_map_to_typed_profile_without_touching_other_storage():
    aliases = {
        "ATTACHMENT_STORAGE_BACKEND": "s3",
        "ATTACHMENT_STORAGE_S3_BUCKET": "owned-private-test",
        "ATTACHMENT_STORAGE_S3_PREFIX": "koinon/private",
        "ATTACHMENT_STORAGE_REQUEST_TIMEOUT_SECONDS": "7",
        "ATTACHMENT_STORAGE_MAX_OBJECT_BYTES": "1048576",
    }
    values = {"storage": {"documents": {"backend": "localfs", "root": "/retained/documents"}}}
    configure_storage(values, lambda alias, path, default: aliases.get(alias, default))
    profile = Config({"koinon": values}).bind(AttachmentStorageProfile)
    assert profile.backend == "s3" and profile.s3_bucket == "owned-private-test"
    assert profile.request_timeout_seconds == 7 and profile.max_object_bytes == 1048576
    assert values["storage"]["documents"]["root"] == "/retained/documents"


def test_native_file_profiles_preserve_values_without_aliases():
    configured = {"backend": "local", "root": "/retained/private", "max_object_bytes": 8192}
    values = {"storage": {"attachments": configured.copy()}}
    configure_storage(
        values,
        lambda alias, path, default: (
            configured.get(path.rsplit(".", 1)[-1], default) if ".attachments." in path else default
        ),
    )
    profile = Config({"koinon": values}).bind(AttachmentStorageProfile)
    assert profile.root == "/retained/private" and profile.max_object_bytes == 8192


def test_larger_shared_object_bound_preserves_separate_chat_file_limits():
    from koinon.knowledge.attachments.settings import AttachmentSettings

    profile = AttachmentStorageProfile(max_object_bytes=256 * 1024**2)
    assert profile.max_object_bytes == 256 * 1024**2
    assert AttachmentSettings().max_file_bytes == 20 * 1024**2
