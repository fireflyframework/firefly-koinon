# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compatibility constructors must borrow the application-owned datasource."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

REPOSITORIES = (
    ("agent_token", "AgentTokenRepository"),
    ("audit", "AuditRepository"),
    ("candidate", "CandidateRepository"),
    ("chunk", "ChunkRepository"),
    ("conversation", "ConversationRepository"),
    ("cost", "CostRepository"),
    ("embedding_set", "EmbeddingSetRepository"),
    ("ingest_job", "IngestJobRepository"),
    ("knowledge", "KnowledgeRepository"),
    ("relation", "RelationRepository"),
    ("scope_purge", "ScopePurgeRepository"),
    ("source", "SourceRepository"),
    ("taxonomy", "TaxonomyRepository"),
    ("workspace", "WorkspaceRepository"),
)
URL = "postgresql+asyncpg://application:private@localhost/knowledge"


def named_registry(url=URL):
    source = SimpleNamespace(engine=SimpleNamespace(url=make_url(url)), sessionmaker=object())
    requested = []

    def get(name):
        requested.append(name)
        assert name == "documents"
        return source

    return SimpleNamespace(get=get), source, requested


@pytest.mark.parametrize(("module", "name"), REPOSITORIES)
def test_constructor_requires_registry_without_opening_a_pool(module, name, monkeypatch):
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine",
        lambda *args, **kwargs: pytest.fail("Repository attempted to own a new pool"),
    )
    repository = getattr(import_module(f"flycanon.models.repositories.{module}_repository"), name)
    with pytest.raises(RuntimeError, match="ApplicationContext-owned DataSourceRegistry"):
        repository.from_url(URL)


@pytest.mark.parametrize(("module", "name"), REPOSITORIES)
def test_constructor_borrows_exact_named_factory_and_engine(module, name):
    repository = getattr(import_module(f"flycanon.models.repositories.{module}_repository"), name)
    registry, source, requested = named_registry()
    instance = repository.from_url(URL, registry=registry, datasource_name="documents", echo=True)
    assert instance._session_factory is source.sessionmaker
    assert instance.engine is source.engine
    assert requested == ["documents"]


@pytest.mark.parametrize(("module", "name"), REPOSITORIES)
def test_constructor_rejects_different_credentials_without_disclosing_them(module, name):
    repository = getattr(import_module(f"flycanon.models.repositories.{module}_repository"), name)
    registry, _, _ = named_registry()
    with pytest.raises(ValueError, match="match the named native datasource") as error:
        repository.from_url(
            URL.replace(":private@", ":different@"), registry=registry, datasource_name="documents"
        )
    assert "private" not in str(error.value) and "different" not in str(error.value)


def test_workspace_admin_constructor_borrows_separate_named_owner():
    from flycanon.models.repositories.workspace_repository import WorkspaceRepository

    runtime = SimpleNamespace(engine=SimpleNamespace(url=make_url(URL)), sessionmaker=object())
    admin_url = URL.replace("application:", "administrator:")
    admin = SimpleNamespace(engine=SimpleNamespace(url=make_url(admin_url)), sessionmaker=object())
    sources = {"documents": runtime, "documents_admin": admin}
    instance = WorkspaceRepository.from_urls(
        URL,
        admin_database_url=admin_url,
        registry=SimpleNamespace(get=sources.__getitem__),
        datasource_name="documents",
        admin_datasource_name="documents_admin",
    )
    assert instance._session_factory is runtime.sessionmaker
    assert instance._admin_session_factory is admin.sessionmaker
    assert instance.has_admin_engine is True


def test_workspace_identical_urls_reuse_runtime_binding():
    from flycanon.models.repositories.workspace_repository import WorkspaceRepository

    registry, source, requested = named_registry()
    instance = WorkspaceRepository.from_urls(
        URL, admin_database_url=URL, registry=registry, datasource_name="documents"
    )
    assert instance._admin_session_factory is source.sessionmaker
    assert instance.has_admin_engine is False
    assert requested == ["documents"]


def test_identical_urls_do_not_share_resources_between_application_registries():
    from flycanon.models.repositories.source_repository import SourceRepository

    first, first_source, _ = named_registry()
    second, second_source, _ = named_registry()
    one = SourceRepository.from_url(URL, registry=first, datasource_name="documents")
    two = SourceRepository.from_url(URL, registry=second, datasource_name="documents")
    assert one.engine is first_source.engine
    assert two.engine is second_source.engine
    assert one.engine is not two.engine
    assert one.session_factory is not two.session_factory


def test_missing_named_binding_does_not_fall_back_to_primary():
    from flycanon.models.repositories.source_repository import SourceRepository

    registry = SimpleNamespace(get={}.__getitem__)
    with pytest.raises(KeyError):
        SourceRepository.from_url(URL, registry=registry, datasource_name="documents")


def test_malformed_url_does_not_expose_sensitive_fragments():
    from flycanon.models.repositories._engine import build_engine

    registry, _, _ = named_registry()
    with pytest.raises(ValueError) as error:
        build_engine(
            "postgresql+asyncpg://user:synthetic-secret-token",
            registry=registry,
            datasource_name="documents",
        )
    assert "synthetic-secret-token" not in str(error.value)
    assert error.value.__suppress_context__
