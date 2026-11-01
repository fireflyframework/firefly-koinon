# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Build inert, relocatable plugin profiles without connecting or registering clients."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from plugin_profile import DeploymentProfile
from plugin_validation import validate_package

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog/koinon"
VERSION = json.loads((ROOT / "integrations/mcp-desktop/manifest.json").read_text())[
    "version"
]
SKILLS = ROOT / "integrations/mcp-desktop/skills"
NOTICE = """firefly koinon plugin packages
Copyright 2026 Firefly Software Foundation

Original package tooling and assistant instructions are licensed under Apache-2.0.
The full license is included in LICENSE. The package contains no executable server
or bundled third-party runtime. Firefly names and graphic identities remain
protected trademarks; Apache-2.0 does not grant trademark rights.
"""


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def safe_tree(root: Path):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Inputs require a real directory")
    result, total = {}, 0
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ValueError("Input symlinks are not supported")
        if file.is_file():
            if file.stat().st_size > 2 * 1024 * 1024 or len(result) >= 100:
                raise ValueError("Package inputs exceed their bound")
            total += file.stat().st_size
            if total > 4 * 1024 * 1024:
                raise ValueError("Package inputs exceed their bound")
            result[file.relative_to(root).as_posix()] = file.read_bytes()
    if sum(map(len, result.values())) > 4 * 1024 * 1024:
        raise ValueError("Package inputs exceed their bound")
    return result


def identity():
    return {
        "name": "koinon",
        "version": VERSION,
        "description": "Use authorized knowledge and organize its catalog through a separately connected koinon account.",
        "author": {
            "name": "Firefly Software Foundation",
            "url": "https://github.com/fireflyframework",
        },
        "homepage": "https://fireflyframework.github.io/firefly-koinon/",
        "repository": "https://github.com/fireflyframework/firefly-koinon",
        "license": "Apache-2.0",
        "keywords": ["knowledge", "evidence", "catalog"],
    }


def catalog_files():
    common = identity()
    palette = json.loads((ROOT / "brand/tokens.json").read_text())["palette"]
    portable = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        **common,
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "firefly koinon",
                    "shortDescription": "Work with authorized knowledge",
                    "longDescription": common["description"],
                    "developerName": "Firefly Software Foundation",
                    "category": "Productivity",
                    "capabilities": ["Read", "Write"],
                    "brandColor": palette["amber"],
                    "composerIcon": "./assets/icon.png",
                    "logo": "./assets/icon.png",
                }
            }
        },
    }
    claude = {
        **common,
        "displayName": "firefly koinon",
        "skills": "./skills/",
        "icon": "./assets/icon.png",
    }
    values = {
        "plugin.json": json_bytes(portable),
        ".claude-plugin/plugin.json": json_bytes(claude),
        "LICENSE": (ROOT / "LICENSE").read_bytes(),
        "NOTICE": NOTICE.encode(),
        "README.md": (
            b"# firefly koinon\n\nThis package supplies reusable instructions and branded assets. "
            b"It does not create a connection, register a client, grant access or approve a change. "
            b"Connect your own authorized koinon account using your operator's HTTPS endpoint. "
            b"Use OAuth for a hosted connection; the separately distributed desktop extension is a PAT alternative.\n"
        ),
    }
    for name, data in safe_tree(SKILLS).items():
        values["skills/" + name] = data
    for source, target in [
        ("brand/exports/koinon-symbol-color-512.png", "assets/icon.png"),
        ("brand/exports/koinon-symbol-reversed-512.png", "assets/icon-dark.png"),
    ]:
        path = ROOT / source
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Brand inputs must be bounded regular files")
        values[target] = path.read_bytes()
    provenance = {
        "canonical_skills": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in safe_tree(SKILLS).items()
        },
        "brand_inputs": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "brand/tokens.json",
                "brand/exports/koinon-symbol-color-512.png",
                "brand/exports/koinon-symbol-reversed-512.png",
            )
        },
        "license_sha256": hashlib.sha256(values["LICENSE"]).hexdigest(),
        "connection_or_membership_created": False,
    }
    values["README.md"] = (
        b"<!-- Copyright 2026 Firefly Software Foundation -->\n"
        b"<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
    ) + values["README.md"]
    values["SOURCES.json"] = json_bytes(provenance)
    return values


def check_catalog():
    if safe_tree(CATALOG) != catalog_files():
        raise ValueError(
            "Regenerate the catalog from the canonical skills, assets and version"
        )


