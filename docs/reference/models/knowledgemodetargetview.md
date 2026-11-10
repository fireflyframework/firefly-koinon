<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeModeTargetView

[All wire models](index.md)

Model aliases: `KnowledgeModeTargetView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `catalog_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `error_code` | `string` or `null` | No | `null` |
| `message` | `string` or `null` | No | `null` |
| `action` | `string` or `null` | No | `null` |
| `index_id` | `string` or `null` | No | `null` |
| `job_id` | `string` or `null` | No | `null` |
| `job_status` | `string` or `null` | No | `null` |
| `index_recovery` | [`KnowledgeModeIndexRecovery`](knowledgemodeindexrecovery.md) or `null` | No | `null` |
| `lease_until` | `string` or `null` | No | `null` |
| `source_version_id` | `string` or `null` | No | `null` |
| `ingestion_extraction_id` | `string` or `null` | No | `null` |
| `view_extraction_id` | `string` or `null` | No | `null` |
| `raw_sha256` | `string` or `null` | No | `null` |
| `raw_bytes` | `integer` or `null` | No | `null` |
| `normalized_sha256` | `string` or `null` | No | `null` |
| `parts` | `integer` or `null` | No | `null` |
| `text_bytes` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"workspace"`, `"document"`, `"curated"`

### status

- Allowed values: `"queued"`, `"prepared"`, `"ready"`, `"waiting"`, `"failed"`, `"excluded"`

### action

- anyOf branch 1 (`string`): Allowed values: `"reprocess_document"`, `"inspect_document_job"`, `"keep_rag"`, `"inspect_source_integrity"`, `"inspect_source_limits"`, `"restart_preparation"`, `"retry_preparation"`, `"configure_models"`, `"inspect_preparation"`, `"inspect_index_job"`, `"reconcile_index"`

### raw_bytes

- anyOf branch 1 (`integer`): Minimum: `0`

### parts

- anyOf branch 1 (`integer`): Minimum: `0`

### text_bytes

- anyOf branch 1 (`integer`): Minimum: `0`


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
        "kind": {
          "enum": [
            "workspace",
            "document",
            "curated"
          ],
          "title": "Kind",
          "type": "string"
        },
        "catalog_id": {
          "title": "Catalog Id",
          "type": "string"
        },
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "queued",
            "prepared",
            "ready",
            "waiting",
            "failed",
            "excluded"
          ],
          "title": "Status",
          "type": "string"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "message": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Message"
        },
        "action": {
          "anyOf": [
            {
              "enum": [
                "reprocess_document",
                "inspect_document_job",
                "keep_rag",
                "inspect_source_integrity",
                "inspect_source_limits",
                "restart_preparation",
                "retry_preparation",
                "configure_models",
                "inspect_preparation",
                "inspect_index_job",
                "reconcile_index"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Action"
        },
        "index_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Index Id"
        },
        "job_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Id"
        },
        "job_status": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Status"
        },
        "index_recovery": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeModeIndexRecovery"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "lease_until": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Lease Until"
        },
        "source_version_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Version Id"
        },
        "ingestion_extraction_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ingestion Extraction Id"
        },
        "view_extraction_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "View Extraction Id"
        },
        "raw_sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Raw Sha256"
        },
        "raw_bytes": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Raw Bytes"
        },
        "normalized_sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Normalized Sha256"
        },
        "parts": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parts"
        },
        "text_bytes": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Text Bytes"
        }
      },
      "required": [
        "id",
        "kind",
        "catalog_id",
        "workspace_id",
        "status"
      ],
      "title": "KnowledgeModeTargetView",
      "type": "object"
    }
    ```
