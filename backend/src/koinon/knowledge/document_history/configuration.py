# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from flycanon.core.services.sources.lineage.service import DocumentLineage
from pyfly.container import Container, bean, configuration

from koinon.knowledge.beans import native_bean
from koinon.knowledge.document_history.native import NativeDocumentHistory
from koinon.knowledge.document_history.ports import DocumentHistoryPort
from koinon.knowledge.document_history.resources import DocumentHistoryResources


@configuration
class DocumentHistoryConfiguration:
    @bean
    def document_history_resources(self, container: Container) -> DocumentHistoryResources:
        return DocumentHistoryResources(lambda: native_bean(container, DocumentLineage))

    @bean
    def document_history_port(self, history: NativeDocumentHistory) -> DocumentHistoryPort:
        return history
