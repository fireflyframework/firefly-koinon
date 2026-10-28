# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_AVATAR_BYTES = 2_097_152
MAX_THUMBNAIL_BYTES = 65_536


def sanitize_avatar(content: bytes) -> bytes:
    if not content or len(content) > MAX_AVATAR_BYTES:
        raise ValueError("Avatar must contain at most 2 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Choose a nonanimated PNG, JPEG or WebP image")
                if source.width < 1 or source.height < 1 or max(source.size) > 4096:
                    raise ValueError("Avatar dimensions must not exceed 4096 pixels")
                source.draft("RGB", (128, 128))
                image = ImageOps.exif_transpose(source)
                image.thumbnail((128, 128), Image.Resampling.LANCZOS)
                rgba = image.convert("RGBA")
                sanitized = Image.new("RGB", rgba.size, "white")
                sanitized.paste(rgba, mask=rgba.getchannel("A"))
                output = BytesIO()
                sanitized.save(output, format="JPEG", quality=85, optimize=True)
                payload = output.getvalue()
                if len(payload) > MAX_THUMBNAIL_BYTES:
                    raise ValueError("Avatar thumbnail exceeds the supported size")
                return payload
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("Choose a valid bounded image") from error
