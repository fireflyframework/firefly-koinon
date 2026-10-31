<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpReadReceipt

[All wire models](index.md)

Model aliases: `McpReadReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `status` | `string` | Yes | Not specified |
| `id` | `string` or `null` | No | `null` |
| `sha256` | `string` or `null` | No | `null` |
| `expires_at` | `string` or `null` | No | `null` |
| `sources` | Array of [`SourceReference`](sourcereference.md) | No | `[]` |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"recorded"`, `"not_recorded"`

### expires_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### sources

- Maximum items: `64`

### reason

- anyOf branch 1 (`string`): Allowed values: `"incomplete_or_unsupported_source_manifest"`, `"source_manifest_limit_or_missing_revision"`, `"receipt_byte_limit"`, `"active_receipt_limit"`, `"source_reuse_scope_required"`, `"capture_unavailable"`, `"transitive_lineage_unqualified"`, `"catalog_is_not_source_evidence"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "status": {
          "enum": [
            "recorded",
            "not_recorded"
          ],
          "title": "Status",
          "type": "string"
        },
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sha256"
        },
        "expires_at": {
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
          "title": "Expires At"
        },
        "sources": {
          "default": [],
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "maxItems": 64,
          "title": "Sources",
          "type": "array"
        },
        "reason": {
          "anyOf": [
            {
              "enum": [
                "incomplete_or_unsupported_source_manifest",
                "source_manifest_limit_or_missing_revision",
                "receipt_byte_limit",
                "active_receipt_limit",
                "source_reuse_scope_required",
                "capture_unavailable",
                "transitive_lineage_unqualified",
                "catalog_is_not_source_evidence"
              ],
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
        "status"
      ],
      "title": "McpReadReceipt",
      "type": "object"
    }
    ```
