# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

from pyfly.container import component

from koinon.knowledge.attachments.extraction import ExtractionFailure, extraction_input
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage


@component(name="knowledge.attachments.parser")
class PrivateAttachmentParser:
    def __init__(self, storage: AttachmentStorage, settings: AttachmentSettings):
        self.storage, self.settings = storage, settings

    async def parse(self, row, content):
        self.settings.validate()
        root = Path(self.settings.storage_root or "")
        self.storage.configured()
        temporary_root = root / ".parsers"
        temporary_root.mkdir(mode=0o700, exist_ok=True)
        if temporary_root.is_symlink() or temporary_root.stat().st_mode & 0o077:
            raise ExtractionFailure("Private parser directory is not private", "ATTACHMENT_STORAGE_REQUIRED")
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            env = {
                "PATH": os.defpath,
                "LANG": "C.UTF-8",
                "TMPDIR": directory,
                "PYTHONPATH": os.pathsep.join(str(Path(value).resolve()) for value in sys.path if value),
            }
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-B",
                "-m",
                "koinon.knowledge.attachments.extraction",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                cwd=directory,
            )

            async def exchange():
                assert process.stdin is not None and process.stdout is not None
                process.stdin.write(extraction_input(content, row, self.settings))
                await process.stdin.drain()
                process.stdin.close()
                output = bytearray()
                while block := await process.stdout.read(65536):
                    output.extend(block)
                    if len(output) > 32 * 1024 * 1024:
                        raise ExtractionFailure("Parser output exceeded its limit", "ATTACHMENT_TEXT_LIMIT")
                await process.wait()
                if process.returncode != 0:
                    raise ExtractionFailure(
                        "Private parser stopped before completion", "ATTACHMENT_PARSER_STOPPED"
                    )
                return json.loads(output)

            async def memory_fence():
                while process.returncode is None:
                    monitor = await asyncio.create_subprocess_exec(
                        "/bin/ps",
                        "-o",
                        "rss=",
                        "-p",
                        str(process.pid),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    output, _ = await monitor.communicate()
                    if output.strip() and int(output.strip()) > 512 * 1024:
                        raise ExtractionFailure(
                            "Parser memory exceeded its limit", "ATTACHMENT_PARSER_MEMORY_LIMIT"
                        )
                    await asyncio.sleep(0.25)

            exchange_task, memory_task = asyncio.create_task(exchange()), asyncio.create_task(memory_fence())
            try:
                async with asyncio.timeout(self.settings.extraction_timeout_seconds):
                    done, _ = await asyncio.wait(
                        (exchange_task, memory_task), return_when=asyncio.FIRST_COMPLETED
                    )
                    if memory_task in done:
                        await memory_task
                    result = await exchange_task
                    if "error" in result:
                        raise ExtractionFailure(result["error"]["message"], result["error"]["code"])
                    return result["result"]
            except TimeoutError as error:
                raise ExtractionFailure(
                    "Private parsing exceeded its time limit", "ATTACHMENT_EXTRACTION_TIMEOUT"
                ) from error
            finally:
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        process.kill()
                await process.wait()
                for task in (exchange_task, memory_task):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
