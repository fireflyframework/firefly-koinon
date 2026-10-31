<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogProposal

[All wire models](index.md)

Model aliases: `CatalogProposal`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `run_id` | `string` | Yes | Not specified |
| `kind` | `string` | No | `"catalog"` |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `asset_id` | `string` | Yes | Not specified |
| `before` | [`CatalogProposalBefore`](catalogproposalbefore.md) | Yes | Not specified |
| `changes` | [`CatalogProposalPatch`](catalogproposalpatch.md) | Yes | Not specified |
| `expected_catalog_digest` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `applied_at` | `string` or `null` | No | `null` |
| `cancelled_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"catalog"`

### status

- Allowed values: `"pending"`, `"applied"`, `"cancelled"`

### revision

- Minimum: `1`

### expected_catalog_digest

- Pattern: `"^[a-f0-9]{64}$"`

### created_at

- Format: `"date-time"`

### applied_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### cancelled_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "run_id": {
          "title": "Run Id",
          "type": "string"
        },
        "kind": {
          "const": "catalog",
          "default": "catalog",
          "title": "Kind",
          "type": "string"
        },
        "status": {
          "enum": [
            "pending",
            "applied",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "asset_id": {
          "title": "Asset Id",
          "type": "string"
        },
        "before": {
          "$ref": "#/$defs/CatalogProposalBefore"
        },
        "changes": {
          "$ref": "#/$defs/CatalogProposalPatch"
        },
        "expected_catalog_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Expected Catalog Digest",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "applied_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Applied At"
        },
        "cancelled_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cancelled At"
        }
      },
      "required": [
        "id",
        "run_id",
        "status",
        "revision",
        "asset_id",
        "before",
        "changes",
        "expected_catalog_digest",
        "created_at"
      ],
      "title": "CatalogProposal",
      "type": "object"
    }
    ```
