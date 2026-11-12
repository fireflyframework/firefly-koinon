# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source authority wraps canonical writes before their transaction begins."""

from functools import wraps
from inspect import signature


def source_mutation(method):
    parameters = signature(method)

    @wraps(method)
    async def protected(self, *args, **kwargs):
        permit = kwargs.pop("_source_write", None)
        parent_hint = kwargs.pop("_source_parent_id", None)
        bound = parameters.bind(self, *args, **kwargs)
        bound.apply_defaults()
        arguments = bound.arguments
        catalog = getattr(self, "catalog", self)
        if permit is not None:
            from koinon.integrations.content_sources.source_publication import consume_write, invalidate_write

            action = method.__name__.removeprefix("_")
            target = arguments.get("entry_id")
            parent = parent_hint
            if action == "create":
                target = arguments.get("_source_create_id")
                parent = arguments.get("parent_id")
                changes = {key: arguments[key] for key in ("kind", "name", "description")}
                changes["metadata"] = arguments.get("metadata") or {}
            elif action == "merge_latest":
                changes = {"latest_content_version_id": arguments["version_id"]}
            elif action == "move":
                changes = {"parent_id": arguments["parent_id"]}
            else:
                changes = arguments.get("changes", {})
            operation = consume_write(
                permit,
                catalog.catalog_repository._require_session(),
                actor=arguments["subject"],
                tenant=arguments["tenant_id"],
                action=action,
                target=target,
                parent=parent,
                changes=changes,
            )
            if "_source_write" in parameters.parameters:
                kwargs["_source_write"] = permit
            if "_source_expected_revision" in parameters.parameters:
                kwargs["_source_expected_revision"] = operation.expected_revision
            try:
                return await method(self, *args, **kwargs)
            except BaseException:
                invalidate_write(permit, catalog.catalog_repository._require_session())
                raise
        if (
            arguments.get("_source_create_id") is not None
            or parent_hint is not None
            or arguments.get("_source_expected_revision") is not None
            or method.__name__ == "_merge_latest"
        ):
            from pyfly.kernel import ConflictException

            raise ConflictException(
                "Source publication authority is required", code="SOURCE_PUBLICATION_DENIED"
            )
        policy = catalog.source_policy.get() if catalog.source_policy is not None else None
        if policy is None:
            return await method(self, *args, **kwargs)
        target = arguments.get("entry_id")
        identifiers = tuple(dict.fromkeys(value for value in (target, arguments.get("parent_id")) if value))
        async with policy.mutation(
            arguments["subject"], arguments["tenant_id"], identifiers, action=method.__name__, target=target
        ):
            return await method(self, *args, **kwargs)

    return protected