def write_new(directory: Path, files):
    for parent in directory.parents:
        if parent.is_symlink():
            raise ValueError("Output ancestors must not be symlinks")
    if directory.is_symlink() or directory.exists():
        raise FileExistsError("Output already exists; it will not be overwritten")
    directory.mkdir(mode=0o700)
    for name, data in files.items():
        path = directory / name
        if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise ValueError("Package paths must stay inside their directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def zipped(destination: Path, files):
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(
                entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
            )


def build(output: Path, profile: DeploymentProfile | None = None, *, include_app=False):
    if include_app and (profile is None or profile.application_id is None):
        raise ValueError(
            "The existing-app variant requires an operator-supplied registered application ID"
        )
    write_new(output, {})
    generic = catalog_files()
    variants = {"skills": generic}
    if profile:
        claude = dict(generic)
        claude["README.md"] = (
            b"# firefly koinon deployment profile\n\nThis Claude Code profile declares the exact HTTPS endpoint "
            b"and a pre-registered public OAuth client in .mcp.json. It does not register a client, link an "
            b"account or grant access. Your operator must register its exact localhost callback and scopes; "
            b"authenticate through the client's supported MCP account flow. Cloud connectors need their own "
            b"host callback and account setup. No credentials are included.\n"
        )
        claude[".mcp.json"] = json_bytes(
            {
                "mcpServers": {
                    "koinon": {
                        "type": "http",
                        "url": profile.server_url,
                        "oauth": {
                            "clientId": profile.public_client_id,
                            "callbackPort": profile.callback_port,
                            "scopes": " ".join(profile.scopes),
                        },
                    }
                }
            }
        )
        variants["claude"] = claude
        portable = {
            k: v for k, v in generic.items() if not k.startswith(".claude-plugin/")
        }
        portable["README.md"] = (
            b"# firefly koinon deployment profile\n\nThe root mcp.json declares the exact HTTPS endpoint and "
            b"a provided public OAuth client. Complete account linking and review the requested scope. "
            b"It does not register a client or grant access. Imported MCP packages may be Desktop only, "
            b"including HTTPS connections. The documented OpenAI auth extension is validated separately "
            b"because the published Agent Plugins 1.0.0 MCP schema does not allow that extension.\n"
        )
        portable["mcp.json"] = json_bytes(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "koinon": {
                        "type": "streamable-http",
                        "url": profile.server_url,
                        "extensions": {
                            "com.openai": {
                                "auth": {
                                    "type": "oauth",
                                    "client": {
                                        "mode": "provided",
                                        "clientId": profile.public_client_id,
                                        "tokenEndpointAuthMethod": "none",
                                    },
                                    "defaultScopes": list(profile.scopes),
                                }
                            }
                        },
                    }
                },
            }
        )
        variants["portable"] = portable
        if include_app:
            registered = {
                k: v for k, v in generic.items() if not k.startswith(".claude-plugin/")
            }
            manifest = json.loads(registered["plugin.json"])
            manifest["extensions"]["com.openai"]["apps"] = "./.app.json"
            registered["README.md"] = (
                b"# firefly koinon registered application reference\n\nThis package references the existing "
                b"application supplied by your operator in .app.json. It does not create or verify that "
                b"application, change workspace access or link an account. The reference does not guarantee "
                b"web availability or remove a Desktop only classification.\n"
            )
            registered["plugin.json"] = json_bytes(manifest)
            registered[".app.json"] = json_bytes(
                {
                    "apps": {
                        "koinon": {
                            "id": profile.application_id,
                            "required": True,
                        }
                    }
                }
            )
            variants["registered-app"] = registered
    inventory = {}
    for name, values in variants.items():
        if not values["README.md"].startswith(b"<!-- Copyright"):
            values["README.md"] = (
                b"<!-- Copyright 2026 Firefly Software Foundation -->\n"
                b"<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
            ) + values["README.md"]
        write_new(output / name, values)
        validation = validate_package(output / name)
        suffix = ""
        if name != "skills":
            assert profile is not None
            suffix = "-" + profile.name
        archive = output / f"firefly-koinon-plugin-{name}{suffix}-{VERSION}.zip"
        zipped(archive, values)
        inventory[archive.name] = {
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "bytes": archive.stat().st_size,
            "files": {
                path: hashlib.sha256(data).hexdigest()
                for path, data in sorted(values.items())
            },
            "validation": validation,
        }
    (output / "SHA256SUMS").write_text(
        "".join(
            row["sha256"] + "  " + name + "\n"
            for name, row in sorted(inventory.items())
        )
    )
    (output / "BUILD.json").write_bytes(
        json_bytes(
            {
                "version": VERSION,
                "qualification": "offline_package_candidate_not_client_acceptance",
                "artifacts": inventory,
                "remote_registration_or_credentials": "not_performed",
            }
        )
    )
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--include-existing-app", action="store_true")
    parser.add_argument("--check-catalog", action="store_true")
    parser.add_argument("--write-catalog", action="store_true")
    parser.add_argument("--refresh-catalog", action="store_true")
    args = parser.parse_args()
    if args.check_catalog:
        check_catalog()
    elif args.refresh_catalog:
        expected = catalog_files()
        if not set(safe_tree(CATALOG)) <= set(expected):
            raise ValueError(
                "Unexpected catalog files; review the source inventory before regeneration"
            )
        for name, content in expected.items():
            destination = CATALOG / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    elif args.write_catalog:
        CATALOG.parent.mkdir(parents=True, exist_ok=True)
        write_new(CATALOG, catalog_files())
    else:
        if args.output is None:
            parser.error("--output is required")
        if args.profile is not None and (
            args.profile.is_symlink()
            or not args.profile.is_file()
            or args.profile.stat().st_size > 65536
        ):
            parser.error("Profile must be a bounded regular JSON file")
        profile = (
            DeploymentProfile.model_validate_json(args.profile.read_bytes())
            if args.profile
            else None
        )
        inventory = build(args.output, profile, include_app=args.include_existing_app)
        print(json.dumps({"status": "built_offline", "artifacts": sorted(inventory)}))


if __name__ == "__main__":
    main()
