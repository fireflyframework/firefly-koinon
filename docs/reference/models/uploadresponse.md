<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UploadResponse

[All wire models](index.md)

Model aliases: `UploadResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `source` | [`CatalogEntry`](catalogentry.md) | Yes | Not specified |
| `assets` | Array of [`CatalogEntry`](catalogentry.md) | Yes | Not specified |
| `job_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "source": {
          "$ref": "#/$defs/CatalogEntry"
        },
        "assets": {
          "items": {
            "$ref": "#/$defs/CatalogEntry"
          },
          "title": "Assets",
          "type": "array"
        },
        "job_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Id"
        }
      },
      "required": [
        "source",
        "assets"
      ],
      "title": "UploadResponse",
      "type": "object"
    }
    ```
