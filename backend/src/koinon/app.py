# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One native context for catalog, security, jobs and retained knowledge domains."""

import importlib.util
from contextlib import AsyncExitStack, asynccontextmanager
from copy import deepcopy
from json import JSONDecodeError

from pydantic import ValidationError
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config, pyfly_application
from pyfly.kernel.exceptions import PyFlyException
from pyfly.web.adapters.fastapi.app import create_app
from pyfly.web.adapters.starlette.errors import global_exception_handler

from koinon import __version__
from koinon.api.controllers.audit import AuditController
from koinon.api.controllers.catalog import CatalogController
from koinon.api.controllers.context import ContextController
from koinon.api.controllers.jobs import JobController
from koinon.api.controllers.memberships import MembershipController
from koinon.configuration import ApplicationConfiguration
from koinon.mcp.connection import McpConnectionService
from koinon.mcp.controllers import McpConnectionController
from koinon.mcp.endpoints import resolve_mcp_configuration
from koinon.mcp.http import McpHttpBoundary
from koinon.mcp.private_reviews import file_upload_preparer, private_review_reader
from koinon.mcp.read_capture import native_read_capture
from koinon.mcp.server import create_mcp_server
from koinon.mcp.settings import McpSettings
from koinon.security.configuration import SecurityConfiguration, native_security_defaults
from koinon.security.controllers import AuthController
from koinon.security.settings import OidcSettings
from koinon.web.capabilities import CapabilitiesController, CapabilityRegistry, HealthController
from koinon.web.domain_errors import register_domain_problems
from koinon.web.legacy_security import LegacyMembershipFilter, LegacyOperationPolicies
from koinon.web.projection import register_controller, register_optional_domain


@pyfly_application(name="firefly koinon", version=__version__, scan_packages=["koinon.catalog"])
class KoinonApplication:
    """Compatibility bootstrap for native Data slices."""


def merge_configuration(base: dict, overlay: dict) -> dict:
    result = deepcopy(base)
    for key, value in overlay.items():
        result[key] = (
            merge_configuration(result[key], value)
            if isinstance(result.get(key), dict) and isinstance(value, dict)
            else deepcopy(value)
        )
    return result


