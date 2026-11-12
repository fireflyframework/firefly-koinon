# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source startup independently enforces its isolated primary database identity."""

import pytest
from pyfly.container.exceptions import BeanCreationException
from test_source_migration_postgres import source_database as source_database


@pytest.fixture
def provisioned_source_processes(source_database, tmp_path, monkeypatch):
    """Exercise the deployment provisioner with freshly generated isolated credentials."""
    from uuid import uuid4

    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url
    from test_source_migration_postgres import load, upgrade_sources

    target, _, engine = source_database
    upgrade_sources(engine)
    generated = load("deploy/generate_local_configuration.py").generate(tmp_path / "private-processes")
    values = dict(line.split("=", 1) for line in (generated / "migration.env").read_text().splitlines())
    suffix = uuid4().hex[:10]
    urls = {}
    for key, value in values.items():
        if key == "KOINON_MIGRATION_DATABASE_URL":
            continue
        parsed = make_url(value)
        url = parsed.set(
            username=parsed.username + "_" + suffix,
            host=target.host,
            port=target.port,
            database=target.database,
        )
        urls[key] = url
        monkeypatch.setenv(key, url.render_as_string(hide_password=False))
    monkeypatch.setenv("KOINON_MIGRATION_DATABASE_URL", target.render_as_string(hide_password=False))
    try:
        load("deploy/provision_roles.py").provision(grants=True)
        yield target, urls
    finally:
        # These unique roles were created by this test; preexisting databases remain untouched.
        with psycopg.connect(target.render_as_string(hide_password=False), autocommit=True) as administrator:
            for url in urls.values():
                exists = administrator.execute(
                    "SELECT EXISTS(SELECT FROM pg_roles WHERE rolname=%s)",
                    (url.username,),
                ).fetchone()[0]
                if exists:
                    administrator.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(url.username)))
                    administrator.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(url.username)))


@pytest.mark.integration
@pytest.mark.parametrize(
    "role,overgrant",
    [
        ("api", None),
        ("worker", None),
        ("worker", "table"),
        ("worker", "column"),
        ("worker", "helper"),
        ("api", "mutator"),
    ],
)
async def test_actual_startup_accepts_only_exact_source_privileges(
    provisioned_source_processes, role, overgrant
):
    import psycopg
    from psycopg import sql
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.integrations.content_sources.process_readiness import (
        SourceProcessReadiness,
        register_source_process,
    )
    from koinon.integrations.content_sources.read_repository import SourceReadRepository
    from koinon.integrations.content_sources.structure_publication_guards import (
        ALL_SIGNATURES,
        ENTRYPOINTS,
        READ_ENTRYPOINTS,
        TABLE,
    )

    target, urls = provisioned_source_processes
    url = urls["KOINON_DATABASE_URL" if role == "api" else "KOINON_ANSWER_PUBLISHER_DATABASE_URL"]
    username = url.username
    functions = []
    with psycopg.connect(target.render_as_string(hide_password=False), autocommit=True) as administrator:
        if overgrant == "helper":
            functions.append(
                next(value for value in ALL_SIGNATURES if value not in (*ENTRYPOINTS, *READ_ENTRYPOINTS))
            )
        if overgrant == "mutator":
            functions.append(ENTRYPOINTS[0])
        for signature in functions:
            administrator.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION public." + signature + " TO {}").format(
                    sql.Identifier(username),
                )
            )
        if overgrant in {"table", "column"}:
            privilege = "UPDATE" if overgrant == "table" else "UPDATE (id)"
            administrator.execute(
                sql.SQL("GRANT " + privilege + " ON public.{} TO {}").format(
                    sql.Identifier(TABLE),
                    sql.Identifier(username),
                )
            )
    connection_url = url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    context = ApplicationContext(
        Config(
            {
                "koinon": {
                    "process": {"role": role},
                    "content_sources": {"enabled": True, "synchronization_enabled": True},
                    "answers": {
                        "release_proofs": {
                            "enabled": False,
                            "api_role": urls["KOINON_DATABASE_URL"].username,
                            "publisher_role": urls["KOINON_ANSWER_PUBLISHER_DATABASE_URL"].username,
                        }
                    },
                },
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "none", "url": connection_url}},
                },
            }
        )
    )
    context.register_bean(SourceReadRepository)
    register_source_process(context)
    try:
        if overgrant is None:
            await context.start()
            assert context.get_bean(SourceProcessReadiness).process.username == username
        else:
            with pytest.raises(BeanCreationException, match="Source process") as failure:
                await context.start()
            assert isinstance(failure.value.__cause__, ValueError)
    finally:
        await context.stop()


# Source-runtime composition must enforce its database identity independently of
# the separate answer-proof rollout.
@pytest.mark.parametrize("role", ["api", "worker"])
def test_synchronization_rejects_shared_primary_identity_when_answer_proofs_disabled(role):
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.integrations.content_sources.configuration import register_source_synchronization
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    context = ApplicationContext(
        Config(
            {
                "koinon": {
                    "process": {"role": role},
                    "answers": {
                        "release_proofs": {
                            "enabled": False,
                            "api_role": "catalog_api",
                            "publisher_role": "source_worker",
                        }
                    },
                },
                "pyfly": {"data": {"relational": {"url": "postgresql+asyncpg://shared@localhost/test"}}},
            }
        )
    )
    context.container.register_instance(
        ContentSourceSettings,
        ContentSourceSettings(enabled=True, synchronization_enabled=True),
    )
    with pytest.raises(ValueError, match="Source.*identity"):
        register_source_synchronization(context, controllers=role == "api")
