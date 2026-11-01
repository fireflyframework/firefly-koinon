<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SystemComponentVersion

[All wire models](index.md)

Model aliases: `SystemComponentVersion`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `distribution` | `string` | Yes | Not specified |
| `version` | `string` or `null` | No | `null` |
| `available` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Allowed values: `"backend"`, `"documents"`, `"structured"`, `"storage"`, `"python-sdk"`, `"framework"`

### distribution

- Allowed values: `"firefly-koinon"`, `"firefly-koinon-documents"`, `"firefly-koinon-structured"`, `"firefly-koinon-storage"`, `"firefly-koinon-sdk"`, `"pyfly"`

### version

- anyOf branch 1 (`string`): Maximum length: `64`
- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z0-9.!+_-]+$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "enum": [
            "backend",
            "documents",
            "structured",
            "storage",
            "python-sdk",
            "framework"
          ],
          "title": "Id",
          "type": "string"
        },
        "distribution": {
          "enum": [
            "firefly-koinon",
            "firefly-koinon-documents",
            "firefly-koinon-structured",
            "firefly-koinon-storage",
            "firefly-koinon-sdk",
            "pyfly"
          ],
          "title": "Distribution",
          "type": "string"
        },
        "version": {
          "anyOf": [
            {
              "maxLength": 64,
              "pattern": "^[A-Za-z0-9.!+_-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Version"
        },
        "available": {
          "title": "Available",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "distribution",
        "available"
      ],
      "title": "SystemComponentVersion",
      "type": "object"
    }
    ```
