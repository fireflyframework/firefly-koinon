#!/usr/bin/env python3
# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Koinon asset assembly from an exact clean Git commit; never publishes."""

from __future__ import annotations

import argparse
import base64
import csv
import email
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import tarfile
import time
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

WHEELS = {
    "backend": ("firefly-koinon", "koinon"),
    "packages/canon": ("firefly-koinon-documents", "flycanon"),
    "packages/structured": ("firefly-koinon-structured", "flyquery"),
    "packages/storage": ("firefly-koinon-storage", "koinon_storage"),
    "sdk/python": ("firefly-koinon-sdk", "koinon_sdk"),
}
JSON_VERSIONS = (
    "sdk/typescript/package.json",
    "frontend/package.json",
    "frontend/projects/koinon-angular/package.json",
    "integrations/mcp-desktop/package.json",
    "integrations/mcp-desktop/manifest.json",
)
NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def require(value: object, message: object) -> None:
    if not value:
        raise RuntimeError(str(message))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(path: Path) -> dict:
    return {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}


def retain_uv_marker(assets: Path, evidence: Path) -> None:
    marker = assets / ".gitignore"
    if marker.exists():
        require(
            marker.read_bytes() in (b"*", b"*\n"),
            "Unexpected hidden file from build backend",
        )
        marker.rename(evidence / "uv-output.gitignore.txt")


def safe_name(name: str) -> None:
    parts = PurePosixPath(name).parts
    require(
        name and not name.startswith(("/", "\\")) and "\\" not in name,
        f"Unsafe archive member: {name!r}",
    )
    require(
        ".." not in parts and not re.match(r"^[A-Za-z]:", name),
        f"Unsafe archive member: {name!r}",
    )
    require(
        not any(p in {"node_modules", ".git", ".venv", "__pycache__"} for p in parts),
        f"Dependency/private directory in archive: {name}",
    )
    require(
        not any(
            p in {".npmrc", ".pypirc", "connection.private.json"}
            or (
                p.startswith(".env")
                and not any(x in p for x in ("example", "sample", "template"))
            )
            for p in parts
        ),
        f"Private configuration in archive: {name}",
    )


def members(path: Path) -> dict[str, bytes]:
    result = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            seen = set()
            for entry in archive.infolist():
                safe_name(entry.filename)
                require(
                    entry.filename not in seen, f"Duplicate ZIP member {entry.filename}"
                )
                seen.add(entry.filename)
                require(
                    (entry.external_attr >> 16) & 0o170000 != 0o120000,
                    f"ZIP symlink {entry.filename}",
                )
                if not entry.is_dir():
                    result[entry.filename] = archive.read(entry)
    else:
        with tarfile.open(path) as archive:
            seen = set()
            for entry in archive:
                safe_name(entry.name)
                require(entry.name not in seen, f"Duplicate TAR member {entry.name}")
                seen.add(entry.name)
                require(
                    entry.isfile() or entry.isdir(),
                    f"Non-regular TAR member {entry.name}",
                )
                if entry.isfile():
                    stream = archive.extractfile(entry)
                    require(stream, f"Missing TAR data {entry.name}")
                    result[entry.name] = stream.read()
    require(result, f"Empty archive {path}")
    return result


def clean_commit(checkout: Path, commit: str) -> str:
    require(
        re.fullmatch(r"[0-9a-f]{40}", commit),
        "Use the full exact 40-character source commit",
    )

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(checkout), *args], text=True
        ).strip()

    require(
        git("rev-parse", "HEAD") == commit,
        "Checkout HEAD differs from requested commit",
    )
    require(
        not git("status", "--porcelain", "--untracked-files=all"),
        "Source checkout must be clean",
    )
    require(
        not git("ls-files", "--stage").startswith("160000 "), "Submodules unsupported"
    )
    modes = git("ls-tree", "-r", commit).splitlines()
    require(
        not any(x.startswith(("120000 ", "160000 ")) for x in modes),
        "Source symlinks/submodules require explicit review",
    )
    return git("rev-parse", f"{commit}^{{tree}}")


