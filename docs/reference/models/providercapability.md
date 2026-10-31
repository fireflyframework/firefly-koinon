<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProviderCapability

[All wire models](index.md)

Model aliases: `ProviderCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `configured` | `boolean` | Yes | Not specified |
| `available` | `boolean` | Yes | Not specified |
| `reason` | `string` or `null` | No | `null` |
| `capabilities` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "available": {
          "title": "Available",
          "type": "boolean"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        },
        "capabilities": {
          "items": {
            "type": "string"
          },
          "title": "Capabilities",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "kind",
        "configured",
        "available"
      ],
      "title": "ProviderCapability",
      "type": "object"
    }
    ```
