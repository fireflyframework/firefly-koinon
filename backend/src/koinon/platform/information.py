# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Known installed metadata and validated limits; no environment or configuration dump."""

import importlib.metadata
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from koinon_storage.profile import LibraryIngestionProfile
from pyfly.container import component
from pyfly.core import Config

from koinon.communications.settings import CommunicationsSettings
from koinon.mcp.settings import McpSettings
from koinon.operations.settings import OperationalSettings
from koinon.platform.dtos import (
    SystemArtifact,
    SystemCapabilities,
    SystemComponentId,
    SystemComponentVersion,
    SystemDistribution,
    SystemInformation,
    SystemLimit,
    SystemLimitId,
)
from koinon.workers.admission import WorkAdmissionSettings

_COMPONENTS: tuple[tuple[SystemComponentId, SystemDistribution], ...] = (
    ("backend", "firefly-koinon"),
    ("documents", "firefly-koinon-documents"),
    ("structured", "firefly-koinon-structured"),
    ("storage", "firefly-koinon-storage"),
    ("python-sdk", "firefly-koinon-sdk"),
    ("framework", "pyfly"),
)
_MAX_ARTIFACT_BYTES = 65536


@component(name="platform.information")
class PlatformInformation:
    def __init__(
        self,
        config: Config,
        operations: OperationalSettings,
        work: WorkAdmissionSettings,
        mcp: McpSettings,
        communications: CommunicationsSettings,
    ):
        self.config, self.operations, self.work, self.mcp, self.communications = (
            config,
            operations,
            work,
            mcp,
            communications,
        )

    def artifact(
        self, distribution, component_id: SystemComponentId, kind: Literal["license", "notice", "sbom"]
    ) -> SystemArtifact:
        unknown = SystemArtifact(component=component_id, kind=kind)
        try:
            files = distribution.files
            if files is None or len(files) > 6000:
                return unknown
            names = {
                "license": {"LICENSE"},
                "notice": {"NOTICE"},
                "sbom": {"SBOM.spdx.json", "sbom.spdx.json", "sbom.json"},
            }[kind]
            candidates = []
            for value in files:
                path = Path(str(value))
                if path.is_absolute() or ".." in path.parts:
                    continue
                if (
                    path.name in names
                    and len(path.parts) in {2, 3}
                    and path.parts[0].endswith(".dist-info")
                    and (len(path.parts) == 2 or path.parts[1] == "licenses")
                ):
                    candidates.append(value)
            if not candidates:
                return (
                    unknown
                    if kind == "sbom"
                    else SystemArtifact(component=component_id, kind=kind, present=False)
                )
            if len(candidates) != 1:
                return unknown
            root = Path(str(distribution.locate_file("."))).resolve()
            path = Path(str(distribution.locate_file(candidates[0]))).resolve(strict=True)
            if (
                not path.is_relative_to(root)
                or not path.is_file()
                or path.stat().st_size > _MAX_ARTIFACT_BYTES
            ):
                return unknown
            with path.open("rb") as stream:
                data = stream.read(_MAX_ARTIFACT_BYTES + 1)
            if len(data) > _MAX_ARTIFACT_BYTES:
                return unknown
            return SystemArtifact(
                component=component_id,
                kind=kind,
                present=True,
                sha256=sha256(data).hexdigest(),
                content_type="application/json" if kind == "sbom" else "text/plain",
            )
        except (OSError, ValueError, TypeError):
            return unknown

    def read(self, tenant_id: str) -> SystemInformation:
        components, artifacts = [], []
        for identifier, name in _COMPONENTS:
            try:
                distribution = importlib.metadata.distribution(name)
                version = distribution.version
                version = version if re.fullmatch(r"[A-Za-z0-9.!+_-]{1,64}", version) else None
                components.append(
                    SystemComponentVersion(
                        id=identifier, distribution=name, version=version, available=version is not None
                    )
                )
                artifacts.extend(
                    self.artifact(distribution, identifier, kind) for kind in ("license", "notice", "sbom")
                )
            except (importlib.metadata.PackageNotFoundError, OSError, ValueError, TypeError):
                components.append(SystemComponentVersion(id=identifier, distribution=name, available=False))
                artifacts.extend(
                    SystemArtifact(component=identifier, kind=kind) for kind in ("license", "notice", "sbom")
                )
        role = self.config.get("koinon.process.role")
        values: list[
            tuple[
                SystemLimitId, int, Literal["operations", "bytes", "workspaces"], Literal["process", "file"]
            ]
        ] = [
            ("api_capacity", self.work.api_capacity, "operations", "process"),
            ("worker_capacity", self.work.worker_capacity, "operations", "process"),
            ("worker_concurrency", self.operations.worker_concurrency, "operations", "process"),
            ("max_index_workspaces", self.operations.max_index_workspaces, "workspaces", "process"),
            ("mcp_max_concurrency", self.mcp.max_concurrency, "operations", "process"),
            ("mcp_max_request_bytes", self.mcp.max_request_bytes, "bytes", "process"),
            ("mcp_max_response_bytes", self.mcp.max_response_bytes, "bytes", "process"),
        ]
        if self.config.get("koinon.knowledge.ingestion") is not None:
            profile = LibraryIngestionProfile.from_config(self.config)
            values.extend(
                [
                    ("ingestion_raw_max_bytes", profile.raw_max_bytes, "bytes", "file"),
                    ("ingestion_scratch_max_bytes", profile.scratch_max_bytes, "bytes", "process"),
                    ("ingestion_child_rss_max_bytes", profile.child_rss_max_bytes, "bytes", "process"),
                ]
            )
        return SystemInformation(
            tenant_id=tenant_id,
            checked_at=datetime.now(UTC),
            components=components,
            serving_role=role if role in {"api", "worker"} else "unknown",
            capabilities=SystemCapabilities(
                knowledge_enabled=self.config.get("koinon.knowledge.enabled", True) is True,
                mcp_enabled=self.mcp.enabled,
                communications_enabled=self.communications.enabled,
                scheduled_consumers_enabled=self.config.get("pyfly.scheduling.enabled", False) is True,
            ),
            limits=[
                SystemLimit(id=name, value=value, unit=unit, scope=scope)
                for name, value, unit, scope in values
            ],
            build_revision=None,
            artifacts=artifacts,
        )
