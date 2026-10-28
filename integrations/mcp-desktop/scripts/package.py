# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

"""Create reproducible MCPB and portable skill archives from the verified build."""
from hashlib import sha256
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
VERSION = json.loads((ROOT / "manifest.json").read_text())["version"]
DIST.mkdir(exist_ok=True)


def archive(destination: Path, files: list[tuple[Path, str]]) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path, name in sorted(files, key=lambda item: item[1]):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


extension = DIST / f"firefly-koinon-desktop-{VERSION}.mcpb"
skills = DIST / f"firefly-koinon-skills-{VERSION}.zip"
archive(extension, [(path, path.relative_to(BUILD).as_posix()) for path in BUILD.rglob("*") if path.is_file()])
archive(skills, [(path, path.relative_to(BUILD / "skills").as_posix()) for path in (BUILD / "skills").rglob("*") if path.is_file()] + [(BUILD / "LICENSE", "LICENSE"), (BUILD / "NOTICE", "NOTICE")])
(DIST / "SHA256SUMS").write_text("".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in [extension, skills]))
print(f"Created {extension.name}, {skills.name}, and SHA256SUMS")
