<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeploymentStorage

[All wire models](index.md)

Model aliases: `DeploymentStorage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `configured` | `boolean` | Yes | Not specified |
| `available` | `boolean` or `null` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `observed_at` | `string` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |
| `ownership` | `string` or `null` | No | `null` |
| `read_only` | `boolean` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `backend` | `string` or `null` | No | `null` |
| `store_originals` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"passed"`, `"failed"`, `"unknown"`

### ownership

- anyOf branch 1 (`string`): Exact value: `"deployment"`

### read_only

- anyOf branch 1 (`boolean`): Exact value: `true`

### id

- Allowed values: `"documents"`, `"structured"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "available": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Available"
        },
        "status": {
          "enum": [
            "passed",
            "failed",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        },
        "observed_at": {
          "title": "Observed At",
          "type": "string"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        },
        "ownership": {
          "anyOf": [
            {
              "const": "deployment",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ownership"
        },
        "read_only": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Read Only"
        },
        "id": {
          "enum": [
            "documents",
            "structured"
          ],
          "title": "Id",
          "type": "string"
        },
        "backend": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend"
        },
        "store_originals": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Store Originals"
        }
      },
      "required": [
        "configured",
        "available",
        "status",
        "observed_at",
        "reason",
        "id"
      ],
      "title": "DeploymentStorage",
      "type": "object"
    }
    ```
