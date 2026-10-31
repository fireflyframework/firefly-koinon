<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DomainCapability

[All wire models](index.md)

Model aliases: `DomainCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `installed` | `boolean` | Yes | Not specified |
| `registered` | `boolean` | Yes | Not specified |
| `beans` | `integer` or `null` | No | `null` |
| `qualified` | `boolean` or `null` | No | `null` |
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
        "installed": {
          "title": "Installed",
          "type": "boolean"
        },
        "registered": {
          "title": "Registered",
          "type": "boolean"
        },
        "beans": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Beans"
        },
        "qualified": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Qualified"
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
        "installed",
        "registered"
      ],
      "title": "DomainCapability",
      "type": "object"
    }
    ```
