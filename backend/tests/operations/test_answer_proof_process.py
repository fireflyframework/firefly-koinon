# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Release attestation credentials are specific to one process boundary."""

import pytest

from koinon.operations.process import process_configuration


def configuration(role, database_role):
    return {
        "koinon": {
            "process": {"role": role},
            "answers": {
                "release_proofs": {
                    "enabled": True,
                    "api_role": "catalog_api",
                    "publisher_role": "answer_worker",
                }
            },
        },
        "pyfly": {
            "data": {
                "relational": {
                    "url": f"postgresql+asyncpg://{database_role}@127.0.0.1/koinon",
                }
            }
        },
    }


@pytest.mark.parametrize("role,wrong_role", [("api", "answer_worker"), ("worker", "catalog_api")])
def test_enabled_proof_publication_rejects_a_cross_process_primary_role(role, wrong_role):
    with pytest.raises(ValueError, match="proof.*role"):
        process_configuration(configuration(role, wrong_role), role=role)


@pytest.mark.parametrize("role,database_role", [("api", "catalog_api"), ("worker", "answer_worker")])
def test_enabled_proof_publication_preserves_the_matching_primary_connection(role, database_role):
    supplied = configuration(role, database_role)
    actual = process_configuration(supplied, role=role)
    assert actual["pyfly"]["data"]["relational"]["url"] == supplied["pyfly"]["data"]["relational"]["url"]
    assert actual["pyfly"]["scheduling"]["enabled"] is (role == "worker")


def test_disabled_rollout_preserves_existing_local_process_configuration():
    actual = process_configuration({"koinon": {"process": {"role": "worker"}}}, role="worker")
    assert actual["pyfly"]["scheduling"]["enabled"] is True


def test_operator_aliases_enable_proof_publication_with_explicit_process_identities(monkeypatch):
    from koinon.operations.configuration import environment_configuration

    monkeypatch.setenv("KOINON_DATABASE_URL", "postgresql+asyncpg://catalog_api@127.0.0.1/koinon")
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "https://identity.example.test/realms/koinon")
    monkeypatch.delenv("PYFLY_DATA_RELATIONAL_URL", raising=False)
    monkeypatch.setenv("KOINON_ANSWER_PROOFS_ENABLED", "true")
    monkeypatch.setenv("KOINON_ANSWER_PROOFS_API_ROLE", "catalog_api")
    monkeypatch.setenv("KOINON_ANSWER_PROOFS_PUBLISHER_ROLE", "answer_worker")
    monkeypatch.setenv("KOINON_PROCESS_ROLE", "worker")
    actual = environment_configuration()
    assert actual["koinon"]["process"]["role"] == "worker"
    assert actual["koinon"]["answers"]["release_proofs"] == {
        "enabled": True,
        "api_role": "catalog_api",
        "publisher_role": "answer_worker",
    }


@pytest.mark.parametrize("role", ["api", "worker"])
def test_enabled_composition_installs_mandatory_role_readiness_and_publisher(role):
    from test_role_composition import config

    from koinon.answers.configuration import AnswerProofReadiness
    from koinon.answers.release_proofs import AnswerReleaseProofPublisher
    from koinon.app import create_application

    values = config(False)
    values.update(configuration(role, "answer_worker" if role == "worker" else "catalog_api"))
    values["koinon"].update(config(False)["koinon"])
    application = create_application(values, role=role)
    assert application.state.context.container.contains_type(AnswerProofReadiness)
    assert application.state.context.container.contains_type(AnswerReleaseProofPublisher)


@pytest.mark.parametrize("role", ["api", "worker"])
@pytest.mark.parametrize("enabled", [True, False])
def test_source_composition_honors_activation_and_process_boundaries(role, enabled):
    import base64
    import secrets

    from test_role_composition import config

    from koinon.app import create_application
    from koinon.integrations.content_sources.mapping_api import SourceMappingController
    from koinon.integrations.content_sources.process_readiness import SourceProcessReadiness
    from koinon.integrations.content_sources.sync_worker import SourceSyncWorker

    values = config(False)
    values.update(configuration(role, "answer_worker" if role == "worker" else "catalog_api"))
    values["koinon"].update(config(False)["koinon"])
    values["koinon"]["answers"]["release_proofs"]["enabled"] = False
    values["koinon"]["content_sources"] = {
        "enabled": True,
        "synchronization_enabled": enabled,
        "master_key": base64.b64encode(secrets.token_bytes(32)).decode(),
    }
    application = create_application(values, role=role)
    container = application.state.context.container
    assert container.contains_type(SourceProcessReadiness) is enabled
    assert container.contains_type(SourceSyncWorker) is (enabled and role == "worker")
    assert container.contains_type(SourceMappingController) is (enabled and role == "api")
    if role == "worker":
        assert not hasattr(application, "router")
