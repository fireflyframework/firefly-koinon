# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compile approved connection records into the native model contract."""

import hashlib
import json
import os
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_ai.models import Model
from pyfly.agentic.models import Credential, ModelFactory, ModelOptions, ModelSpec, model_settings_for
from pyfly.agentic.models.factory import DEFAULT_CLASS_BY_PROVIDER
from pyfly.container import component

from koinon.assistants.settings import AssistantSettings

APIS = {"openai": ("chat", "responses"), "ollama": ("chat",), "anthropic": ("messages",)}
CLASSES = {"chat": "OpenAIChatModel", "responses": "OpenAIResponsesModel", "messages": "AnthropicModel"}
DEFAULT_URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


class ModelParameters(ModelOptions):
    output_mode: Literal["default", "native"] | None = None
    max_tokens: int | None = Field(
        default=4096, ge=64, le=16384, strict=True, json_schema_extra={"type": "integer"}
    )
    temperature: float | None = Field(default=None, ge=0, le=2, strict=True)
    top_p: float | None = Field(default=None, ge=0, le=1, strict=True)
    top_k: int | None = Field(default=None, ge=1, le=1000, strict=True)
    seed: int | None = Field(default=None, ge=-(2**31), le=2**31 - 1, strict=True)
    request_timeout: float | None = Field(default=None, ge=0.1, le=120, strict=True)
    reasoning_budget_tokens: int | None = Field(default=None, ge=1024, le=16000, strict=True)
    stop_sequences: tuple[Annotated[str, Field(min_length=1, max_length=256)], ...] | None = Field(
        default=None, max_length=8
    )

    @field_validator("max_tokens", mode="before")
    @classmethod
    def _require_output_limit(cls, value):
        if value is None:
            raise ValueError("An explicit output-token limit is required")
        return value


def api_for(kind: str, api: str | None = None) -> str:
    if kind not in APIS:
        raise ValueError("Choose a supported provider")
    selected = api or APIS[kind][0]
    if selected not in APIS[kind]:
        raise ValueError("The selected API is not supported by this provider")
    return selected


def api_base_url(kind: str, address: str) -> str:
    value = address.strip().rstrip("/") or DEFAULT_URLS.get(kind, "")
    parts = urlsplit(value)
    if kind == "ollama":
        if not parts.path:
            value += "/v1"
        elif not parts.path.endswith("/v1"):
            raise ValueError(
                "Use an Ollama compatible API base ending in /v1; custom prefixes must include /v1"
            )
    return value


def normalized_options(api: str, values: dict | None) -> ModelParameters:
    parameters = ModelParameters.model_validate(values or {})
    if api == "responses" and parameters.store_responses is None:
        parameters = parameters.model_copy(update={"store_responses": False})
    return parameters


def output_mode_for(kind: str, values: dict | None) -> Literal["default", "native"]:
    selected = ModelParameters.model_validate(values or {}).output_mode
    return selected or ("native" if kind == "ollama" else "default")


def admit_output_mode(model: Model, mode: Literal["default", "native"], *, rlm: bool = False):
    profile = model.profile
    protocol = "native" if mode == "native" else (
        "tool" if rlm else profile.get("default_structured_output_mode", "tool")
    )
    requirements = {
        "native": ("supports_json_schema_output", False),
        "tool": ("supports_tools", True),
        "prompted": ("supports_text_output", True),
    }
    requirement = requirements.get(protocol)
    if mode not in {"default", "native"} or requirement is None or profile.get(*requirement) is not True:
        raise ValueError("The selected output mode is unsupported by the resolved model profile")
    return protocol