def verify_versions(source: Path, version: str) -> dict:
    require(
        re.fullmatch(r"\d{2}\.\d{1,2}\.\d+", version),
        "Final CalVer required; prereleases rejected",
    )
    result = {}
    for directory, (name, _) in WHEELS.items():
        path = f"{directory}/pyproject.toml"
        project = tomllib.loads((source / path).read_text())["project"]
        require(project["name"] == name and project["version"] == version, path)
        result[path] = project["version"]
        for dependency in project.get("dependencies", []):
            if "koinon" in dependency.lower():
                require(
                    "alpha" not in dependency.lower(),
                    f"Active alpha requirement: {dependency}",
                )
    for path in JSON_VERSIONS:
        data = json.loads((source / path).read_text())
        require(data["version"] == version, path)
        for section in ("dependencies", "peerDependencies", "devDependencies"):
            for name, spec in data.get(section, {}).items():
                if "koinon" in name:
                    require(
                        "alpha" not in spec.lower(),
                        f"Active alpha requirement: {path}:{name}",
                    )
        result[path] = data["version"]
    pom = ET.parse(source / "sdk/java/pom.xml").getroot()
    require(pom.findtext("m:version", namespaces=NS) == version, "Java SDK version")
    require(
        pom.findtext("m:properties/m:maven.compiler.release", namespaces=NS) == "21",
        "Java21 required",
    )
    result["sdk/java/pom.xml"] = version
    return result


def tar_directory(
    directory: Path, destination: Path, epoch: int, extra: dict[str, Path]
) -> None:
    files = {
        p.relative_to(directory).as_posix(): p
        for p in directory.rglob("*")
        if p.is_file()
    }
    for name, path in extra.items():
        require(
            name not in files or files[name].read_bytes() == path.read_bytes(),
            f"Legal collision {name}",
        )
        files[name] = path
    with (
        destination.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=epoch, filename="") as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for name, path in sorted(files.items()):
            safe_name(name)
            require(not path.is_symlink(), f"Symlink in bundle {path}")
            data = path.read_bytes()
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = len(data), 0o644, epoch
            archive.addfile(entry, io.BytesIO(data))


