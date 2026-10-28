# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded native embedding contract qualification before allocating an index."""

import asyncio
from math import isfinite
from numbers import Real

from pyfly.kernel import InvalidRequestException, ServiceUnavailableException


async def qualify_embedding(lifetime, *, domain, expected_dimensions=None):
    if domain not in {"documents", "structured"}:
        raise InvalidRequestException("Choose a supported knowledge domain", code="INVALID_INDEX_DOMAIN")
    try:
        async with lifetime as embedder, asyncio.timeout(20):
            result = await embedder.embed(
                ["Knowledge index dimension qualification.", "A second bounded embedding."]
            )
            vectors = result.embeddings
    except (InvalidRequestException, ServiceUnavailableException):
        raise
    except Exception as error:
        raise ServiceUnavailableException(
            "The selected embedding connection failed qualification; verify endpoint, credential and model",
            code="INDEX_PROVIDER_UNAVAILABLE",
        ) from error
    if (
        not isinstance(vectors, (list, tuple))
        or len(vectors) != 2
        or any(not isinstance(vector, (list, tuple)) for vector in vectors)
        or not 64 <= len(vectors[0]) <= 4096
        or len(vectors[0]) != len(vectors[1])
        or any(
            not vector
            or not any(value != 0 for value in vector)
            or any(
                isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value)
                for value in vector
            )
            for vector in vectors
        )
    ):
        raise InvalidRequestException(
            "The provider returned an invalid embedding width or nonfinite/empty vectors",
            code="INVALID_INDEX_EMBEDDINGS",
        )
    width = len(vectors[0])
    if domain == "documents" and width > 4000:
        raise InvalidRequestException(
            "The native ANN strategy supports at most 4000 dimensions; select a compatible embedding model",
            code="INDEX_ANN_DIMENSIONS_UNSUPPORTED",
        )
    if (expected_dimensions is not None and width != expected_dimensions) or (
        domain == "structured" and width > 1536
    ):
        raise InvalidRequestException(
            "The actual provider width does not match the requested compatible storage space",
            code="INDEX_DIMENSIONS_MISMATCH",
        )
    return {
        "dimensions": width,
        "storage_dimensions": 1536 if domain == "structured" else width,
        "qualification": "probe_passed",
    }
