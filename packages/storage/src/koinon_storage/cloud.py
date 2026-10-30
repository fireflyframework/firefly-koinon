# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded cloud byte transport shared by the native document and structured ports."""

import hashlib
import hmac
import importlib
import os
import re
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from koinon_storage.client_lifecycle import ClientLifecycle
from koinon_storage.client_lifecycle import client_operation as _cloud_operation


class ObjectTooLargeError(ValueError):
    pass


class ObjectIntegrityError(OSError):
    pass


class ObjectCollisionError(OSError):
    pass


def validate_key(key: str, *, prefix: bool = False) -> str:
    if prefix and key == "":
        return key
    if (
        not isinstance(key, str)
        or not key
        or len(key.encode("utf-8")) > 1024
        or key.startswith("/")
        or any(
            part in {"", ".", ".."} for part in (key[:-1] if prefix and key.endswith("/") else key).split("/")
        )
        or (not prefix and key.endswith("/"))
        or any(char in key for char in ("\\", "\0", "\r", "\n"))
    ):
        raise ValueError("A relative registered object key is required")
    return key


def validate_endpoint(value: str) -> None:
    parsed = urlsplit(value)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(char in value for char in ("\0", "\r", "\n"))
        or (
            parsed.scheme != "https"
            and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"})
        )
    ):
        raise ValueError("Cloud endpoints require HTTPS or explicit loopback without credentials")
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError("Cloud endpoint has an invalid port") from None


@dataclass
class CloudProfile:
    backend: str
    azure_account_url: str = ""
    azure_container: str = ""
    azure_prefix: str = ""
    gcs_bucket: str = ""
    gcs_project: str = ""
    gcs_prefix: str = ""
    gcs_endpoint_url: str = ""
    request_timeout_seconds: int = 10
    max_object_bytes: int = 64 * 1024 * 1024

    def __post_init__(self):
        if self.backend not in {"azure", "gcs"}:
            raise ValueError("Cloud backend must be azure or gcs")
        if type(self.request_timeout_seconds) is not int or not 1 <= self.request_timeout_seconds <= 60:
            raise ValueError("Cloud timeout must be an integer from 1 to 60 seconds")
        if type(self.max_object_bytes) is not int or not 1 <= self.max_object_bytes <= 64 * 1024 * 1024:
            raise ValueError("Cloud object byte limit must be from 1 byte to 64 MiB")
        for name in (
            "azure_account_url",
            "azure_container",
            "azure_prefix",
            "gcs_bucket",
            "gcs_project",
            "gcs_prefix",
            "gcs_endpoint_url",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or any(char in value for char in ("\0", "\r", "\n")):
                raise ValueError("Cloud settings must be plain configuration strings")
        for value in (self.azure_prefix, self.gcs_prefix):
            validate_key(value, prefix=True)
        for value in (self.azure_account_url, self.gcs_endpoint_url):
            if value:
                validate_endpoint(value)
        if self.backend == "azure":
            if (
                not self.azure_account_url
                or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])", self.azure_container)
                or "--" in self.azure_container
            ):
                raise ValueError("Azure requires an explicit account URL and valid existing container")
        elif not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", self.gcs_bucket):
            raise ValueError("GCS requires a valid existing bucket")


