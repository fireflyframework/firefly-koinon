# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from pyfly.container import component
from pyfly.core import config_properties


@component(name="corporate_profiles.settings")
@config_properties(prefix="koinon.identity.profile_sync")
@dataclass
class CorporateProfileSettings:
    worker_enabled: bool = True
    photo_origins: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        if (
            type(self.worker_enabled) is not bool
            or not isinstance(self.photo_origins, dict)
            or len(self.photo_origins) > 20
        ):
            raise ValueError("Use a bounded corporate photo origin policy")
        for origin, paths in self.photo_origins.items():
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or origin != f"https://{parsed.netloc}"
                or not isinstance(paths, list)
                or not 1 <= len(paths) <= 20
            ):
                raise ValueError("Use exact HTTPS photo origins and bounded path prefixes")
            _ = parsed.port
            for path in paths:
                if (
                    not isinstance(path, str)
                    or not path.startswith("/")
                    or not path.endswith("/")
                    or len(path) > 512
                    or "\\" in path
                    or any(part in {".", ".."} for part in unquote(path).split("/"))
                ):
                    raise ValueError("Use absolute corporate photo path prefixes")

    def photo_url(self, value):
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 2048
            or "\\" in value
            or any(ord(char) < 33 or ord(char) == 127 for char in value)
        ):
            return False
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            return False
        try:
            _ = parsed.port
        except ValueError:
            return False
        decoded = unquote(parsed.path)
        if (
            "\\" in decoded
            or any(ord(char) < 33 or ord(char) == 127 for char in decoded)
            or any(part in {".", ".."} for part in decoded.split("/"))
            or unquote(decoded) != decoded
        ):
            return False
        return any(
            decoded.startswith(prefix) for prefix in self.photo_origins.get(f"https://{parsed.netloc}", [])
        )
