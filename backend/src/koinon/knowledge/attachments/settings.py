# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="knowledge.attachments.settings")
@config_properties(prefix="koinon.attachments")
@dataclass
class AttachmentSettings:
    storage_root: str | None = None
    max_file_bytes: int = 20 * 1024 * 1024
    max_image_bytes: int = 8 * 1024 * 1024
    max_thread_bytes: int = 128 * 1024 * 1024
    max_thread_files: int = 100
    max_selected: int = 10
    ttl_seconds: int = 86400
    extraction_timeout_seconds: int = 60
    max_expanded_bytes: int = 32 * 1024 * 1024
    max_artifacts: int = 8
    max_pages: int = 200
    max_text_bytes: int = 2 * 1024 * 1024
    max_chunks: int = 2048
    max_image_pixels: int = 40000000
    worker_enabled: bool = False

    def validate(self):
        limits = (
            (self.max_file_bytes, 1, 64 * 1024 * 1024),
            (self.max_image_bytes, 1, 16 * 1024 * 1024),
            (self.max_thread_bytes, 1, 1024 * 1024 * 1024),
            (self.max_thread_files, 1, 1000),
            (self.max_selected, 1, 10),
            (self.ttl_seconds, 3600, 604800),
            (self.extraction_timeout_seconds, 1, 60),
            (self.max_expanded_bytes, 1, 64 * 1024 * 1024),
            (self.max_artifacts, 1, 16),
            (self.max_pages, 1, 200),
            (self.max_text_bytes, 1, 2 * 1024 * 1024),
            (self.max_chunks, 1, 2048),
            (self.max_image_pixels, 1, 40000000),
        )
        if any(
            type(value) is not int or not minimum <= value <= maximum for value, minimum, maximum in limits
        ):
            raise ValueError("Private attachment configuration exceeds a supported resource bound")
