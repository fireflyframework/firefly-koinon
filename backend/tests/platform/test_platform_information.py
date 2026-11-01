# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

from pyfly.core import Config

from koinon.communications.settings import CommunicationsSettings
from koinon.mcp.settings import McpSettings
from koinon.operations.settings import OperationalSettings
from koinon.platform.information import PlatformInformation
from koinon.workers.admission import WorkAdmissionSettings


def reader(config=None):
    return PlatformInformation(
        Config(config or {}),
        OperationalSettings(),
        WorkAdmissionSettings(),
        McpSettings(),
        CommunicationsSettings(),
    )


def test_information_uses_only_known_installed_metadata_not_configuration_or_environment(monkeypatch):
    monkeypatch.setenv("BUILD_REVISION", "a" * 40)
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret@internal.example/private")
    result = reader(
        {"secret": "sentinel-key", "internal_url": "https://private.invalid", "build_revision": "b" * 40}
    ).read("north")
    wire = result.model_dump_json()
    assert result.build_revision is None and result.product == "koinon"
    assert len(result.components) == 6 and len(result.artifacts) <= 18
    assert "secret@internal" not in wire and "sentinel-key" not in wire and "private.invalid" not in wire
    assert "site-packages" not in wire and "localhost" not in wire
    assert all(value.sha256 for value in result.artifacts if value.present is True)
    assert all(value.present is None for value in result.artifacts if value.kind == "sbom")


def test_artifact_reader_rejects_large_files_and_paths_outside_installed_distribution(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    outside = tmp_path / "private-key"
    outside.write_text("must not read")
    dist = SimpleNamespace(
        locate_file=lambda name: root if str(name) == "." else root / str(name),
        files=["package.dist-info/licenses/LICENSE"],
    )
    licenses = root / "package.dist-info/licenses"
    licenses.mkdir(parents=True)
    (licenses / "LICENSE").symlink_to(outside)
    item = reader().artifact(dist, "backend", "license")
    assert item.present is None and item.sha256 is None
    (licenses / "LICENSE").unlink()
    (licenses / "LICENSE").write_bytes(b"x" * 65537)
    assert reader().artifact(dist, "backend", "license").present is None
