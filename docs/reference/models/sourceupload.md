<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceUpload

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `file` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `project_id` | `string` | Yes | Not specified |
| `parent_id` | `string` | Yes | Not specified |
| `mode` | `"document"` or `"dataset"` | Yes | Not specified |

## Field constraints

### file

- Content encoding: `"binary"`

### mode

- Allowed values: `"document"`, `"dataset"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "type": "object",
      "required": [
        "file",
        "workspace_id",
        "project_id",
        "parent_id",
        "mode"
      ],
      "properties": {
        "file": {
          "type": "string",
          "contentEncoding": "binary"
        },
        "workspace_id": {
          "type": "string"
        },
        "project_id": {
          "type": "string"
        },
        "parent_id": {
          "type": "string"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ]
        }
      }
    }
    ```
