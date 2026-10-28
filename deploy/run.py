# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run a command with a private literal KEY=VALUE file without shell evaluation."""

import argparse
import os
import stat
from pathlib import Path


def environment(path: Path) -> dict[str, str]:
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("Environment file must have mode 0600")
    result = os.environ.copy()
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            key, separator, value = line.partition("=")
            if not separator or not key.isidentifier():
                raise ValueError("Expected literal KEY=VALUE lines")
            result[key] = value
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Supply a command after --")
    os.execvpe(command[0], command, environment(args.env_file))