def create_application(config: dict):
    settings = Config(config).bind(OidcSettings)
    defaults = {
        "koinon": {"knowledge": {"require_connections": True}},
        "pyfly": {
            "cqrs": {"enabled": True},
            "agentic": {"enabled": True},
            "eda": {"provider": "memory"},
            "aop": {"enabled": True},
            "web": {"actuator": {"enabled": False}, "problem-details": {"enabled": True}},
        },
    }
    native_defaults = native_security_defaults(settings)
    values = merge_configuration(merge_configuration(defaults, native_defaults), config)
    mandatory = deepcopy(native_defaults)
    mandatory["pyfly"]["session"].pop("store")
    mandatory["pyfly"]["session"].pop("postgres")
    mandatory["pyfly"]["session"].pop("concurrency")
    values = merge_configuration(values, mandatory)
    values = resolve_mcp_configuration(values)
    context = ApplicationContext(Config(values))
    mcp_settings = Config(values).bind(McpSettings)
    context.container.register_instance(McpSettings, mcp_settings)
    registry = CapabilityRegistry()
    context.container.register_instance(CapabilityRegistry, registry)
    context.container.register_instance(LegacyOperationPolicies, LegacyOperationPolicies())
    for package in (
        "koinon.catalog",
        "koinon.jobs",
        "koinon.assistants",
        "koinon.organization_chat",
        "koinon.organization_knowledge",
        "koinon.organization_branding",
        "koinon.organization_people",
        "koinon.corporate_profiles",
        "koinon.profiles",
        "koinon.tokens",
        "koinon.authorized_applications",
        "koinon.mcp_auth",
        "koinon.mcp_applications",
        "koinon.operations",
        "koinon.corporate_identity",
        "koinon.evidence",
        "koinon.exports",
        "koinon.sharing",
        "koinon.storage",
    ):
        scan_package(package, context.container)
    for cls in (
        ApplicationConfiguration,
        SecurityConfiguration,
        McpConnectionService,
        AuthController,
        HealthController,
        LegacyMembershipFilter,
    ):
        context.register_bean(cls)
    for cls in (
        ContextController,
        McpConnectionController,
        CatalogController,
        MembershipController,
        AuditController,
        JobController,
        CapabilitiesController,
    ):
        register_controller(context, cls)
    if (
        Config(values).get("koinon.knowledge.enabled", True)
        and importlib.util.find_spec("koinon.knowledge") is not None
    ):
        scan_package("koinon.knowledge", context.container)
        for cls in list(context.container.registered_types()):
            if cls.__module__.startswith("koinon.knowledge") and getattr(cls, "__pyfly_stereotype__", "") in (
                "controller",
                "rest_controller",
            ):
                register_controller(context, cls)
    for cls in list(context.container.registered_types()):
        if cls.__module__.startswith(
            (
                "koinon.assistants",
                "koinon.organization_chat",
                "koinon.organization_knowledge",
                "koinon.organization_branding",
                "koinon.organization_people",
                "koinon.corporate_profiles",
                "koinon.profiles",
                "koinon.tokens",
                "koinon.authorized_applications",
                "koinon.mcp_applications",
                "koinon.corporate_identity",
                "koinon.evidence",
                "koinon.exports",
                "koinon.sharing",
            )
        ) and getattr(cls, "__pyfly_stereotype__", "") in ("controller", "rest_controller"):
            register_controller(context, cls)
    legacy_enabled = Config(values).get("koinon.legacy.enabled", True)
    for package, domain in (("flycanon", "canon"), ("flyquery", "structured")):
        registry.domains[domain] = (
            register_optional_domain(context, package, domain)
            if legacy_enabled
            else {
                "installed": importlib.util.find_spec(package) is not None,
                "registered": False,
                "reason": "Optional domain is disabled",
            }
        )

    @asynccontextmanager
    async def lifespan(app):
        await context.start()
        try:
            async with AsyncExitStack() as stack:
                if mcp_settings.enabled:
                    await stack.enter_async_context(app.state.mcp_server.session_manager.run())
                yield
        finally:
            await context.stop()

    app = create_app(
        title="firefly koinon",
        version=__version__,
        context=context,
        lifespan=lifespan,
        docs_enabled=False,
        actuator_enabled=False,
    )
    for exception in (PyFlyException, ValidationError, JSONDecodeError):
        app.add_exception_handler(exception, global_exception_handler)
    register_domain_problems(app)
    if mcp_settings.enabled:
        from koinon.mcp_auth.http import install_oauth
        from koinon.mcp_auth.service import McpOAuthService

        async def canonical_bearer(raw):
            return await context.get_bean(McpOAuthService).canonical_bearer(raw)

        async def can_request_scopes(raw, scopes):
            return await context.get_bean(McpOAuthService).can_request_scopes(raw, scopes)

        server = create_mcp_server(
            app,
            mcp_settings,
            canonical_bearer,
            oauth_enabled=Config(values).get("koinon.mcp.oauth.enabled", False),
            can_request_scopes=can_request_scopes,
            private_review=private_review_reader(context)
            if Config(values).get("koinon.knowledge.enabled", True)
            else None,
            private_file_review=private_review_reader(context, file=True)
            if Config(values).get("koinon.knowledge.enabled", True)
            else None,
            read_capture=native_read_capture(context)
            if Config(values).get("koinon.knowledge.enabled", True)
            else None,
            prepare_file=file_upload_preparer(context)
            if Config(values).get("koinon.knowledge.enabled", True)
            else None,
        )
        mcp_app = server.streamable_http_app(
            stateless_http=False,
            json_response=True,
            max_sessions=mcp_settings.max_sessions,
            session_idle_timeout=mcp_settings.session_idle_timeout_seconds,
            max_request_body_size=mcp_settings.max_request_bytes,
            transport_security=mcp_settings.transport_security(),
        )
        app.router.routes.extend(mcp_app.routes)
        app.add_middleware(McpHttpBoundary, settings=mcp_settings)
        app.state.mcp_server = server
        install_oauth(app, context)
    app.state.context = context
    app.state.capability_registry = registry
    return app
