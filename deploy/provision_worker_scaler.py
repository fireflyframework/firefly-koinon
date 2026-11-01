# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Install the fixed counts-only function after migrations, never from runtime CI."""

import argparse
import os

import psycopg
from koinon.workers.scaler_installation import install
from koinon.workers.scaling import (
    ScalingLimits,
    render_demand_function,
    require_colocated_postgres,
)
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--reader", required=True)
    parser.add_argument("--document-lease-seconds", type=int, required=True)
    parser.add_argument("--document-max-attempts", type=int, required=True)
    parser.add_argument("--structured-lease-seconds", type=int, required=True)
    parser.add_argument("--structured-max-attempts", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    bindings = {
        name: os.environ[key]
        for name, key in (
            ("primary", "KOINON_DATABASE_URL"),
            ("canon", "KOINON_CANON_DATABASE_URL"),
            ("canon_admin", "KOINON_CANON_ADMIN_DATABASE_URL"),
            ("structured", "KOINON_STRUCTURED_DATABASE_URL"),
            ("structured_admin", "KOINON_STRUCTURED_ADMIN_DATABASE_URL"),
            ("operator", "KOINON_SCALER_OPERATOR_DATABASE_URL"),
        )
    }
    require_colocated_postgres(bindings)
    contract = render_demand_function(
        ScalingLimits(
            args.document_lease_seconds,
            args.document_max_attempts,
            args.structured_lease_seconds,
            args.structured_max_attempts,
        )
    )
    if not args.apply:
        print(contract.sql)
        return
    url = make_url(bindings["operator"])
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        install(connection, contract, owner=args.owner, reader=args.reader)
    print(
        f"Installed counts-only contract {contract.sha256}; {len(contract.queues)} queues"
    )


if __name__ == "__main__":
    main()
