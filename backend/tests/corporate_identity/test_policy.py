# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.policy import (
    DirectorySnapshot,
    IdentityPolicy,
    MappingRule,
    planned_grants,
    verified_identity,
)

ISSUER = "https://identity.example.test/realms/koinon"


def test_broker_identity_preserves_canonical_subject_and_never_merges_email():
    policy = IdentityPolicy(
        "provider", "entra", ISSUER, "north-entra", external_tenant_id="11111111-1111-1111-1111-111111111111"
    )
    claims = {
        "iss": ISSUER,
        "sub": "preserved-keycloak-id",
        "email": "same@example.test",
        "koinon_identity_provider": "north-entra",
        "koinon_external_tid": "11111111-1111-1111-1111-111111111111",
        "koinon_external_oid": "22222222-2222-2222-2222-222222222222",
    }
    identity = verified_identity(policy, claims)
    assert identity.subject == ISSUER + "|preserved-keycloak-id"
    assert identity.external_subject == "22222222-2222-2222-2222-222222222222"
    for field, value in (
        ("iss", "https://other.test"),
        ("koinon_identity_provider", "other-provider"),
        ("koinon_external_tid", "33333333-3333-3333-3333-333333333333"),
        ("koinon_external_oid", None),
    ):
        with pytest.raises(AccessDenied):
            verified_identity(policy, {**claims, field: value})


def test_google_requires_signed_hosted_domain_and_stable_external_subject():
    policy = IdentityPolicy(
        "google", "google_workspace", ISSUER, "north-google", hosted_domains=("example.test",)
    )
    claims = {
        "iss": ISSUER,
        "sub": "broker-id",
        "email": "person@example.test",
        "koinon_identity_provider": "north-google",
        "koinon_google_hd": "example.test",
        "koinon_external_subject": "google-stable-id",
    }
    assert verified_identity(policy, claims).external_subject == "google-stable-id"
    for changes in (
        {"koinon_google_hd": None},
        {"koinon_google_hd": "evil-example.test"},
        {"koinon_external_subject": None},
    ):
        with pytest.raises(AccessDenied):
            verified_identity(policy, {**claims, **changes})


def test_overage_is_explicit_and_never_becomes_an_empty_authoritative_group_list():
    policy = IdentityPolicy("local", "keycloak", ISSUER, None)
    identity = verified_identity(
        policy,
        {
            "iss": ISSUER,
            "sub": "existing-id",
            "hasgroups": True,
            "_claim_names": {"groups": "src1"},
            "_claim_sources": {"src1": {"endpoint": "http://private.invalid"}},
        },
    )
    assert identity.requires_directory is True and identity.external_subject == "existing-id"
    assert not hasattr(identity, "directory_url")
    with pytest.raises(AccessDenied):
        verified_identity(
            policy, {"iss": ISSUER, "sub": "existing-id", "koinon_identity_provider": "unapproved-broker"}
        )


def test_only_current_complete_snapshots_map_explicit_groups_and_scope():
    now = datetime.now(UTC)
    rules = [
        MappingRule("rule-one", "group-one", "editor", "workspace-one"),
        MappingRule("rule-two", "group-two", "admin", None),
        MappingRule("disabled", "group-one", "admin", None, enabled=False),
    ]
    snapshot = DirectorySnapshot(
        "external-id", frozenset({"group-one"}), True, now, now + timedelta(minutes=5)
    )
    assert planned_grants(rules, snapshot, expected_subject="external-id", now=now) == [rules[0]]
    for broken in (
        DirectorySnapshot("other", snapshot.groups, True, now, snapshot.expires_at),
        DirectorySnapshot("external-id", snapshot.groups, False, now, snapshot.expires_at),
        DirectorySnapshot(
            "external-id", snapshot.groups, True, now - timedelta(minutes=10), now - timedelta(seconds=1)
        ),
    ):
        with pytest.raises(ServiceUnavailableException):
            planned_grants(rules, broken, expected_subject="external-id", now=now)
    assert planned_grants(rules, None, expected_subject="external-id", now=now, active=False) == []


def test_unknown_snapshot_completeness_and_future_or_unbounded_observation_fail_closed():
    now = datetime.now(UTC)
    for complete, observed, expiry in (
        ("unknown", now, now + timedelta(minutes=5)),
        (True, now + timedelta(minutes=2), now + timedelta(minutes=3)),
        (True, now, now + timedelta(hours=1)),
    ):
        with pytest.raises(ServiceUnavailableException):
            planned_grants(
                [],
                DirectorySnapshot("external", frozenset(), complete, observed, expiry),
                expected_subject="external",
                now=now,
            )
