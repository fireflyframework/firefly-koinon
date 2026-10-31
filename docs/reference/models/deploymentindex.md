<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeploymentIndex

[All wire models](index.md)

Model aliases: `DeploymentIndex`.

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
| `id` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `vector_extension` | `boolean` or `null` | No | `null` |
| `embedding_sets` | `integer` or `null` | No | `null` |
| `physical_indexes` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"passed"`, `"failed"`, `"unknown"`


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
        "id": {
          "title": "Id",
          "type": "string"
        },
        "workspace_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Id"
        },
        "vector_extension": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Vector Extension"
        },
        "embedding_sets": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Embedding Sets"
        },
        "physical_indexes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Physical Indexes"
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
      "title": "DeploymentIndex",
      "type": "object"
    }
    ```
