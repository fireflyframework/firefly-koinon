<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AnswerAudit

[All wire models](index.md)

Model aliases: `AnswerAudit`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `run_id` | `string` | Yes | Not specified |
| `provenance_status` | `string` | Yes | Not specified |
| `source_provenance_complete` | `boolean` or `null` | No | `null` |
| `knowledge_settings_snapshot` | [`OrganizationKnowledgeSnapshot`](organizationknowledgesnapshot.md) or `null` | No | `null` |
| `memory` | [`MemoryReceipt`](memoryreceipt.md) or `null` | No | `null` |
| `generations` | Array of [`GenerationReceipt`](generationreceipt.md) | No | Not specified |
| `sources` | Array of [`SourceReference`](sourcereference.md) | No | Not specified |
| `private_files` | Array of [`PrivateFileReceipt`](privatefilereceipt.md) | No | Not specified |
| `native_reads` | Array of [`NativeReadReceipt`](nativereadreceipt.md) | No | Not specified |
| `sql_attempts` | Array of [`SqlAttemptReceipt`](sqlattemptreceipt.md) | No | Not specified |
| `rlm_tools` | Array of [`RlmToolReceipt`](rlmtoolreceipt.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### provenance_status

- Allowed values: `"recorded"`, `"not_recorded"`

### generations

- Maximum items: `100`

### sources

- Maximum items: `500`

### private_files

- Maximum items: `10`

### native_reads

- Maximum items: `1000`

### sql_attempts

- Maximum items: `1000`

### rlm_tools

- Actual recorded RLM function actions. Null means unrecorded; historical traces are never backfilled. A list does not assert that an interrupted generation has a complete trace.
- anyOf branch 1 (Array of [`RlmToolReceipt`](rlmtoolreceipt.md)): Maximum items: `1000`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "run_id": {
          "title": "Run Id",
          "type": "string"
        },
        "provenance_status": {
          "enum": [
            "recorded",
            "not_recorded"
          ],
          "title": "Provenance Status",
          "type": "string"
        },
        "source_provenance_complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Provenance Complete"
        },
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
        "memory": {
          "anyOf": [
            {
              "$ref": "#/$defs/MemoryReceipt"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "generations": {
          "items": {
            "$ref": "#/$defs/GenerationReceipt"
          },
          "maxItems": 100,
          "title": "Generations",
          "type": "array"
        },
        "sources": {
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "maxItems": 500,
          "title": "Sources",
          "type": "array"
        },
        "private_files": {
          "items": {
            "$ref": "#/$defs/PrivateFileReceipt"
          },
          "maxItems": 10,
          "title": "Private Files",
          "type": "array"
        },
        "native_reads": {
          "items": {
            "$ref": "#/$defs/NativeReadReceipt"
          },
          "maxItems": 1000,
          "title": "Native Reads",
          "type": "array"
        },
        "sql_attempts": {
          "items": {
            "$ref": "#/$defs/SqlAttemptReceipt"
          },
          "maxItems": 1000,
          "title": "Sql Attempts",
          "type": "array"
        },
        "rlm_tools": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/RlmToolReceipt"
              },
              "maxItems": 1000,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Actual recorded RLM function actions. Null means unrecorded; historical traces are never backfilled. A list does not assert that an interrupted generation has a complete trace.",
          "title": "Rlm Tools"
        }
      },
      "required": [
        "run_id",
        "provenance_status"
      ],
      "title": "AnswerAudit",
      "type": "object"
    }
    ```
