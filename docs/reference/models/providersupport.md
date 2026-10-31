<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProviderSupport

[All wire models](index.md)

Model aliases: `ProviderSupport`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `native_supported` | `boolean` | Yes | Not specified |
| `exposed` | `boolean` | Yes | Not specified |
| `kind` | `string` or `null` | No | `null` |
| `api` | `string` or `null` | No | `null` |
| `model_class` | `string` | Yes | Not specified |
| `reason` | `string` or `null` | No | `null` |

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
        "native_supported": {
          "title": "Native Supported",
          "type": "boolean"
        },
        "exposed": {
          "title": "Exposed",
          "type": "boolean"
        },
        "kind": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Kind"
        },
        "api": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Api"
        },
        "model_class": {
          "title": "Model Class",
          "type": "string"
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
        }
      },
      "required": [
        "id",
        "native_supported",
        "exposed",
        "model_class"
      ],
      "title": "ProviderSupport",
      "type": "object"
    }
    ```
