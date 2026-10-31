<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BatchQueryOutcome

[All wire models](index.md)

Model aliases: `BatchQueryOutcome`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `query_id` | `string` | Yes | Not specified |
| `execution_status` | `string` or `null` | Yes | Not specified |
| `sql` | `string` or `null` | No | `null` |
| `preview` | Array of Map of string keys to [`JsonValue`](jsonvalue.md) or `null` | No | `null` |
| `row_count` | `integer` or `null` | No | `null` |
| `elapsed_ms` | `integer` or `null` | No | `null` |
| `truncated` | `boolean` | No | `false` |
| `chart_hint` | `string` or `null` | No | `null` |
| `explanation` | `string` or `null` | No | `null` |
| `clarification` | [`ClarificationFrame`](clarificationframe.md) or `null` | No | `null` |
| `grounded_summary` | Map of string keys to [`JsonValue`](jsonvalue.md) or `null` | No | `null` |
| `usage` | [`UsageSummary`](usagesummary.md) or `null` | No | `null` |
| `snapshot_pins` | Map of string keys to `string` | No | Not specified |
| `knowledge_settings_snapshot` | [`OrganizationKnowledgeSnapshot`](organizationknowledgesnapshot.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### query_id

- Format: `"uuid"`

### execution_status

- anyOf branch 1 (`string`): Allowed values: `"OK"`, `"REFINED_OK"`, `"FAILED"`, `"REJECTED_BY_FIREWALL"`

### sql

- anyOf branch 1 (`string`): Maximum length: `65536`

### preview

- anyOf branch 1 (Array of Map of string keys to [`JsonValue`](jsonvalue.md)): Maximum items: `100`
- anyOf branch 1 (Array of Map of string keys to [`JsonValue`](jsonvalue.md)): Each item: Additional properties: [`JsonValue`](jsonvalue.md)

### row_count

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `2147483647`

### elapsed_ms

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `3600000`

### chart_hint

- anyOf branch 1 (`string`): Allowed values: `"line"`, `"bar"`, `"table"`, `"pie"`, `"none"`

### explanation

- anyOf branch 1 (`string`): Maximum length: `65536`

### grounded_summary

- anyOf branch 1 (Map of string keys to [`JsonValue`](jsonvalue.md)): Additional properties: [`JsonValue`](jsonvalue.md)

### snapshot_pins

- Maximum properties: `128`
- Additional properties: `string`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "query_id": {
          "format": "uuid",
          "title": "Query Id",
          "type": "string"
        },
        "execution_status": {
          "anyOf": [
            {
              "enum": [
                "OK",
                "REFINED_OK",
                "FAILED",
                "REJECTED_BY_FIREWALL"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Execution Status"
        },
        "sql": {
          "anyOf": [
            {
              "maxLength": 65536,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sql"
        },
        "preview": {
          "anyOf": [
            {
              "items": {
                "additionalProperties": {
                  "$ref": "#/$defs/JsonValue"
                },
                "type": "object"
              },
              "maxItems": 100,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Preview"
        },
        "row_count": {
          "anyOf": [
            {
              "maximum": 2147483647,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Count"
        },
        "elapsed_ms": {
          "anyOf": [
            {
              "maximum": 3600000,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Elapsed Ms"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        },
        "chart_hint": {
          "anyOf": [
            {
              "enum": [
                "line",
                "bar",
                "table",
                "pie",
                "none"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Chart Hint"
        },
        "explanation": {
          "anyOf": [
            {
              "maxLength": 65536,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Explanation"
        },
        "clarification": {
          "anyOf": [
            {
              "$ref": "#/$defs/ClarificationFrame"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "grounded_summary": {
          "anyOf": [
            {
              "additionalProperties": {
                "$ref": "#/$defs/JsonValue"
              },
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Grounded Summary"
        },
        "usage": {
          "anyOf": [
            {
              "$ref": "#/$defs/UsageSummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "snapshot_pins": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 128,
          "title": "Snapshot Pins",
          "type": "object"
        },
        "knowledge_settings_snapshot": {
          "$ref": "#/$defs/OrganizationKnowledgeSnapshot"
        }
      },
      "required": [
        "query_id",
        "execution_status",
        "knowledge_settings_snapshot"
      ],
      "title": "BatchQueryOutcome",
      "type": "object"
    }
    ```
