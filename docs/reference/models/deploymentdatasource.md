<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeploymentDatasource

[All wire models](index.md)

Model aliases: `DeploymentDatasource`.

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
| `kind` | `string` | Yes | Not specified |
| `driver` | `string` | Yes | Not specified |
| `pool` | [`ConnectionPool`](connectionpool.md) | Yes | Not specified |
| `pool_usage` | [`PoolUsage`](poolusage.md) | Yes | Not specified |
| `role_policy` | [`RoleObservation`](roleobservation.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"passed"`, `"failed"`, `"unknown"`

### kind

- Exact value: `"database"`


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
        "kind": {
          "const": "database",
          "title": "Kind",
          "type": "string"
        },
        "driver": {
          "title": "Driver",
          "type": "string"
        },
        "pool": {
          "$ref": "#/$defs/ConnectionPool"
        },
        "pool_usage": {
          "$ref": "#/$defs/PoolUsage"
        },
        "role_policy": {
          "$ref": "#/$defs/RoleObservation"
        }
      },
      "required": [
        "configured",
        "available",
        "status",
        "observed_at",
        "reason",
        "id",
        "kind",
        "driver",
        "pool",
        "pool_usage",
        "role_policy"
      ],
      "title": "DeploymentDatasource",
      "type": "object"
    }
    ```
