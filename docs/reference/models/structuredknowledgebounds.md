<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StructuredKnowledgeBounds

[All wire models](index.md)

Model aliases: `StructuredKnowledgeBounds`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `top_k_schema` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `top_k_examples` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `top_k_metrics` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `rrf_k` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `generation_candidates` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `max_refine_retries` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `grounding_min_confidence` | [`KnowledgeNumberBounds`](knowledgenumberbounds.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "top_k_schema": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "top_k_examples": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "top_k_metrics": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "rrf_k": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "generation_candidates": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "max_refine_retries": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "grounding_min_confidence": {
          "$ref": "#/$defs/KnowledgeNumberBounds"
        }
      },
      "required": [
        "top_k_schema",
        "top_k_examples",
        "top_k_metrics",
        "rrf_k",
        "generation_candidates",
        "max_refine_retries",
        "grounding_min_confidence"
      ],
      "title": "StructuredKnowledgeBounds",
      "type": "object"
    }
    ```
