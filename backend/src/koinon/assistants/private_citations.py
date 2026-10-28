# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Hide canonical private citation labels without changing file contents or typed refs."""

from collections.abc import Sequence

from koinon.knowledge.attachments.ports import AttachmentRef


class PrivateCitationLabels:
    def __init__(self, refs: Sequence[AttachmentRef]):
        self.labels = {f"Attachment {ref.id}: {ref.filename}": ref.filename for ref in refs}
        self.pending = ""

    def feed(self, value: str) -> str:
        text = self.pending + value
        for label, filename in self.labels.items():
            text = text.replace(label, filename)
        retained = 0
        for label in self.labels:
            for size in range(min(len(text), len(label) - 1), retained, -1):
                if text.endswith(label[:size]):
                    retained = size
                    break
        self.pending = text[-retained:] if retained else ""
        return text[:-retained] if retained else text

    def finish(self) -> str:
        text, self.pending = self.pending, ""
        return text
