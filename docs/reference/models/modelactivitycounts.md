<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ModelActivityCounts

[All wire models](index.md)

Model aliases: `ModelActivityCounts`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `input_tokens` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `output_tokens` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `embedding_tokens` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `cost` | [`ObservedCost`](observedcost.md) | Yes | Not specified |
| `external_client_consumption` | `string` | No | `"not_observed"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### external_client_consumption

- Exact value: `"not_observed"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "input_tokens": {
          "$ref": "#/$defs/ObservedCount"
        },
        "output_tokens": {
          "$ref": "#/$defs/ObservedCount"
        },
        "embedding_tokens": {
          "$ref": "#/$defs/ObservedCount"
        },
        "cost": {
          "$ref": "#/$defs/ObservedCost"
        },
        "external_client_consumption": {
          "const": "not_observed",
          "default": "not_observed",
          "title": "External Client Consumption",
          "type": "string"
        }
      },
      "required": [
        "input_tokens",
        "output_tokens",
        "embedding_tokens",
        "cost"
      ],
      "title": "ModelActivityCounts",
      "type": "object"
    }
    ```
