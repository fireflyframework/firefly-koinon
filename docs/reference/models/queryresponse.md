<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryResponse

[All wire models](index.md)

Model aliases: `QueryResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `knowledge_settings_snapshot` | [`OrganizationKnowledgeSnapshot`](organizationknowledgesnapshot.md) or `null` | No | `null` |
| `query_id` | `string` | Yes | Not specified |
| `sql` | `string` or `null` | No | `null` |
| `execution_status` | `string` or `null` | Yes | Not specified |
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

## Model constraints

- Additional properties: permitted

## Field constraints

### execution_status

- anyOf branch 1 (`string`): Allowed values: `"OK"`, `"REFINED_OK"`, `"FAILED"`, `"REJECTED_BY_FIREWALL"`

### preview

- anyOf branch 1 (Array of Map of string keys to [`JsonValue`](jsonvalue.md)): Each item: Additional properties: [`JsonValue`](jsonvalue.md)

### chart_hint

- anyOf branch 1 (`string`): Allowed values: `"line"`, `"bar"`, `"table"`, `"pie"`, `"none"`

### grounded_summary

- anyOf branch 1 (Map of string keys to [`JsonValue`](jsonvalue.md)): Additional properties: [`JsonValue`](jsonvalue.md)

### snapshot_pins

- Additional properties: `string`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "knowledge_settings_snapshot": {
          "anyOf": [
            {
              "$ref": "#/$defs/OrganizationKnowledgeSnapshot"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "query_id": {
          "title": "Query Id",
          "type": "string"
        },
        "sql": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sql"
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
        "preview": {
          "anyOf": [
            {
              "items": {
                "additionalProperties": {
                  "$ref": "#/$defs/JsonValue"
                },
                "type": "object"
              },
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
          "title": "Snapshot Pins",
          "type": "object"
        }
      },
      "required": [
        "query_id",
        "execution_status"
      ],
      "title": "QueryResponse",
      "type": "object"
    }
    ```