def verify_wheel(path: Path, source: Path, directory: str, version: str) -> dict:
    payload = members(path)
    name, namespace = WHEELS[directory]
    metadata = email.message_from_bytes(
        next(
            data for key, data in payload.items() if key.endswith(".dist-info/METADATA")
        )
    )
    require(
        metadata["Name"] == name and metadata["Version"] == version,
        f"Wheel metadata: {path.name}",
    )
    expected = {
        p.relative_to(source / directory / "src").as_posix(): p.read_bytes()
        for p in (source / directory / "src" / namespace).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    actual = {
        key: data for key, data in payload.items() if key.startswith(namespace + "/")
    }
    require(actual == expected, f"Wheel source payload mismatch: {path.name}")
    for legal in ("LICENSE", "NOTICE"):
        data = next(
            (
                data
                for key, data in payload.items()
                if key.endswith("/licenses/" + legal)
            ),
            None,
        )
        require(
            data == (source / directory / legal).read_bytes(),
            f"Wheel legal missing: {path.name}:{legal}",
        )
    record = next(
        data for key, data in payload.items() if key.endswith(".dist-info/RECORD")
    )
    rows = list(csv.reader(io.StringIO(record.decode())))
    require({row[0] for row in rows} == set(payload), "Wheel RECORD inventory")
    for name, hashed, size in rows:
        if hashed:
            algorithm, value = hashed.split("=", 1)
            require(
                algorithm == "sha256"
                and base64.urlsafe_b64encode(hashlib.sha256(payload[name]).digest())
                .decode()
                .rstrip("=")
                == value
                and len(payload[name]) == int(size),
                f"Invalid RECORD {name}",
            )
    return {
        "namespace": namespace,
        "source_files_exact": len(actual),
        "record_entries": len(rows),
    }


class Builder:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.checkout = args.checkout.resolve()
        self.output = args.output.resolve()
        self.env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}
        }
        self.env.update(
            {
                "CI": "true",
                "NG_CLI_ANALYTICS": "false",
                "NPM_CONFIG_OFFLINE": "true",
                "NPM_CONFIG_AUDIT": "false",
                "NPM_CONFIG_FUND": "false",
                "UV_OFFLINE": "1",
                "NPM_CONFIG_USERCONFIG": str(
                    self.output / "evidence/npm-user.empty.conf"
                ),
                "NPM_CONFIG_GLOBALCONFIG": str(
                    self.output / "evidence/npm-global.empty.conf"
                ),
                "PYTHONNOUSERSITE": "1",
                "JAVA_HOME": str(args.java_home.resolve()),
            }
        )
        self.env["PATH"] = (
            str(args.java_home.resolve() / "bin") + os.pathsep + self.env["PATH"]
        )
        if args.allow_build_network:
            self.env["UV_OFFLINE"] = "0"
        self.commands = []

    def run(self, command: list[str], cwd: Path, label: str) -> str:
        require(
            shutil.disk_usage(self.output).free >= self.args.min_free_gib * 1024**3,
            "Release disk floor reached; preserve the output and stop",
        )
        path = self.output / "evidence" / f"{label}.log"
        start = time.monotonic()
        with path.open("w") as stream:
            process = subprocess.run(
                command,
                cwd=cwd,
                env=self.env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        self.commands.append(
            {
                "label": label,
                "command": command,
                "cwd": str(cwd),
                "exit_code": process.returncode,
                "seconds": round(time.monotonic() - start, 2),
                "log": str(path),
                **pin(path),
            }
        )
        (self.output / "evidence" / "commands.json").write_text(
            json.dumps(self.commands, indent=2) + "\n"
        )
        require(process.returncode == 0, f"Build failed ({label}); see {path}")
        print(f"PASS {label}", flush=True)
        return path.read_text()

    def npm(self, directory: Path, label: str) -> None:
        lock = json.loads((directory / "package-lock.json").read_text())
        for entry in lock["packages"].values():
            resolved = entry.get("resolved", "")
            require(
                not resolved
                or resolved.startswith(("https://registry.npmjs.org/", "file:", "../")),
                f"Noncanonical npm build dependency URL: {resolved}",
            )
            if resolved.startswith("https:"):
                require(
                    entry.get("integrity"), f"Missing lockfile integrity: {resolved}"
                )
        mode = "--offline=false" if self.args.allow_registry_install else "--offline"
        self.run(
            [
                "npm",
                "ci",
                mode,
                "--prefer-offline",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                "--registry=https://registry.npmjs.org",
            ],
            directory,
            label + "-install",
        )

    def pack_npm(self, directory: Path, name: str, label: str) -> Path:
        self.run(
            [
                "npm",
                "pack",
                "--offline",
                "--ignore-scripts",
                "--pack-destination",
                str(self.assets),
            ],
            directory,
            label,
        )
        path = self.assets / f"{name}-{self.args.version}.tgz"
        payload = members(path)
        metadata = json.loads(payload["package/package.json"])
        require(metadata["version"] == self.args.version, f"npm version {name}")
        for legal in ("LICENSE", "NOTICE"):
            require(
                payload.get("package/" + legal) == (self.source / legal).read_bytes(),
                f"npm legal {name}:{legal}",
            )
        for key, data in payload.items():
            relative = key.removeprefix("package/")
            require(
                key.startswith("package/")
                and (directory / relative).is_file()
                and (directory / relative).read_bytes() == data,
                f"npm payload mismatch {key}",
            )
        return path

    def build(self) -> None:
        args = self.args
        tree = clean_commit(self.checkout, args.commit)
        require(not self.output.exists(), "Output must be a new absent directory")
        require(
            not self.output.is_relative_to(self.checkout),
            "Output cannot be inside source checkout",
        )
        self.output.mkdir(mode=0o700)
        self.assets = self.output / "assets"
        self.assets.mkdir()
        (self.output / "evidence").mkdir()
        epoch = int(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(self.checkout),
                    "show",
                    "-s",
                    "--format=%ct",
                    args.commit,
                ],
                text=True,
            )
        )
        self.env["SOURCE_DATE_EPOCH"] = str(epoch)
        archive = self.assets / f"koinon-{args.version}-source.tar.gz"
        temporary = self.output / "source.tar"
        with temporary.open("wb") as stream:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.checkout),
                    "archive",
                    "--format=tar",
                    f"--prefix=koinon-{args.version}/",
                    args.commit,
                ],
                check=True,
                stdout=stream,
            )
        source_members = members(temporary)
        with (
            temporary.open("rb") as stream,
            archive.open("wb") as raw,
            gzip.GzipFile(
                fileobj=raw, mode="wb", mtime=epoch, filename=""
            ) as compressed,
        ):
            shutil.copyfileobj(stream, compressed)
        self.source = self.output / "build" / f"koinon-{args.version}"
        for name, data in source_members.items():
            path = self.output / "build" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        modes = subprocess.check_output(
            ["git", "-C", str(self.checkout), "ls-tree", "-r", args.commit], text=True
        )
        for line in modes.splitlines():
            mode, rest = line.split(" ", 1)
            relative = rest.split("\t", 1)[1]
            if mode == "100755":
                (self.source / relative).chmod(0o755)
        baseline = {
            p.relative_to(self.source).as_posix(): digest(p.read_bytes())
            for p in self.source.rglob("*")
            if p.is_file()
        }
        versions = verify_versions(self.source, args.version)
        # Build backends resolve only cached build requirements into uv's isolated build environments.
        for directory in WHEELS:
            self.run(
                [
                    "uv",
                    "build",
                    *([] if args.allow_build_network else ["--offline"]),
                    "--wheel",
                    "--out-dir",
                    str(self.assets),
                    str(self.source / directory),
                ],
                self.source,
                "wheel-" + directory.replace("/", "-"),
            )
        retain_uv_marker(self.assets, self.output / "evidence")
        wheel_report = {}
        for directory, (name, _) in WHEELS.items():
            path = (
                self.assets
                / f"{name.replace('-', '_')}-{args.version}-py3-none-any.whl"
            )
            wheel_report[path.name] = verify_wheel(
                path, self.source, directory, args.version
            )
        sdk = self.source / "sdk/typescript"
        self.npm(sdk, "typescript")
        self.run(["npm", "run", "build"], sdk, "typescript-build")
        self.pack_npm(sdk, "fireflyframework-koinon-sdk", "typescript-pack")
        frontend = self.source / "frontend"
        self.npm(frontend, "frontend")
        self.run(["npm", "run", "build"], frontend, "frontend-build")
        self.pack_npm(
            frontend / "dist/koinon-angular",
            "fireflyframework-koinon-angular",
            "angular-pack",
        )
        for app in ("management", "elements"):
            app_root = frontend / "dist" / app
            browser = app_root / "browser"
            require((browser / "index.html").is_file(), f"Missing {app} index.html")
            extra = {name: self.source / name for name in ("LICENSE", "NOTICE")}
            notices = list(app_root.glob("*licenses*.txt")) + list(
                app_root.glob("*Licenses*.txt")
            )
            require(
                notices or (browser / "3rdpartylicenses.txt").is_file(),
                f"Missing {app} third-party notices",
            )
            extra.update({p.name: p for p in notices})
            tar_directory(
                browser,
                self.assets / f"koinon-{app}-{args.version}.tar.gz",
                epoch,
                extra,
            )
            for path in (self.source / "brand").rglob("*"):
                if path.is_file() and ("OFL" in path.name or "NOTICE" in path.name):
                    target = (
                        browser
                        / "assets/brand"
                        / path.relative_to(self.source / "brand")
                    )
                    require(
                        target.is_file() and target.read_bytes() == path.read_bytes(),
                        f"Missing brand license {app}:{path.name}",
                    )
        self.run(
            [str(args.java_home / "bin/java"), "-version"], self.source, "java-version"
        )
        self.run(
            [
                "mvn",
                *([] if args.allow_build_network else ["--offline"]),
                "--batch-mode",
                "--no-transfer-progress",
                "-Dmaven.test.skip=true",
                f"-Dproject.build.outputTimestamp={epoch}",
                "package",
            ],
            self.source / "sdk/java",
            "java-package",
        )
        jar = self.source / "sdk/java/target" / f"koinon-sdk-{args.version}.jar"
        payload = members(jar)
        classes = [data for name, data in payload.items() if name.endswith(".class")]
        require(
            classes and {struct.unpack(">H", data[6:8])[0] for data in classes} == {65},
            "Java21 bytecode required",
        )
        for legal in ("LICENSE", "NOTICE"):
            require(
                payload.get("META-INF/" + legal) == (self.source / legal).read_bytes(),
                f"Java legal {legal}",
            )
        props = next(
            data for name, data in payload.items() if name.endswith("pom.properties")
        )
        require(f"version={args.version}" in props.decode(), "Java JAR version")
        shutil.copyfile(jar, self.assets / jar.name)
        mcp = self.source / "integrations/mcp-desktop"
        self.npm(mcp, "mcp")
        for command in ("typecheck", "build", "validate"):
            self.run(["npm", "run", command], mcp, "mcp-" + command)
        self.run([str(args.python), "scripts/package.py"], mcp, "mcp-package")
        for filename in (
            f"firefly-koinon-desktop-{args.version}.mcpb",
            f"firefly-koinon-skills-{args.version}.zip",
        ):
            shutil.copyfile(mcp / "dist" / filename, self.assets / filename)
        desktop = members(self.assets / f"firefly-koinon-desktop-{args.version}.mcpb")
        require(
            json.loads(desktop["manifest.json"])["version"] == args.version
            and json.loads(desktop["package.json"])["version"] == args.version,
            "MCPB version",
        )
        for item in (
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY_NOTICES.txt",
            "DEPENDENCIES.json",
            "assets/FONT-LICENSE.txt",
        ):
            require(item in desktop and desktop[item], f"MCPB legal/provenance {item}")
        skills = members(self.assets / f"firefly-koinon-skills-{args.version}.zip")
        require(
            {"LICENSE", "NOTICE", "koinon-evidence/SKILL.md"} <= skills.keys(),
            "Skill payload",
        )
        if args.docs_python:
            self.run(
                [
                    str(args.docs_python),
                    "-m",
                    "mkdocs",
                    "build",
                    "--strict",
                    "--site-dir",
                    str(self.output / "docs-site"),
                ],
                self.source,
                "docs-build",
            )
            tar_directory(
                self.output / "docs-site",
                self.assets / f"koinon-docs-{args.version}.tar.gz",
                epoch,
                {name: self.source / name for name in ("LICENSE", "NOTICE")},
            )
        changed = [
            name
            for name, hashed in baseline.items()
            if not (self.source / name).is_file()
            or digest((self.source / name).read_bytes()) != hashed
        ]
        require(not changed, f"Build mutated committed source: {changed}")
        clean_commit(self.checkout, args.commit)
        inventory = {
            path.name: {**pin(path), "archive_files": len(members(path))}
            for path in sorted(self.assets.iterdir())
        }
        expected = {
            f"{name.replace('-', '_')}-{args.version}-py3-none-any.whl"
            for name, _ in WHEELS.values()
        }
        expected.update(
            {
                f"koinon-{args.version}-source.tar.gz",
                f"koinon-management-{args.version}.tar.gz",
                f"koinon-elements-{args.version}.tar.gz",
                f"koinon-sdk-{args.version}.jar",
                f"fireflyframework-koinon-sdk-{args.version}.tgz",
                f"fireflyframework-koinon-angular-{args.version}.tgz",
                f"firefly-koinon-desktop-{args.version}.mcpb",
                f"firefly-koinon-skills-{args.version}.zip",
            }
        )
        if args.docs_python:
            expected.add(f"koinon-docs-{args.version}.tar.gz")
        require(set(inventory) == expected, "Asset allowlist differs from built assets")
        sums = self.assets / "SHA256SUMS"
        sums.write_text(
            "".join(f"{data['sha256']}  {name}\n" for name, data in inventory.items())
        )
        receipt = {
            "source_commit": args.commit,
            "source_tree": tree,
            "version": args.version,
            "source_checkout": str(self.checkout),
            "source_archive_files": len(source_members),
            "all_committed_source_unchanged_by_build": True,
            "versions": versions,
            "assets": inventory,
            "SHA256SUMS": pin(sums),
            "wheel_payloads": wheel_report,
            "java": {
                "bytecode_major": 65,
                "classes": len(classes),
                "sources_javadoc": "not configured by native pom",
            },
            "gates": {
                "source_tests": "parent-owned exact-commit evidence",
                "local_asset_assembly": "passed",
                "isolated_installed_artifact": "not performed by packager",
                "hosted_ci": "parent-owned separate gate",
                "publication": "not performed",
                "remote_download": "not performed",
                "live_acceptance": "not performed",
            },
        }
        (self.output / "evidence/inventory.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        )
        print(
            json.dumps(
                {
                    "assets": len(inventory),
                    "commit": args.commit,
                    "inventory": str(self.output / "evidence/inventory.json"),
                }
            ),
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Must not exist; assets/build/evidence stay separate",
    )
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(shutil.which("python3") or "/usr/bin/python3"),
    )
    parser.add_argument("--docs-python", type=Path)
    parser.add_argument(
        "--allow-registry-install",
        action="store_true",
        help="Explicitly allow missing integrity-pinned npm build dependencies from registry.npmjs.org",
    )
    parser.add_argument(
        "--allow-build-network",
        action="store_true",
        help="Allow uv build requirements and Maven dependencies on a fresh hosted runner",
    )
    parser.add_argument("--min-free-gib", type=int, default=16)
    args = parser.parse_args()
    args.python = args.python.resolve()
    args.java_home = args.java_home.resolve()
    if args.docs_python:
        args.docs_python = args.docs_python.absolute()
    require(args.min_free_gib >= 16, "Release disk floor cannot be below 16 GiB")
    Builder(args).build()


if __name__ == "__main__":
    main()
