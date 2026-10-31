# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import io
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from koinon.mcp.private_reviews import presentation
from koinon.organization_branding.dtos import BrandingValues


def raster(size):
    image = Image.frombytes("RGB", (size, size), random.Random(0).randbytes(size * size * 3))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


@pytest.mark.parametrize("size", [None, 4, 192])
async def test_private_presentation_projects_only_small_validated_symbol_without_copying_logos(size):
    symbol = raster(size) if size else None
    branding = BrandingValues(
        product_name="Organization knowledge",
        assistant_name="Navigator",
        font_family="Inter",
        symbol=symbol,
        logo_light=raster(4),
        logo_dark=raster(4),
    )
    get = AsyncMock(return_value=SimpleNamespace(branding=branding))
    context = SimpleNamespace(get_bean=lambda kind: SimpleNamespace(get=get))
    result = await presentation(context, "issuer|owner", "north")
    get.assert_awaited_once_with("issuer|owner", "north")
    assert result["product_name"] == "Organization knowledge" and result["assistant_name"] == "Navigator"
    assert result["font_family"] == "Inter"
    assert "logo_light" not in result and "logo_dark" not in result and "favicon" not in result
    if size == 4:
        assert result["symbol"] == branding.symbol and len(result["symbol"]) <= 65536
    else:
        assert "symbol" not in result
