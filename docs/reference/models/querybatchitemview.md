<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchItemView

[All wire models](index.md)

Model aliases: `QueryBatchItemView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `client_item_id` | `string` | Yes | Not specified |
| `dataset_id` | `string` | Yes | Not specified |
| `question` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `job_id` | `string` | Yes | Not specified |
| `error_code` | `string` or `null` | No | `null` |
| `query_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"queued"`, `"running"`, `"succeeded"`, `"failed"`, `"cancelled"`, `"reconciling"`

### query_id

- anyOf branch 1 (`string`): Format: `"uuid"`


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
        "client_item_id": {
          "title": "Client Item Id",
          "type": "string"
        },
        "dataset_id": {
          "title": "Dataset Id",
          "type": "string"
        },
        "question": {
          "title": "Question",
          "type": "string"
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "reconciling"
          ],
          "title": "Status",
          "type": "string"
        },
        "job_id": {
          "title": "Job Id",
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
        "query_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Query Id"
        }
      },
      "required": [
        "id",
        "client_item_id",
        "dataset_id",
        "question",
        "status",
        "job_id"
      ],
      "title": "QueryBatchItemView",
      "type": "object"
    }
    ```
