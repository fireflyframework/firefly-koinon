# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import binascii
import re
import warnings
from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 262144
MAX_IMAGE_DIMENSION = 2048
MAX_DATA_URL_LENGTH = 349550
_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}


def image_data_url(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_DATA_URL_LENGTH:
        raise ValueError("Brand images must contain at most 256 KiB")
    prefix, separator, encoded = value.partition(",")
    media = prefix.removeprefix("data:").removesuffix(";base64")
    if (not separator or prefix != f"data:{media};base64" or media not in _FORMATS
            or not encoded or len(encoded) % 4 or re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", encoded) is None):
        raise ValueError("Choose a PNG, JPEG or WebP data URL")
    return value


def sanitize_image(value: str | None) -> str | None:
    value = image_data_url(value)
    if value is None:
        return None
    prefix, encoded = value.split(",", 1)
    media = prefix.removeprefix("data:").removesuffix(";base64")
    try:
        content = base64.b64decode(encoded, validate=True)
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise ValueError("Brand images must contain at most 256 KiB")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format != _FORMATS[media] or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Choose a nonanimated image matching its data URL format")
                if min(source.size) < 1 or max(source.size) > MAX_IMAGE_DIMENSION:
                    raise ValueError("Brand image dimensions must not exceed 2048 pixels")
                rgba = source.convert("RGBA")
                sanitized = Image.new("RGBA", rgba.size)
                sanitized.paste(rgba)
                output = BytesIO()
                sanitized.save(output, format="PNG")
                payload = output.getvalue()
                if len(payload) > MAX_IMAGE_BYTES:
                    raise ValueError("Sanitized brand image exceeds 256 KiB")
                return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    except (
        binascii.Error,
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("Choose a valid bounded raster image") from error