class CloudStore:
    """Immutable creates with bounded verification; never provisions provider resources.

    SDK work runs in a worker thread. Cancellation drains the current bounded SDK
    operation before propagating, preventing an unobserved write racing a retry.
    Socket limits do not promise hard process deadlines. Cloud lifecycle policies
    remain responsible for abandoned SDK-managed resumable upload sessions.
    """

    def __init__(self, profile: CloudProfile, *, client: Any = None, owns_client: bool = True):
        profile.__post_init__()
        self.profile, self._client = profile, client
        self._credential = None
        self._owns_client = owns_client if client is not None else True
        self._lifecycle = ClientLifecycle()
        self._client_lock = threading.Lock()
        self.connection_string: str | None = None
        self.service_file: str | None = None
        self.encryption_scope: str | None = None

    @property
    def _closing(self):
        return self._lifecycle.closing

    @property
    def _closed(self):
        return self._lifecycle.closed

    def _operation(self):
        return self._lifecycle.operation()

    def _sdk(self):
        with self._client_lock:
            if self._client is None:
                profile = self.profile
                try:
                    if profile.backend == "azure":
                        if self.connection_string:
                            parts = dict(
                                part.split("=", 1)
                                for part in self.connection_string.split(";")
                                if "=" in part
                            )
                            endpoint = parts.get("BlobEndpoint") or (
                                parts.get("DefaultEndpointsProtocol", "https")
                                + "://"
                                + parts.get("AccountName", "")
                                + ".blob."
                                + parts.get("EndpointSuffix", "core.windows.net")
                            )
                            if endpoint.rstrip("/") != profile.azure_account_url.rstrip("/"):
                                raise ValueError("Azure credentials conflict with the configured account")
                        sdk = importlib.import_module("azure.storage.blob")
                        identity = importlib.import_module("azure.identity")
                        loopback = urlsplit(profile.azure_account_url).hostname in {
                            "127.0.0.1",
                            "localhost",
                            "::1",
                        }
                        self._credential = (
                            None if self.connection_string or loopback else identity.DefaultAzureCredential()
                        )
                        client_options = dict(
                            credential=self._credential,
                            connection_timeout=profile.request_timeout_seconds,
                            read_timeout=profile.request_timeout_seconds,
                            retry_total=0,
                            retry_connect=0,
                            retry_read=0,
                            retry_status=0,
                            max_single_put_size=64 * 1024 * 1024,
                            max_single_get_size=4 * 1024 * 1024,
                            max_chunk_get_size=4 * 1024 * 1024,
                        )
                        if self.connection_string:
                            client_options.pop("credential")
                            self._client = sdk.BlobServiceClient.from_connection_string(
                                self.connection_string, **client_options
                            )
                        else:
                            self._client = sdk.BlobServiceClient(profile.azure_account_url, **client_options)
                    else:
                        for name in ("STORAGE_EMULATOR_HOST", "API_ENDPOINT_OVERRIDE"):
                            ambient = os.environ.get(name)
                            if ambient and ambient.rstrip("/") != profile.gcs_endpoint_url.rstrip("/"):
                                raise ValueError(
                                    "Cloud endpoints must be selected by the explicit storage profile"
                                )
                        sdk = importlib.import_module("google.cloud.storage")
                        kwargs: dict[str, Any] = {"project": profile.gcs_project or None}
                        if profile.gcs_endpoint_url:
                            # An explicit emulator endpoint is the only anonymous path.
                            if urlsplit(profile.gcs_endpoint_url).hostname in {
                                "127.0.0.1",
                                "localhost",
                                "::1",
                            }:
                                kwargs["credentials"] = importlib.import_module(
                                    "google.auth.credentials"
                                ).AnonymousCredentials()
                            kwargs["client_options"] = {"api_endpoint": profile.gcs_endpoint_url}
                        self._client = (
                            sdk.Client.from_service_account_json(self.service_file, **kwargs)
                            if self.service_file
                            else sdk.Client(**kwargs)
                        )
                except ImportError:
                    raise OSError("Install the declared cloud storage SDK extra") from None
            return self._client

    def _full_key(self, key: str, *, prefix: bool = False) -> str:
        validate_key(key, prefix=prefix)
        configured = self.profile.azure_prefix if self.profile.backend == "azure" else self.profile.gcs_prefix
        configured = configured.rstrip("/")
        full = configured + "/" + key if configured else key
        validate_key(full, prefix=prefix)
        return full

    def _object(self, key: str):
        client = self._sdk()
        if self.profile.backend == "azure":
            return client.get_blob_client(container=self.profile.azure_container, blob=key)
        return client.bucket(self.profile.gcs_bucket).blob(key)

    def _options(self):
        options: dict[str, Any] = {"timeout": self.profile.request_timeout_seconds}
        if self.profile.backend == "gcs":
            options["retry"] = None
        return options

    @staticmethod
    def _status(error):
        status = (
            getattr(error, "status_code", None)
            or getattr(error, "code", None)
            or getattr(getattr(error, "response", None), "status_code", None)
        )
        return status() if callable(status) else status

    async def _run(self, function):
        with self._operation():
            try:
                return await self._lifecycle.run(function)
            except (ObjectTooLargeError, ObjectIntegrityError, ObjectCollisionError, FileNotFoundError):
                raise
            except Exception as error:
                if self._status(error) == 404:
                    raise FileNotFoundError("Registered cloud object is unavailable") from None
                raise OSError("Cloud object storage request failed") from None

    @_cloud_operation
    async def put(self, key: str, data: bytes, content_type: str | None = None, *, kms_key_uri=None):
        full = self._full_key(key)
        if not isinstance(data, bytes) or len(data) > self.profile.max_object_bytes:
            raise ObjectTooLargeError("Cloud object exceeds its configured byte limit")
        digest = hashlib.sha256(data).hexdigest()

        def write():
            blob = self._object(full)
            metadata = {"sha256": digest, "bytes": str(len(data))}
            try:
                if self.profile.backend == "azure":
                    sdk = importlib.import_module("azure.storage.blob")
                    scope = kms_key_uri or self.encryption_scope
                    options = {"encryption_scope": scope} if scope else {}
                    blob.upload_blob(
                        data,
                        overwrite=False,
                        metadata=metadata,
                        content_settings=sdk.ContentSettings(
                            content_type=content_type or "application/octet-stream"
                        ),
                        max_concurrency=1,
                        **self._options(),
                        **options,
                    )
                else:
                    blob.metadata = metadata
                    if kms_key_uri:
                        blob.kms_key_name = kms_key_uri
                    if len(data) > 8 * 1024 * 1024:
                        self._upload_gcs_session(blob, data, content_type)
                    else:
                        blob.upload_from_string(
                            data,
                            content_type=content_type or "application/octet-stream",
                            if_generation_match=0,
                            checksum="auto",
                            **self._options(),
                        )
            except Exception as error:
                if self._status(error) not in {409, 412}:
                    raise
                return False
            return True

        created = await self._run(write)
        try:
            persisted = await self.get_bounded(key, len(data))
        except ObjectTooLargeError:
            if not created:
                raise ObjectCollisionError("Cloud object collision with retained bytes") from None
            raise ObjectIntegrityError("Cloud persisted-byte verification failed") from None
        if len(persisted) != len(data) or not hmac.compare_digest(
            hashlib.sha256(persisted).hexdigest(), digest
        ):
            raise ObjectCollisionError("Cloud object collision or persisted-byte verification failure")

    def _upload_gcs_session(self, blob, data: bytes, content_type):
        # The SDK creates an authenticated, create-only resumable session. Its
        # bearer URL is used only by this operation and is never exposed/logged.
        # The final single transfer and failed-session abort both have explicit
        # socket bounds; no private SDK transfer APIs or global retry policy.
        requests = importlib.import_module("requests")
        session_url = blob.create_resumable_upload_session(
            content_type=content_type or "application/octet-stream",
            size=len(data),
            if_generation_match=0,
            **self._options(),
        )
        validate_endpoint(session_url.split("?", 1)[0])
        endpoint = urlsplit(self.profile.gcs_endpoint_url or "https://storage.googleapis.com")
        session_endpoint = urlsplit(session_url)
        if (session_endpoint.scheme, session_endpoint.netloc) != (endpoint.scheme, endpoint.netloc):
            raise OSError("Cloud upload session is outside its configured endpoint")
        with requests.Session() as transport:
            try:
                response = transport.put(
                    session_url,
                    data=data,
                    headers={
                        "Content-Type": content_type or "application/octet-stream",
                        "Content-Length": str(len(data)),
                        "Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}",
                    },
                    timeout=self.profile.request_timeout_seconds,
                    allow_redirects=False,
                )
                response.raise_for_status()
                if response.status_code not in {200, 201}:
                    raise OSError("Cloud upload session did not complete")
            except BaseException:
                with suppress(Exception):
                    transport.delete(
                        session_url, timeout=self.profile.request_timeout_seconds, allow_redirects=False
                    )
                raise

    def _read(self, key: str, max_bytes: int) -> bytes:
        blob = self._object(key)
        if self.profile.backend == "azure":
            props = blob.get_blob_properties(**self._options())
            if props.size > max_bytes:
                raise ObjectTooLargeError("Cloud object exceeds its read bound")
            conditions = importlib.import_module("azure.core").MatchConditions
            size, metadata = props.size, getattr(props, "metadata", None) or {}
            if props.size == 0:
                return self._verified(b"", size, metadata)
            content = blob.download_blob(
                offset=0,
                length=max_bytes + 1,
                etag=props.etag,
                match_condition=conditions.IfNotModified,
                max_concurrency=1,
                **self._options(),
            ).readall()
        else:
            blob.reload(**self._options())
            if blob.size > max_bytes:
                raise ObjectTooLargeError("Cloud object exceeds its read bound")
            size, metadata = blob.size, blob.metadata or {}
            if blob.size == 0:
                return self._verified(b"", size, metadata)
            content = blob.download_as_bytes(
                start=0,
                end=max_bytes,
                if_generation_match=blob.generation,
                checksum="auto",
                **self._options(),
            )
        if len(content) > max_bytes:
            raise ObjectTooLargeError("Cloud object exceeds its read bound")
        return self._verified(content, size, metadata)

    @staticmethod
    def _verified(content, size, metadata):
        if len(content) != size:
            raise ObjectIntegrityError("Cloud object length verification failed")
        if "sha256" in metadata or "bytes" in metadata:
            digest = metadata.get("sha256", "")
            if (
                metadata.get("bytes") != str(size)
                or not isinstance(digest, str)
                or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), digest)
            ):
                raise ObjectIntegrityError("Cloud object digest verification failed")
        return content

    @_cloud_operation
    async def get_bounded(self, key: str, max_bytes: int) -> bytes:
        full = self._full_key(key)
        if type(max_bytes) is not int or not 0 <= max_bytes <= self.profile.max_object_bytes:
            raise ValueError("Cloud read requires a configured byte bound")
        return await self._run(lambda: self._read(full, max_bytes))

    @_cloud_operation
    async def get(self, key: str) -> bytes:
        return await self.get_bounded(key, self.profile.max_object_bytes)

    def get_sync(self, key: str) -> bytes:
        with self._operation():
            full = self._full_key(key)
            try:
                return self._read(full, self.profile.max_object_bytes)
            except (ObjectTooLargeError, ObjectIntegrityError, FileNotFoundError):
                raise
            except Exception as error:
                if self._status(error) == 404:
                    raise FileNotFoundError("Registered cloud object is unavailable") from None
                raise OSError("Cloud object storage request failed") from None

    @_cloud_operation
    async def delete(self, key: str):
        full = self._full_key(key)

        def remove():
            try:
                self._object(full).delete_blob(
                    **self._options()
                ) if self.profile.backend == "azure" else self._object(full).delete(**self._options())
            except Exception as error:
                if self._status(error) != 404:
                    raise

        await self._run(remove)

    @_cloud_operation
    async def exists(self, key: str) -> bool:
        try:
            await self.head(key)
        except FileNotFoundError:
            return False
        return True

    @_cloud_operation
    async def head(self, key: str):
        full = self._full_key(key)

        def metadata():
            blob = self._object(full)
            if self.profile.backend == "azure":
                return blob.get_blob_properties(**self._options())
            blob.reload(**self._options())
            return blob

        return await self._run(metadata)

    @_cloud_operation
    async def purge_staging(self, key: str):
        validate_key(key)

    async def close(self):
        """Drain admitted work, then release owned resources exactly once.

        Supplying a client transfers ownership by default for compatibility.
        Set ``owns_client=False`` when its lifecycle belongs to another bean.
        """

        def release():
            failure = None
            if self._owns_client and self._client is not None:
                try:
                    self._client.close()
                except BaseException as error:
                    failure = error
            if self._credential is not None:
                try:
                    self._credential.close()
                except BaseException as error:
                    if failure is None:
                        failure = error
            if failure is not None:
                raise failure

        await self._lifecycle.close(release)

    @_cloud_operation
    async def list_metadata(self, prefix: str):
        full = self._full_key(prefix, prefix=True)

        def listing():
            client = self._sdk()
            if self.profile.backend == "azure":
                values = client.get_container_client(self.profile.azure_container).list_blobs(
                    name_starts_with=full, results_per_page=100, **self._options()
                )
            else:
                values = client.list_blobs(
                    self.profile.gcs_bucket, prefix=full, page_size=100, max_results=10001, **self._options()
                )
            result = []
            for value in values:
                if len(result) >= 10000:
                    raise OSError("Cloud object listing exceeds its supported bound")
                result.append(value)
            return result

        return await self._run(listing)

    @_cloud_operation
    async def presign_get(self, key: str, ttl_s: int) -> str:
        from datetime import UTC, datetime, timedelta

        full = self._full_key(key)
        if type(ttl_s) is not int or not 1 <= ttl_s <= 604800:
            raise ValueError("Signed object URL lifetime must be from 1 second to 7 days")

        def sign():
            expires = datetime.now(tz=UTC) + timedelta(seconds=ttl_s)
            if self.profile.backend == "gcs":
                return self._object(full).generate_signed_url(version="v4", expiration=expires, method="GET")
            sdk = importlib.import_module("azure.storage.blob")
            client = self._sdk()
            parts = dict(
                part.split("=", 1) for part in (self.connection_string or "").split(";") if "=" in part
            )
            if parts.get("AccountKey"):
                signing = {"account_key": parts["AccountKey"]}
            else:
                start = datetime.now(tz=UTC) - timedelta(minutes=1)
                signing = {
                    "user_delegation_key": client.get_user_delegation_key(start, expires, **self._options())
                }
            token = sdk.generate_blob_sas(
                account_name=client.account_name,
                container_name=self.profile.azure_container,
                blob_name=full,
                **signing,
                permission=sdk.BlobSasPermissions(read=True),
                expiry=expires,
            )
            return self._object(full).url + "?" + token

        return await self._run(sign)