def options_fingerprint(api: str, values: dict | None) -> str:
    encoded = json.dumps(
        normalized_options(api, values).model_dump(mode="json", exclude_none=True), sort_keys=True
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def supported_option_fields(provider, model_id: str) -> list[str]:
    api = api_for(provider.kind, getattr(provider, "api", None))
    examples = {
        "max_tokens": 4096,
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 10,
        "seed": 1,
        "stop_sequences": ["stop"],
        "request_timeout": 30,
        "reasoning": "low",
        "reasoning_budget_tokens": 2048,
        "parallel_tool_calls": True,
        "store_responses": False,
        "output_verbosity": "low",
    }
    supported = ["output_mode"]
    for name, value in examples.items():
        try:
            spec = ModelSpec(
                provider=provider.kind,
                model=model_id,
                base_url=api_base_url(provider.kind, provider.base_url),
                model_class=CLASSES[api],
                credential=Credential.none(),
                options=normalized_options(api, {name: value}),
            )
            model_settings_for(spec)
            supported.append(name)
        except ValueError:
            continue
    return supported


def capability_state(provider, options_key: str | None = None) -> list[dict]:
    checks = provider.checks if provider.validated_revision == provider.revision else []
    result = []
    for model in provider.model_ids:
        row = {
            "model_id": model,
            "observed_tools": [],
            "option_fields": supported_option_fields(provider, model),
        }
        for capability in ("chat", "streaming", "tools", "image_input", "audio_input"):
            matching = [c for c in checks if c.get("model_id") == model and c.get("capability") == capability]
            observed = next(
                (
                    c
                    for c in matching
                    if c.get("verified")
                    and c["status"] == "passed"
                    and (options_key is None or c.get("options_key") == options_key)
                ),
                None,
            )
            declared = next((c for c in matching if not c.get("verified")), None)
            row[capability] = {
                "supported": True if observed else declared.get("supported") if declared else None,
                "verified": bool(observed),
            }
            if observed and capability == "tools":
                row["observed_tools"] = observed.get("observed_tools", [])
        result.append(row)
    return result


def provider_state(provider) -> dict:
    current = provider.validated_revision == provider.revision
    checks = provider.checks if current else []
    connected = any(c["id"] == "connection" and c["status"] == "passed" for c in checks)
    discovered = connected and any(c["id"] == "models" and c["status"] == "passed" for c in checks)
    capabilities = capability_state(provider)
    verified = (
        discovered
        and bool(capabilities)
        and all(c["chat"]["verified"] and c["streaming"]["verified"] for c in capabilities)
    )
    api = api_for(provider.kind, getattr(provider, "api", None))
    return {
        "api": api,
        "model_class": CLASSES[api],
        "configured": bool(
            provider.enabled
            and provider.model_ids
            and (provider.kind == "ollama" or provider.secret_ciphertext)
        ),
        "connected": connected,
        "discovered": discovered,
        "validated": verified,
        "model_capabilities": capabilities,
        "configuration_ownership": "tenant",
        "credential_ownership": "tenant" if provider.secret_ciphertext else "none",
        "ambient_credentials": False,
        "native_adapter": {
            "ownership": "deployment",
            "read_only": True,
            "model_class": CLASSES[api],
            "provider_identity": provider.kind,
            "profile_status": "unverified",
            "reason": "Native Ollama preserves its provider identity over OpenAI-compatible chat transport; "
            "provider-specific profile behavior remains unqualified."
            if provider.kind == "ollama"
            else "Only reported observed model capabilities are qualified.",
        },
    }


@component(name="assistants.connections")
class ConnectionResolver:
    def __init__(self, settings: AssistantSettings, models: ModelFactory):
        self.settings, self.models = settings, models

    def address(self, kind: str, address: str) -> str:
        api_for(kind)
        value = api_base_url(kind, address)
        parts = urlsplit(value)
        local = parts.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            parts.hostname not in self.settings.allowed_provider_hosts
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or (parts.scheme != "https" and not (local and parts.scheme == "http"))
        ):
            raise ValueError("Provider address is not permitted by deployment settings")
        _ = parts.port
        if kind in {"openai", "ollama"} and any(
            os.getenv(key) for key in ("OPENAI_ORG_ID", "OPENAI_PROJECT_ID")
        ):
            raise ValueError(
                "Ambient OpenAI organization/project selectors are not supported for tenant connections"
            )
        if kind == "anthropic" and value != DEFAULT_URLS["anthropic"]:
            raise ValueError("Use the supported Anthropic API address")
        if kind == "anthropic" and os.getenv("ANTHROPIC_BASE_URL", "").rstrip("/") not in (
            "",
            "https://api.anthropic.com",
        ):
            raise ValueError("Native Anthropic endpoint overrides are not supported for tenant connections")
        return value

    def spec(self, provider, model_id: str, options: dict | None = None) -> ModelSpec:
        api = api_for(provider.kind, getattr(provider, "api", None))
        parameters = normalized_options(api, options)
        spec = ModelSpec(
            provider=provider.kind,
            model=model_id,
            base_url=self.address(provider.kind, provider.base_url),
            credential=Credential.none(),
            model_class=CLASSES[api],
            options=ModelOptions.model_validate(parameters.model_dump(exclude={"output_mode"})),
        )
        self.settings_for(spec)
        return spec

    def settings_for(self, spec: ModelSpec) -> dict:
        return self.models.settings_for(spec)

    def output_mode(self, provider, model_id, options, model, *, rlm=False):
        mode = output_mode_for(provider.kind, options)
        protocol = admit_output_mode(model, mode, rlm=rlm)
        option_key = options_fingerprint(api_for(provider.kind, provider.api), options)
        capability = next(
            (row for row in capability_state(provider, option_key) if row["model_id"] == model_id), None
        )
        if capability and (
            capability["chat"]["supported"] is False
            or (protocol == "tool" and capability["tools"]["supported"] is False)
        ):
            raise ValueError("The selected output mode conflicts with current model capabilities")
        return mode

    def supported_providers(self) -> list[dict]:
        aliases = {"openai-chat": ("openai", "chat"), "openai-responses": ("openai", "responses")}
        return [
            {
                "id": kind,
                "native_supported": True,
                "exposed": kind in APIS or kind in aliases,
                "kind": aliases[kind][0] if kind in aliases else kind if kind in APIS else None,
                "api": aliases[kind][1] if kind in aliases else APIS[kind][0] if kind in APIS else None,
                "model_class": model_class,
                "reason": None
                if kind in APIS or kind in aliases
                else "Requires a separately reviewed provider configuration and explicit credential binding.",
            }
            for kind, model_class in DEFAULT_CLASS_BY_PROVIDER.items()
        ]


def input_modalities(capability: dict | None) -> list[str]:
    """Only explicit current provider evidence enables a native binary input."""
    result = ["text"]
    for name, modality in (("image_input", "image"), ("audio_input", "audio")):
        if capability and capability.get(name, {}).get("supported") is True:
            result.append(modality)
    return result
