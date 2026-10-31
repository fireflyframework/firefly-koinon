# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import os

from koinon_sdk import KoinonClient


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this example")
    return value


def connect() -> KoinonClient:
    return KoinonClient(
        required("KOINON_API_URL"),
        token_provider=lambda: required("KOINON_TOKEN"),
    )
