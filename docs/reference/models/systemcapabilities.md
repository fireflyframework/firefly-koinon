<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SystemCapabilities

[All wire models](index.md)

Model aliases: `SystemCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `knowledge_enabled` | `boolean` | Yes | Not specified |
| `mcp_enabled` | `boolean` | Yes | Not specified |
| `communications_enabled` | `boolean` | Yes | Not specified |
| `scheduled_consumers_enabled` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "knowledge_enabled": {
          "title": "Knowledge Enabled",
          "type": "boolean"
        },
        "mcp_enabled": {
          "title": "Mcp Enabled",
          "type": "boolean"
        },
        "communications_enabled": {
          "title": "Communications Enabled",
          "type": "boolean"
        },
        "scheduled_consumers_enabled": {
          "title": "Scheduled Consumers Enabled",
          "type": "boolean"
        }
      },
      "required": [
        "knowledge_enabled",
        "mcp_enabled",
        "communications_enabled",
        "scheduled_consumers_enabled"
      ],
      "title": "SystemCapabilities",
      "type": "object"
    }
    ```
