# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve native file configuration and explicit product environment aliases."""

import json
import math
import os
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from pyfly.config.properties.data import parse_bool
from pyfly.core import Config
from sqlalchemy.engine import make_url

from koinon.security.settings import OidcSettings

SOURCES = ("canon", "canon_admin", "structured", "structured_admin")


def explicit(name: str) -> str | None:
    return os.environ.get("KOINON_" + name)


def integer(value, name: str, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, (bool, float)):
            raise ValueError()
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(name + " must be an integer") from None
    if not minimum <= result <= maximum:
        raise ValueError(name + " is outside its supported range")
    return result


def number(value, name: str, minimum: float, maximum: float) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(name + " must be finite") from None
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(name + " is outside its supported range")
    return result


def boolean(value, name: str) -> bool:
    try:
        return parse_bool(value, name)
    except ValueError:
        raise ValueError(name + " must be a boolean") from None


def text(value, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(name + " must be a string")
    return value


def environment_configuration() -> dict:
    path = explicit("CONFIG_FILE")
    if path:
        try:
            if not Path(path).is_file():
                raise ValueError("Missing configuration file")
            loaded = Config.from_file(path, load_defaults=False)
        except Exception:
            raise ValueError("Could not load the operator configuration file") from None
        base = {section: loaded.get_section(section).copy() for section in ("pyfly", "koinon")}
    else:
        base = {}
    source = Config(deepcopy(base))

    def value(alias, key, default):
        selected = explicit(alias)
        return selected if selected is not None else source.get(key, default)

    def string(alias, key, default=""):
        return text(value(alias, key, default), alias)

    issuer = string("OIDC_ISSUER", "koinon.security.issuer")
    provider = string("OIDC_PROVIDER", "koinon.security.provider", "keycloak")
    prefix = issuer.rstrip("/") + "/protocol/openid-connect" if provider == "keycloak" and issuer else ""
    callback = string(
        "OIDC_REDIRECT_URI",
        "koinon.security.redirect_uri",
        "http://127.0.0.1:18781/login/oauth2/code/koinon",
    )
    local = urlsplit(callback).scheme == "http" and urlsplit(callback).hostname in (
        "127.0.0.1",
        "localhost",
        "::1",
    )
    security = OidcSettings(
        issuer=issuer,
        jwks_uri=string("OIDC_JWKS_URI", "koinon.security.jwks_uri", prefix + "/certs" if prefix else ""),
        authorization_uri=string(
            "OIDC_AUTHORIZATION_URI", "koinon.security.authorization_uri", prefix + "/auth" if prefix else ""
        ),
        token_uri=string("OIDC_TOKEN_URI", "koinon.security.token_uri", prefix + "/token" if prefix else ""),
        client_id=string("OIDC_CLIENT_ID", "koinon.security.client_id", "koinon-browser"),
        client_secret=string("OIDC_CLIENT_SECRET", "koinon.security.client_secret"),
        api_audience=string("OIDC_API_AUDIENCE", "koinon.security.api_audience", "koinon-api"),
        redirect_uri=callback,
        success_uri=string(
            "FRONTEND_URI", "koinon.security.success_uri", "http://127.0.0.1:18782" if local else "/"
        ),
        cookie_secure=boolean(
            value("COOKIE_SECURE", "koinon.security.cookie_secure", not local), "COOKIE_SECURE"
        ),
        require_iss=boolean(
            value("OIDC_REQUIRE_ISS", "koinon.security.require_iss", provider == "keycloak"),
            "OIDC_REQUIRE_ISS",
        ),
    )
    koinon = base.setdefault("koinon", {})
    koinon["security"] = asdict(security)
    koinon.setdefault("legacy", {})["enabled"] = boolean(
        value("LEGACY_ENABLED", "koinon.legacy.enabled", True), "LEGACY_ENABLED"
    )
    assistants = koinon.setdefault("assistants", {})
    allowed = value("ASSISTANTS_ALLOWED_PROVIDER_HOSTS", "koinon.assistants.allowed_provider_hosts", [])
    if isinstance(allowed, str):
        try:
            allowed = json.loads(allowed)
        except ValueError:
            raise ValueError("ASSISTANTS_ALLOWED_PROVIDER_HOSTS must be a JSON list") from None
    if not isinstance(allowed, list) or not all(isinstance(host, str) and host.strip() for host in allowed):
        raise ValueError("ASSISTANTS_ALLOWED_PROVIDER_HOSTS must be a list of host names")
    assistants["allowed_provider_hosts"] = allowed
    master = string("MASTER_KEY", "koinon.assistants.master_key")
    if master or explicit("MASTER_KEY") is not None:
        assistants["master_key"] = master
    identity = koinon.setdefault("identity", {})
    identity_hosts = value("IDENTITY_ALLOWED_PROVIDER_HOSTS", "koinon.identity.allowed_provider_hosts", [])
    if isinstance(identity_hosts, str):
        try:
            identity_hosts = json.loads(identity_hosts)
        except ValueError:
            raise ValueError("IDENTITY_ALLOWED_PROVIDER_HOSTS must be a JSON list") from None
    if not isinstance(identity_hosts, list) or not all(
        isinstance(host, str) and host.strip() for host in identity_hosts
    ):
        raise ValueError("IDENTITY_ALLOWED_PROVIDER_HOSTS must be a list of host names")
    identity["allowed_provider_hosts"] = identity_hosts
    identity_origins = value(
        "IDENTITY_ALLOWED_PROVIDER_ORIGINS", "koinon.identity.allowed_provider_origins", []
    )
    if isinstance(identity_origins, str):
        try:
            identity_origins = json.loads(identity_origins)
        except ValueError:
            raise ValueError("IDENTITY_ALLOWED_PROVIDER_ORIGINS must be a JSON list") from None
    if not isinstance(identity_origins, list) or not all(
        isinstance(origin, str) and origin.strip() for origin in identity_origins
    ):
        raise ValueError("IDENTITY_ALLOWED_PROVIDER_ORIGINS must be a list of origins")
    identity["allowed_provider_origins"] = identity_origins
    for alias, key in (
        ("IDENTITY_MASTER_KEY", "master_key"),
        ("IDENTITY_BROKER_ADMIN_CLIENT_ID", "broker_admin_client_id"),
        ("IDENTITY_BROKER_ADMIN_SECRET", "broker_admin_secret"),
    ):
        identity[key] = string(alias, "koinon.identity." + key)
    identity["snapshot_ttl_seconds"] = integer(
        value("IDENTITY_SNAPSHOT_TTL_SECONDS", "koinon.identity.snapshot_ttl_seconds", 60),
        "IDENTITY_SNAPSHOT_TTL_SECONDS",
        1,
        300,
    )
    pyfly = base.setdefault("pyfly", {})
    pyfly.setdefault("agentic", {}).setdefault("enabled", True)
    relational = pyfly.setdefault("data", {}).setdefault("relational", {})
    url = string("DATABASE_URL", "pyfly.data.relational.url")
    if os.getenv("PYFLY_DATA_RELATIONAL_URL") is not None:
        url = os.environ["PYFLY_DATA_RELATIONAL_URL"]
    if not url:
        raise ValueError("Configure the primary database URL")
    relational.update(enabled=True, url=url)
    policy = string("SCHEMA_POLICY", "pyfly.data.relational.ddl-auto", "validate")
    if policy not in ("validate", "none"):
        raise ValueError("Runtime DDL is disabled; use the migration job")
    if boolean(source.get("pyfly.data.relational.migrations.enabled", False), "data.migrations.enabled"):
        raise ValueError("Runtime migrations are disabled; use the separate migration job")
    relational["ddl-auto"] = policy

    def pool(alias, path, default_size):
        def inherited(key, default):
            return source.get("pyfly.data.relational.pool." + key, default)

        return {
            "size": integer(
                value(alias + "_POOL_SIZE", path + ".pool.size", inherited("size", default_size)),
                alias + "_POOL_SIZE",
                1,
                100,
            ),
            "max-overflow": integer(
                value(
                    alias + "_POOL_MAX_OVERFLOW", path + ".pool.max-overflow", inherited("max-overflow", 0)
                ),
                alias + "_POOL_MAX_OVERFLOW",
                0,
                100,
            ),
            "timeout": number(
                value(alias + "_POOL_TIMEOUT", path + ".pool.timeout", inherited("timeout", 5)),
                alias + "_POOL_TIMEOUT",
                0.1,
                120,
            ),
            "recycle": integer(
                value(alias + "_POOL_RECYCLE", path + ".pool.recycle", inherited("recycle", 1800)),
                alias + "_POOL_RECYCLE",
                -1,
                86400,
            ),
            "pre-ping": boolean(
                value(alias + "_POOL_PRE_PING", path + ".pool.pre-ping", inherited("pre-ping", False)),
                alias + "_POOL_PRE_PING",
            ),
        }

    def connect_arguments(alias, path, target):
        arguments = dict(source.get(path + ".connect-args", {}) or {})
        inherited = (
            source.get("pyfly.data.relational.connect-args", {})
            if make_url(target).drivername == make_url(url).drivername
            else {}
        )
        if make_url(target).drivername == "postgresql+asyncpg":
            arguments["timeout"] = number(
                value(
                    alias + "_CONNECT_TIMEOUT", path + ".connect-args.timeout", inherited.get("timeout", 5)
                ),
                alias + "_CONNECT_TIMEOUT",
                0.1,
                120,
            )
            arguments["command_timeout"] = number(
                value(
                    alias + "_COMMAND_TIMEOUT",
                    path + ".connect-args.command_timeout",
                    inherited.get("command_timeout", 30),
                ),
                alias + "_COMMAND_TIMEOUT",
                1,
                3600,
            )
        return arguments

    relational["pool"] = pool("DATABASE", "pyfly.data.relational", 5)
    relational["connect-args"] = connect_arguments("DATABASE", "pyfly.data.relational", url)
    relational.setdefault("health", {})["timeout"] = number(
        value("DATABASE_HEALTH_TIMEOUT", "pyfly.data.relational.health.timeout", 2),
        "DATABASE_HEALTH_TIMEOUT",
        0.1,
        10,
    )
    named = relational.setdefault("datasources", {})
    for name in SOURCES:
        prefix_path = "pyfly.data.relational.datasources." + name
        target = string(name.upper() + "_DATABASE_URL", prefix_path + ".url")
        selected_pool = pool(name.upper(), prefix_path, 1 if name.endswith("_admin") else 2)
        if target:
            settings = named.setdefault(name, {})
            settings.update(url=target, pool=selected_pool)
            settings["connect-args"] = connect_arguments(name.upper(), prefix_path, target)
        elif explicit(name.upper() + "_DATABASE_URL") is not None:
            named.pop(name, None)
    configure_policies(koinon, value)
    configure_storage(koinon, value)
    return base


def configure_policies(koinon, value):
    policies = (
        ("operations", "worker_concurrency", "WORKER_CONCURRENCY", 1, 1, 16),
        ("operations", "max_queued_per_subject", "MAX_QUEUED_PER_SUBJECT", 50, 1, 10000),
        ("operations", "job_lease_seconds", "JOB_LEASE_SECONDS", 60, 5, 3600),
        ("operations", "max_index_workspaces", "MAX_INDEX_WORKSPACES", 32, 1, 128),
        ("assistants", "lease_seconds", "ASSISTANT_LEASE_SECONDS", 60, 5, 3600),
        ("assistants", "run_timeout_seconds", "ASSISTANT_RUN_TIMEOUT", 180, 10, 3600),
        ("assistants", "max_history_messages", "ASSISTANT_MAX_HISTORY_MESSAGES", 40, 2, 200),
        ("assistants", "max_history_tokens", "ASSISTANT_MAX_HISTORY_TOKENS", 8192, 256, 131072),
        ("assistants", "max_context_tokens", "ASSISTANT_MAX_CONTEXT_TOKENS", 32768, 1024, 262144),
        ("assistants", "tool_result_tokens", "ASSISTANT_TOOL_RESULT_TOKENS", 4096, 128, 32768),
        ("tokens", "max_active_per_user", "TOKEN_MAX_ACTIVE_PER_USER", 100, 1, 10000),
        ("tokens", "max_lifetime_days", "TOKEN_MAX_LIFETIME_DAYS", 365, 1, 3650),
    )
    for section, key, alias, default, minimum, maximum in policies:
        selected = value(alias, "koinon." + section + "." + key, default)
        koinon.setdefault(section, {})[key] = integer(selected, alias, minimum, maximum)


def configure_storage(koinon, value):
    fields = {
        "documents": {
            "azure_account_url": "DOCUMENT_STORAGE_AZURE_ACCOUNT_URL",
            "azure_container": "DOCUMENT_STORAGE_AZURE_CONTAINER",
            "azure_prefix": "DOCUMENT_STORAGE_AZURE_PREFIX",
            "gcs_bucket": "DOCUMENT_STORAGE_GCS_BUCKET",
            "gcs_project": "DOCUMENT_STORAGE_GCS_PROJECT",
            "gcs_prefix": "DOCUMENT_STORAGE_GCS_PREFIX",
            "gcs_endpoint_url": "DOCUMENT_STORAGE_GCS_ENDPOINT_URL",
            "request_timeout_seconds": "DOCUMENT_STORAGE_REQUEST_TIMEOUT_SECONDS",
            "max_object_bytes": "DOCUMENT_STORAGE_MAX_OBJECT_BYTES",
            "backend": "DOCUMENT_STORAGE_BACKEND",
            "root": "DOCUMENT_STORAGE_ROOT",
            "store_originals": "DOCUMENT_STORE_ORIGINALS",
            "s3_bucket": "DOCUMENT_STORAGE_S3_BUCKET",
            "s3_prefix": "DOCUMENT_STORAGE_S3_PREFIX",
            "s3_endpoint_url": "DOCUMENT_STORAGE_S3_ENDPOINT_URL",
            "s3_region": "DOCUMENT_STORAGE_S3_REGION",
        },
        "structured": {
            "azure_account_url": "STRUCTURED_STORAGE_AZURE_ACCOUNT_URL",
            "azure_container": "STRUCTURED_STORAGE_AZURE_CONTAINER",
            "azure_prefix": "STRUCTURED_STORAGE_AZURE_PREFIX",
            "gcs_bucket": "STRUCTURED_STORAGE_GCS_BUCKET",
            "gcs_project": "STRUCTURED_STORAGE_GCS_PROJECT",
            "gcs_prefix": "STRUCTURED_STORAGE_GCS_PREFIX",
            "gcs_endpoint_url": "STRUCTURED_STORAGE_GCS_ENDPOINT_URL",
            "request_timeout_seconds": "STRUCTURED_STORAGE_REQUEST_TIMEOUT_SECONDS",
            "max_object_bytes": "STRUCTURED_STORAGE_MAX_OBJECT_BYTES",
            "backend": "STRUCTURED_STORAGE_BACKEND",
            "root": "STRUCTURED_STORAGE_ROOT",
            "presign_ttl_seconds": "STRUCTURED_STORAGE_PRESIGN_TTL_SECONDS",
        },
        "attachments": {
            "azure_account_url": "ATTACHMENT_STORAGE_AZURE_ACCOUNT_URL",
            "azure_container": "ATTACHMENT_STORAGE_AZURE_CONTAINER",
            "azure_prefix": "ATTACHMENT_STORAGE_AZURE_PREFIX",
            "gcs_bucket": "ATTACHMENT_STORAGE_GCS_BUCKET",
            "gcs_project": "ATTACHMENT_STORAGE_GCS_PROJECT",
            "gcs_prefix": "ATTACHMENT_STORAGE_GCS_PREFIX",
            "gcs_endpoint_url": "ATTACHMENT_STORAGE_GCS_ENDPOINT_URL",
            "backend": "ATTACHMENT_STORAGE_BACKEND",
            "root": "ATTACHMENT_STORAGE_ROOT",
            "s3_bucket": "ATTACHMENT_STORAGE_S3_BUCKET",
            "s3_prefix": "ATTACHMENT_STORAGE_S3_PREFIX",
            "s3_endpoint_url": "ATTACHMENT_STORAGE_S3_ENDPOINT_URL",
            "s3_region": "ATTACHMENT_STORAGE_S3_REGION",
            "s3_kms_key_id": "ATTACHMENT_STORAGE_S3_KMS_KEY_ID",
            "request_timeout_seconds": "ATTACHMENT_STORAGE_REQUEST_TIMEOUT_SECONDS",
            "max_object_bytes": "ATTACHMENT_STORAGE_MAX_OBJECT_BYTES",
        },
    }
    for domain, mapping in fields.items():
        for key, alias in mapping.items():
            selected = value(alias, "koinon.storage." + domain + "." + key, None)
            if selected is None:
                continue
            if key == "store_originals":
                selected = boolean(selected, alias)
            elif key == "presign_ttl_seconds":
                selected = integer(selected, alias, 0, 604800)
            elif key in {"request_timeout_seconds", "max_object_bytes"}:
                selected = integer(
                    selected, alias, 1, 60 if key == "request_timeout_seconds" else 64 * 1024 * 1024
                )
            else:
                selected = text(selected, alias)
                if "\0" in selected:
                    raise ValueError(alias + " contains an invalid character")
            if key == "backend" and selected not in (
                {"localfs", "s3", "azure", "gcs"}
                if domain == "documents"
                else {"local", "s3", "azure", "gcs"}
                if domain == "attachments"
                else {"local", "s3", "gcs", "azure"}
            ):
                raise ValueError(alias + " names an unsupported backend")
            if key in {"s3_endpoint_url", "azure_account_url", "gcs_endpoint_url"} and selected:
                parsed = urlsplit(text(selected, alias))
                if (
                    not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(alias + " must be an endpoint without credentials")
                if parsed.scheme != "https" and not (
                    parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                ):
                    raise ValueError(alias + " requires HTTPS outside loopback")
            koinon.setdefault("storage", {}).setdefault(domain, {})[key] = selected
