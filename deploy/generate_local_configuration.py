# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generate local-only credentials into a new private directory without printing them."""

import argparse
import base64
import os
import secrets
from pathlib import Path


def generate(directory: Path):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = {
        name: secrets.token_urlsafe(36)
        for name in (
            "database_admin_password",
            "keycloak_database_password",
            "keycloak_admin_password",
            "demo_password",
            "oidc_client_secret",
        )
    }

    def write(name, value):
        descriptor = os.open(
            directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "w") as target:
            target.write(value + "\n")

    for name, value in values.items():
        write(name, value)
    master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    write("master_key", master_key)
    mcp_oauth_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    write("mcp_oauth_key", mcp_oauth_key)
    runtime = {
        "KOINON_OIDC_ISSUER": "http://127.0.0.1:18784/realms/koinon",
        "KOINON_OIDC_CLIENT_ID": "koinon-browser",
        "KOINON_OIDC_API_AUDIENCE": "koinon-api",
        "KOINON_OIDC_CLIENT_SECRET": values["oidc_client_secret"],
        "KOINON_FRONTEND_URI": "http://127.0.0.1:18782",
        "KOINON_SCHEMA_POLICY": "validate",
        "KOINON_CACHE_ENABLED": "true",
        "KOINON_CACHE_PROVIDER": "postgres",
        "KOINON_CACHE_DATASOURCE": "primary",
        "KOINON_MASTER_KEY": master_key,
        "KOINON_ASSISTANTS_ALLOWED_PROVIDER_HOSTS": '["127.0.0.1","localhost"]',
        "PYFLY_SERVER_HOST": "127.0.0.1",
        "PYFLY_SERVER_PORT": "18781",
        "KOINON_MCP_ENABLED": "true",
        "KOINON_MCP_OAUTH_ENABLED": "true",
        "KOINON_MCP_OAUTH_ENCRYPTION_KEY": mcp_oauth_key,
    }
    for key, role in (
        ("KOINON_DATABASE_URL", "koinon_catalog"),
        ("KOINON_CANON_DATABASE_URL", "koinon_canon"),
        ("KOINON_CANON_ADMIN_DATABASE_URL", "koinon_canon_admin"),
        ("KOINON_STRUCTURED_DATABASE_URL", "koinon_structured"),
        ("KOINON_STRUCTURED_ADMIN_DATABASE_URL", "koinon_structured_admin"),
    ):
        runtime[key] = (
            f"postgresql+asyncpg://{role}:{secrets.token_urlsafe(36)}@127.0.0.1:18783/koinon"
        )
    runtime["PYFLY_DATA_RELATIONAL_URL"] = runtime["KOINON_DATABASE_URL"]
    runtime["FLYCANON_DATABASE_URL"] = runtime["KOINON_CANON_DATABASE_URL"]
    runtime["FLYCANON_ADMIN_DATABASE_URL"] = runtime["KOINON_CANON_ADMIN_DATABASE_URL"]
    runtime["FLYQUERY_DATABASE_URL"] = runtime["KOINON_STRUCTURED_DATABASE_URL"]
    runtime["FLYQUERY_DATABASE_URL_ADMIN"] = runtime[
        "KOINON_STRUCTURED_ADMIN_DATABASE_URL"
    ]
    migration = {
        key: value
        for key, value in runtime.items()
        if key.startswith("KOINON_") and key.endswith("_DATABASE_URL")
    }
    migration["KOINON_DATABASE_URL"] = runtime["KOINON_DATABASE_URL"]
    migration["KOINON_MIGRATION_DATABASE_URL"] = (
        f"postgresql+asyncpg://koinon_migrator:{values['database_admin_password']}@127.0.0.1:18783/koinon"
    )
    write("runtime.env", "\n".join(f"{key}={value}" for key, value in runtime.items()))
    write(
        "migration.env", "\n".join(f"{key}={value}" for key, value in migration.items())
    )
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(
        "Private local configuration generated at",
        generate(parser.parse_args().directory),
    )
