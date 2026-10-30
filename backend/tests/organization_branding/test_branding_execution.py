# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import threading
from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import AsyncMock

from pyfly.core import Config

from koinon.organization_branding.controllers import (
    BrandingDefaultsController,
    OrganizationBrandingController,
)
from koinon.organization_branding.dtos import BrandingValues, OrganizationBranding, encode_branding
from koinon.organization_branding.service import OrganizationBrandingService


def test_branding_controller_responses_have_concrete_wire_types():
    assert get_type_hints(BrandingDefaultsController.defaults)["return"] is BrandingValues
    for name in ("get", "update", "reset"):
        assert get_type_hints(getattr(OrganizationBrandingController, name))["return"] is OrganizationBranding


def test_actual_request_json_converter_does_not_decode_raster_images(monkeypatch):
    import base64
    import json
    from io import BytesIO

    from PIL import Image
    from pyfly.web.message_converters import JsonMessageConverter

    from koinon.organization_branding.dtos import OrganizationBrandingInput

    output = BytesIO()
    Image.new("RGB", (16, 16), "white").save(output, format="PNG")
    values = BrandingValues().model_dump(mode="json")
    values["logo_light"] = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()

    def forbidden(value):
        raise AssertionError("Native body binding must not decode raster images")

    monkeypatch.setattr("koinon.organization_branding.dtos.sanitize_image", forbidden)
    parsed = JsonMessageConverter().read(json.dumps({
        "expected_revision": 0, "branding": values,
    }).encode(), OrganizationBrandingInput)
    assert parsed.branding.logo_light == values["logo_light"]


async def test_persisted_validation_runs_off_loop_with_at_most_two_workers(monkeypatch):
    service = OrganizationBrandingService(None, None, Config({}))
    row = SimpleNamespace(revision=3, branding_json=encode_branding(BrandingValues()))
    lock = threading.Lock()
    observed = {"active": 0, "maximum": 0, "threads": set()}
    original = BrandingValues.model_validate_json
    loop_thread = threading.get_ident()

    def decode(*args, **kwargs):
        import time

        with lock:
            observed["active"] += 1
            observed["maximum"] = max(observed["maximum"], observed["active"])
            observed["threads"].add(threading.get_ident())
        try:
            time.sleep(0.01)
            return original(*args, **kwargs)
        finally:
            with lock:
                observed["active"] -= 1

    monkeypatch.setattr(BrandingValues, "model_validate_json", decode)
    service._authorize_read = AsyncMock()
    service.settings = SimpleNamespace(current=AsyncMock(return_value=row))
    get = OrganizationBrandingService.get.__wrapped__
    values = await asyncio.gather(*(get(service, "owner", "north") for _ in range(8)))
    assert len(values) == 8 and all(value.revision == 3 for value in values)
    assert loop_thread not in observed["threads"]
    assert observed["maximum"] <= 2
    assert service._authorize_read.await_count == 8


async def test_cancelled_requests_keep_validation_slots_until_the_worker_finishes(monkeypatch):
    service = OrganizationBrandingService(None, None, Config({}))
    row = SimpleNamespace(revision=1, branding_json=encode_branding(BrandingValues()))
    release = threading.Event()
    lock = threading.Lock()
    observed = {"active": 0, "maximum": 0}
    original = service._decode

    def decode(*args):
        with lock:
            observed["active"] += 1
            observed["maximum"] = max(observed["maximum"], observed["active"])
        try:
            assert release.wait(timeout=2)
            return original(*args)
        finally:
            with lock:
                observed["active"] -= 1

    monkeypatch.setattr(service, "_decode", decode)
    tasks = [asyncio.create_task(service._view("north", row)) for _ in range(2)]
    try:
        async with asyncio.timeout(1):
            while observed["active"] < 2:
                await asyncio.sleep(0.001)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        tasks.extend(asyncio.create_task(service._view("north", row)) for _ in range(4))
        await asyncio.sleep(0.03)
        assert observed["maximum"] <= 2
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
