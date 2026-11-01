<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SystemArtifact

[All wire models](index.md)

Model aliases: `SystemArtifact`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `component` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `present` | `boolean` or `null` | No | `null` |
| `sha256` | `string` or `null` | No | `null` |
| `content_type` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### component

- Allowed values: `"backend"`, `"documents"`, `"structured"`, `"storage"`, `"python-sdk"`, `"framework"`

### kind

- Allowed values: `"license"`, `"notice"`, `"sbom"`

### sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### content_type

- anyOf branch 1 (`string`): Allowed values: `"text/plain"`, `"application/json"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "component": {
          "enum": [
            "backend",
            "documents",
            "structured",
            "storage",
            "python-sdk",
            "framework"
          ],
          "title": "Component",
          "type": "string"
        },
        "kind": {
          "enum": [
            "license",
            "notice",
            "sbom"
          ],
          "title": "Kind",
          "type": "string"
        },
        "present": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Present"
        },
        "sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sha256"
        },
        "content_type": {
          "anyOf": [
            {
              "enum": [
                "text/plain",
                "application/json"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Content Type"
        }
      },
      "required": [
        "component",
        "kind"
      ],
      "title": "SystemArtifact",
      "type": "object"
    }
    ```
