# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Project retained controller metadata without changing constituent classes."""

import importlib
import importlib.util
import inspect
import pkgutil
from types import FunctionType
from typing import Any

from pyfly.container.scanner import scan_module_classes
from pyfly.context import ApplicationContext

from koinon.web.legacy_security import trusted_legacy_context


def _projected(cls: type, name: str, path: str) -> type:
    methods: dict[str, Any] = {
        "__module__": cls.__module__,
        "__pyfly_request_mapping__": path,
        "__pyfly_bean_name__": name,
    }
    if name.startswith(("canon.", "structured.", "bff.canon.", "bff.structured.")):
        for attr in dir(cls):
            original = getattr(cls, attr, None)
            if (
                not isinstance(original, FunctionType)
                or "tenant_context_from_request" not in original.__globals__
            ):
                continue
            globals_copy = {**original.__globals__, "tenant_context_from_request": trusted_legacy_context}
            clone = FunctionType(
                original.__code__,
                globals_copy,
                original.__name__,
                original.__defaults__,
                original.__closure__,
            )
            clone.__kwdefaults__ = original.__kwdefaults__
            clone.__annotations__ = original.__annotations__.copy()
            clone.__dict__.update(original.__dict__)
            methods[attr] = clone
    return type(name, (cls,), methods)


def register_controller(context: ApplicationContext, cls: type, domain: str | None = None) -> list[type]:
    base = getattr(cls, "__pyfly_request_mapping__", "")
    if domain:
        if base != "/api/v1" and not base.startswith("/api/v1/"):
            raise ValueError(f"Unsupported retained controller prefix: {base}")
        base = f"/api/v1/{domain}" + base[len("/api/v1") :]
        public = _projected(cls, f"{domain}.{cls.__name__}", base)
    else:
        public = cls
    context.register_bean(public)
    if domain:
        context.container.bind(cls, public)
    browser = _projected(cls, f"bff.{domain or 'common'}.{cls.__name__}", "/bff" + base)
    context.register_bean(browser)
    return [public, browser]


def _configuration(cls: type, domain: str) -> type:
    methods: dict[str, Any] = {
        "__module__": cls.__module__,
        "__pyfly_bean_name__": f"{domain}.{cls.__name__}",
    }
    for name in dir(cls):
        function = getattr(cls, name, None)
        if not isinstance(function, FunctionType) or not getattr(function, "__pyfly_bean__", False):
            continue
        clone = FunctionType(
            function.__code__,
            function.__globals__,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        clone.__kwdefaults__ = function.__kwdefaults__
        clone.__annotations__ = function.__annotations__.copy()
        clone.__dict__.update(function.__dict__)
        bean_name = getattr(function, "__pyfly_bean_name__", name)
        clone.__dict__["__pyfly_bean_name__"] = (
            bean_name if bean_name.startswith(domain + ".") else f"{domain}.{bean_name}"
        )
        methods[name] = clone
    return type(f"{domain}.{cls.__name__}", (cls,), methods)


def register_optional_domain(context: ApplicationContext, package: str, domain: str) -> dict:
    if importlib.util.find_spec(package) is None:
        return {"installed": False, "registered": False, "reason": "Optional package is not installed"}
    classes = set()
    for package_name in (f"{package}.core", f"{package}.web.controllers"):
        module = importlib.import_module(package_name)
        modules = [module]
        if hasattr(module, "__path__"):
            modules.extend(
                importlib.import_module(info.name)
                for info in pkgutil.walk_packages(module.__path__, prefix=package_name + ".")
                if not info.name.startswith(f"{package}.core.services.storage.adapters.")
            )
        for current in modules:
            classes.update(scan_module_classes(current))
    for cls in sorted(classes, key=lambda item: (item.__module__, item.__qualname__)):
        stereotype = getattr(cls, "__pyfly_stereotype__", "")
        if stereotype in ("controller", "rest_controller"):
            register_controller(context, cls, domain)
        else:
            registered = _configuration(cls, domain) if stereotype == "configuration" else cls
            context.register_bean(registered, name=f"{domain}.{cls.__module__}.{cls.__name__}")
            for base in inspect.getmro(registered)[1:]:
                if (
                    getattr(base, "_is_protocol", False)
                    or inspect.isabstract(base)
                    or ".ports" in base.__module__
                ):
                    context.container.bind(base, registered)
    return {"installed": True, "registered": True, "beans": len(classes)}
