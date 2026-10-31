<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StructuredKnowledgeSettings

[All wire models](index.md)

Model aliases: `StructuredKnowledgeSettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `top_k_schema` | `integer` | Yes | Not specified |
| `top_k_examples` | `integer` | Yes | Not specified |
| `top_k_metrics` | `integer` | Yes | Not specified |
| `rrf_k` | `integer` | Yes | Not specified |
| `generation_candidates` | `integer` | Yes | Not specified |
| `max_refine_retries` | `integer` | Yes | Not specified |
| `grounding_min_confidence` | `number` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### top_k_schema

- Minimum: `1`
- Maximum: `100`

### top_k_examples

- Minimum: `0`
- Maximum: `50`

### top_k_metrics

- Minimum: `0`
- Maximum: `50`

### rrf_k

- Minimum: `1`
- Maximum: `1000`

### generation_candidates

- Minimum: `1`
- Maximum: `8`

### max_refine_retries

- Minimum: `0`
- Maximum: `8`

### grounding_min_confidence

- Minimum: `0`
- Maximum: `1`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "top_k_schema": {
          "maximum": 100,
          "minimum": 1,
          "title": "Top K Schema",
          "type": "integer"
        },
        "top_k_examples": {
          "maximum": 50,
          "minimum": 0,
          "title": "Top K Examples",
          "type": "integer"
        },
        "top_k_metrics": {
          "maximum": 50,
          "minimum": 0,
          "title": "Top K Metrics",
          "type": "integer"
        },
        "rrf_k": {
          "maximum": 1000,
          "minimum": 1,
          "title": "Rrf K",
          "type": "integer"
        },
        "generation_candidates": {
          "maximum": 8,
          "minimum": 1,
          "title": "Generation Candidates",
          "type": "integer"
        },
        "max_refine_retries": {
          "maximum": 8,
          "minimum": 0,
          "title": "Max Refine Retries",
          "type": "integer"
        },
        "grounding_min_confidence": {
          "maximum": 1,
          "minimum": 0,
          "title": "Grounding Min Confidence",
          "type": "number"
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
      "title": "StructuredKnowledgeSettings",
      "type": "object"
    }
    ```
