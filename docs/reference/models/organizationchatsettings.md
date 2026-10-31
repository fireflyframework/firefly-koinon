<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationChatSettings

[All wire models](index.md)

Model aliases: `OrganizationChatSettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `default_agent_id` | `string` or `null` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `configured` | `boolean` | Yes | Not specified |
| `memory` | [`OrganizationMemoryPolicy`](organizationmemorypolicy.md) | No | Not specified |
| `can_run` | `boolean` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Minimum: `0`
- Maximum: `2147483647`

### status

- Allowed values: `"unconfigured"`, `"unavailable"`, `"disabled"`, `"needs_setup"`, `"unverified"`, `"ready"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "default_agent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Default Agent Id"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "memory": {
          "$ref": "#/$defs/OrganizationMemoryPolicy"
        },
        "can_run": {
          "title": "Can Run",
          "type": "boolean"
        },
        "status": {
          "enum": [
            "unconfigured",
            "unavailable",
            "disabled",
            "needs_setup",
            "unverified",
            "ready"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "tenant_id",
        "default_agent_id",
        "revision",
        "configured",
        "can_run",
        "status"
      ],
      "title": "OrganizationChatSettings",
      "type": "object"
    }
    ```
