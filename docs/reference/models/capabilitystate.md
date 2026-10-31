<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CapabilityState

[All wire models](index.md)

Model aliases: `CapabilityState`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `supported` | `boolean` or `null` | No | `null` |
| `verified` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "supported": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Supported"
        },
        "verified": {
          "default": false,
          "title": "Verified",
          "type": "boolean"
        }
      },
      "title": "CapabilityState",
      "type": "object"
    }
    ```
