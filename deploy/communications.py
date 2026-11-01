# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Manage approved recipient observations and queue a new, idempotent delivery diagnostic."""

import argparse
import asyncio
import json
import os
import stat
from pathlib import Path
from uuid import UUID


def load_contacts(path: Path):
    from koinon.communications.contact_dtos import OperatorContactInput
    from pydantic import TypeAdapter

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        observed = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_mode & 0o077
            or observed.st_uid != os.getuid()
            or observed.st_size > 262144
        ):
            raise ValueError(
                "Use an owner-only regular contact file of at most 256 KiB"
            )
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("Use an owner-only regular contact file of at most 256 KiB")
    try:
        values = TypeAdapter(list[OperatorContactInput]).validate_json(raw)
    except ValueError:
        raise ValueError("The protected operator contact file is invalid") from None
    if not 1 <= len(values) <= 100:
        raise ValueError("Supply one to one hundred approved recipient observations")
    keys = {(value.tenant_id, value.identity.model_dump_json()) for value in values}
    if len(keys) != len(values):
        raise ValueError("Choose each immutable contact identity once")
    return values


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision")
    provision.add_argument("--contacts-file", type=Path, required=True)
    renew = commands.add_parser("renew")
    renew.add_argument("--contacts-file", type=Path, required=True)
    for name in ("renew", "revoke", "status", "diagnostic"):
        command = renew if name == "renew" else commands.add_parser(name)
        command.add_argument("--contact-id", type=UUID, required=True)
        if name in {"renew", "revoke"}:
            command.add_argument("--expected-revision", type=int, required=True)
        if name == "diagnostic":
            command.add_argument("--operation-id", type=UUID, required=True)
    return parser.parse_args(argv)


async def execute(context, args, values=()):
    from koinon.communications.operator_contacts import OperatorContacts
    from pyfly.data.transaction import TransactionTemplate
    from pyfly.data.transaction.registry import (
        TransactionManagerRegistry,
        bind_registry,
    )

    registry = context.get_bean(TransactionManagerRegistry)
    with bind_registry(registry):
        service = context.get_bean(OperatorContacts)
        if args.command == "provision":
            result = []
            async with TransactionTemplate(registry.get("primary")).transaction():
                for value in values:
                    row = await service.provision(value)
                    result.append({"contact_id": row.id, "revision": row.revision})
            return {"status": "provisioned", "contacts": result}
        identifier = str(args.contact_id)
        if args.command == "renew":
            if len(values) != 1:
                raise ValueError("Renew exactly one contact observation")
            row = await service.renew(identifier, args.expected_revision, values[0])
            return {"status": "renewed", "contact_id": row.id, "revision": row.revision}
        if args.command == "revoke":
            row = await service.revoke(identifier, args.expected_revision)
            return {"status": "revoked", "contact_id": row.id, "revision": row.revision}
        if args.command == "diagnostic":
            return await service.diagnostic(identifier, str(args.operation_id))
        return await service.status(identifier)


async def main(argv=None):
    args = arguments(argv)
    values = (
        load_contacts(args.contacts_file)
        if args.command in {"provision", "renew"}
        else ()
    )
    from koinon.app import create_application
    from koinon.operations.configuration import environment_configuration

    app = create_application(environment_configuration(), role="api")
    context = app.state.context
    await context.start()
    try:
        print(json.dumps(await execute(context, args, values)))
    finally:
        await context.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:  # noqa: BLE001 -- credentials and recipient values are not operator output
        print(
            "Communications operation failed:",
            getattr(error, "code", "CONTACT_CONFIGURATION_INVALID"),
        )
        raise SystemExit(2) from None
