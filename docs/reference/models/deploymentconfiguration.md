<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeploymentConfiguration

[All wire models](index.md)

Model aliases: `DeploymentConfiguration`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `ownership` | `string` | Yes | Not specified |
| `read_only` | `boolean` | Yes | Not specified |
| `datasources` | Array of [`DeploymentDatasource`](deploymentdatasource.md) | Yes | Not specified |
| `storage` | Array of [`DeploymentStorage`](deploymentstorage.md) | Yes | Not specified |
| `indexes` | Array of [`DeploymentIndex`](deploymentindex.md) | Yes | Not specified |
| `metrics` | [`MetricsObservation`](metricsobservation.md) | Yes | Not specified |
| `limits` | [`OperationalLimits`](operationallimits.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### ownership

- Exact value: `"deployment"`

### read_only

- Exact value: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "ownership": {
          "const": "deployment",
          "title": "Ownership",
          "type": "string"
        },
        "read_only": {
          "const": true,
          "title": "Read Only",
          "type": "boolean"
        },
        "datasources": {
          "items": {
            "$ref": "#/$defs/DeploymentDatasource"
          },
          "title": "Datasources",
          "type": "array"
        },
        "storage": {
          "items": {
            "$ref": "#/$defs/DeploymentStorage"
          },
          "title": "Storage",
          "type": "array"
        },
        "indexes": {
          "items": {
            "$ref": "#/$defs/DeploymentIndex"
          },
          "title": "Indexes",
          "type": "array"
        },
        "metrics": {
          "$ref": "#/$defs/MetricsObservation"
        },
        "limits": {
          "$ref": "#/$defs/OperationalLimits"
        }
      },
      "required": [
        "ownership",
        "read_only",
        "datasources",
        "storage",
        "indexes",
        "metrics",
        "limits"
      ],
      "title": "DeploymentConfiguration",
      "type": "object"
    }
    ```
