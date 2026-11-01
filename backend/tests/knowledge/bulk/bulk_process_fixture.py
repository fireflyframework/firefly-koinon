# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent native application process for an explicitly owned SQL fixture."""

import asyncio
import json
import os
import sys
from pathlib import Path


def context_for(url, root, cloud=None):
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "none", "url": url}},
                },
                "koinon": {"knowledge": {"bulk": {"storage_root": root, **(cloud or {})}}},
            }
        )
    )
    for package in ("koinon.catalog", "koinon.jobs", "koinon.storage", "koinon.knowledge.bulk"):
        scan_package(package, context.container)
    from koinon.assistants.repositories import ProviderRepository
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.repositories import PersonalTokenRepository

    for bean in (
        PersonalTokenRepository,
        TokenRestriction,
        ProviderRepository,
        KnowledgeConnectionRepository,
        DomainBindingRepository,
    ):
        context.register_bean(bean)
    return context


async def main(path):
    from bulk_fixture_network import restrict_owned_sockets

    values = json.loads(Path(path).read_text())
    restrict_owned_sockets(values["url"], values.get("cloud", {}).get("azure_account_url"))
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkAction
    from koinon.knowledge.bulk.service import FileBatches, UploadTicket

    context = context_for(values["url"], values["root"], values.get("cloud"))
    await context.start()
    try:
        service = context.get_bean(FileBatches)
        if values.get("emulator_connection"):
            service.storage.configured().native.connection_string = values["emulator_connection"]
        try:
            if values["operation"] == "read-original":
                result = await service.receipt("issuer|editor", "north", values["batch"], values["item"])
                output = {"code": "ok", "receipt": result.receipt_id, "sha256": result.sha256}
            elif values["operation"] == "finish":
                result = await service._finish_upload(
                    "issuer|editor",
                    "north",
                    values["batch"],
                    values["item"],
                    UploadTicket(**values["ticket"]),
                )
                output = {"code": "ok", "receipt": result.receipt_id}
            elif values["operation"] == "claim-and-crash":
                await service._recovery_ticket(
                    "issuer|editor",
                    "north",
                    values["batch"],
                    values["item"],
                    BulkAction(expected_revision=values["revision"]),
                    values["key"],
                )
                print(json.dumps({"code": "crashed-after-committed-fence"}), flush=True)
                os._exit(17)
            else:
                result = await service.recover_original(
                    "issuer|editor",
                    "north",
                    values["batch"],
                    values["item"],
                    BulkAction(expected_revision=values["revision"]),
                    values["key"],
                )
                output = {"code": "ok", "revision": result.revision}
        except ConflictException as error:
            output = {"code": error.code}
        print(json.dumps(output))
    finally:
        await context.stop()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
