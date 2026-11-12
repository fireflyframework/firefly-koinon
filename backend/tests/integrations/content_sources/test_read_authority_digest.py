# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviewed authority survives credential refresh but not identity or scope changes."""

from types import SimpleNamespace

import pytest

from koinon.integrations.content_sources.errors import SourceError


def grant(**changes):
    return SimpleNamespace(
        **{
            "id": "connection",
            "tenant_id": "tenant",
            "owner": "reader",
            "provider": "google_drive",
            "external_subject": "remote",
            "external_tenant": None,
            "issuer": "https://accounts.google.com",
            "config_fingerprint": "a" * 64,
            "scopes": ["openid", "drive.readonly"],
            "revision": 1,
            "status": "connected",
            "secret_ciphertext": b"old",
            **changes,
        }
    )


def test_authority_digest_survives_credential_rotation_and_scope_order():
    from koinon.integrations.content_sources.read_authority import source_authority

    payload, digest = source_authority(grant())
    assert source_authority(
        grant(revision=9, secret_ciphertext=b"refreshed", scopes=["drive.readonly", "openid", "openid"])
    ) == (payload, digest)
    assert payload["schema"] == "koinon.source-authority.v1" and payload["external_tenant"] is None
    assert len(digest) == 64 and not {"revision", "status", "secret_ciphertext"} & payload.keys()


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "other"),
        ("tenant_id", "other"),
        ("owner", "other"),
        ("provider", "onedrive"),
        ("external_subject", "other"),
        ("external_tenant", "other"),
        ("issuer", "https://issuer.invalid"),
        ("config_fingerprint", "b" * 64),
        ("scopes", ["openid"]),
    ],
)
def test_authority_digest_changes_with_every_authority_input(field, value):
    from koinon.integrations.content_sources.read_authority import source_authority

    assert source_authority(grant())[1] != source_authority(grant(**{field: value}))[1]


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": None},
        {"config_fingerprint": ""},
        {"scopes": "openid"},
        {"scopes": ["openid", 1]},
        {"scopes": ["bad scope"]},
    ],
)
def test_malformed_authority_is_rejected(changes):
    from koinon.integrations.content_sources.read_authority import source_authority

    with pytest.raises(SourceError, match="authority_changed"):
        source_authority(grant(**changes))
