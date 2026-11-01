# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provision a reviewed initial knowledge plan with an operator-only database identity."""

import argparse
import asyncio
import json
import os
from pathlib import Path


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate bounded source inputs without starting an application or making network requests",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Explicitly reconcile a partial attempt of the exact same installation plan",
    )
    return parser.parse_args(argv)


async def provision(context, plan, credentials, *, resume=False):
    from koinon.installation.service import InstallationProvisioner

    return await context.get_bean(InstallationProvisioner).apply(
        plan, credentials, resume=resume
    )


async def main(argv=None):
    from koinon.installation.plan_file import load_plan, resolve_secrets

    args = arguments(argv)
    plan = load_plan(args.manifest)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "source_valid",
                    "plan_key": plan.plan_key,
                    "plan_sha256": plan.fingerprint(),
                    "providers": len(plan.providers),
                    "catalog_entries": len(plan.catalog),
                    "indexes": len(plan.indexes),
                }
            )
        )
        return
    credentials = resolve_secrets(plan, os.environ)
    from koinon.main import app
    from koinon.web.projection import register_product_package

    context = app.state.context
    register_product_package(context, "koinon.installation", controllers=False)
    await context.start()
    try:
        result = await provision(context, plan, credentials, resume=args.resume)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "run_id": result["run_id"],
                    "plan_sha256": result["plan_sha256"],
                    "committed_checkpoints": len(result["checkpoints"]),
                }
            )
        )
    finally:
        await context.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:  # noqa: BLE001 - provider exceptions may contain credentials
        # Provider bodies, credentials and database URLs are not operator output.
        print(
            "Installation failed:",
            getattr(error, "code", "INSTALLATION_CONFIGURATION_INVALID"),
        )
        raise SystemExit(2) from None
