<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MemoryReceipt

[All wire models](index.md)

Model aliases: `MemoryReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `validation_mode` | `string` | No | `"generation"` |
| `generation_id` | `string` | Yes | Not specified |
| `policy_version` | `integer` | No | `1` |
| `mode` | `string` | Yes | Not specified |
| `folder_id` | `string` or `null` | No | `null` |
| `folder_revision` | `integer` or `null` | No | `null` |
| `scope_sha256` | `string` | Yes | Not specified |
| `manifest_sha256` | `string` | Yes | Not specified |
| `organization_policy_revision` | `integer` | Yes | Not specified |
| `effective_policy` | [`OrganizationMemoryPolicy`](organizationmemorypolicy.md) | Yes | Not specified |
| `turns` | Array of [`MemoryTurnReference`](memoryturnreference.md) | No | `[]` |
| `dependency_count` | `integer` | Yes | Not specified |
| `context_available` | `boolean` | No | `true` |
| `unavailable_dependency_count` | `integer` | No | `0` |
| `created_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### validation_mode

- Allowed values: `"generation"`, `"historical_replay"`

### generation_id

- Minimum length: `1`
- Maximum length: `64`

### policy_version

- Exact value: `1`

### mode

- Allowed values: `"current_thread"`, `"personal_project"`

### folder_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### folder_revision

- anyOf branch 1 (`integer`): Minimum: `1`
- anyOf branch 1 (`integer`): Maximum: `2147483647`

### scope_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### manifest_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### organization_policy_revision

- Minimum: `0`
- Maximum: `2147483647`

### turns

- Maximum items: `20`

### dependency_count

- Minimum: `0`
- Maximum: `128`

### unavailable_dependency_count

- Minimum: `0`
- Maximum: `128`

### created_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "validation_mode": {
          "default": "generation",
          "enum": [
            "generation",
            "historical_replay"
          ],
          "title": "Validation Mode",
          "type": "string"
        },
        "generation_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Generation Id",
          "type": "string"
        },
        "policy_version": {
          "const": 1,
          "default": 1,
          "title": "Policy Version",
          "type": "integer"
        },
        "mode": {
          "enum": [
            "current_thread",
            "personal_project"
          ],
          "title": "Mode",
          "type": "string"
        },
        "folder_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Folder Id"
        },
        "folder_revision": {
          "anyOf": [
            {
              "maximum": 2147483647,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Folder Revision"
        },
        "scope_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Scope Sha256",
          "type": "string"
        },
        "manifest_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Manifest Sha256",
          "type": "string"
        },
        "organization_policy_revision": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Organization Policy Revision",
          "type": "integer"
        },
        "effective_policy": {
          "$ref": "#/$defs/OrganizationMemoryPolicy"
        },
        "turns": {
          "default": [],
          "items": {
            "$ref": "#/$defs/MemoryTurnReference"
          },
          "maxItems": 20,
          "title": "Turns",
          "type": "array"
        },
        "dependency_count": {
          "maximum": 128,
          "minimum": 0,
          "title": "Dependency Count",
          "type": "integer"
        },
        "context_available": {
          "default": true,
          "title": "Context Available",
          "type": "boolean"
        },
        "unavailable_dependency_count": {
          "default": 0,
          "maximum": 128,
          "minimum": 0,
          "title": "Unavailable Dependency Count",
          "type": "integer"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        }
      },
      "required": [
        "generation_id",
        "mode",
        "scope_sha256",
        "manifest_sha256",
        "organization_policy_revision",
        "effective_policy",
        "dependency_count",
        "created_at"
      ],
      "title": "MemoryReceipt",
      "type": "object"
    }
    ```
