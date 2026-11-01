# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Queue operator-verified initial-administrator welcome after the public origin is live."""

import argparse
import asyncio
import os
import stat
from pathlib import Path


def load_contacts(path: Path):
    from koinon.bootstrap.dtos import BootstrapContactInput
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
        values = TypeAdapter(list[BootstrapContactInput]).validate_json(raw)
    except ValueError:
        raise ValueError("The protected bootstrap contact file is invalid") from None
    if not 1 <= len(values) <= 100:
        raise ValueError("Supply one to one hundred exact pending bootstrap contacts")
    keys = {
        (
            value.tenant_id,
            value.issuer,
            value.client_id,
            value.entra_tenant_id,
            value.object_id,
        )
        for value in values
    }
    if len(keys) != len(values):
        raise ValueError("Choose each exact pending bootstrap grant once")
    return values


async def admit_contacts(context, values):
    from koinon.communications.bootstrap_contacts import BootstrapContacts
    from pyfly.data.transaction import TransactionTemplate

    service = context.get_bean(BootstrapContacts)
    async with TransactionTemplate("primary").transaction():
        for value in values:
            await service.admit(value)
    return len(values)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contacts-file", type=Path, required=True)
    arguments = parser.parse_args()
    values = load_contacts(arguments.contacts_file)
    from koinon.main import app

    context = app.state.context
    await context.start()
    try:
        count = await admit_contacts(context, values)
        print("Bootstrap contact admissions recorded:", count)
    finally:
        await context.stop()


if __name__ == "__main__":
    asyncio.run(main())
