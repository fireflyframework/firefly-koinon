<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TableReplacement

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `file` | `string` | Yes | Not specified |

## Field constraints

### file

- Content encoding: `"binary"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "type": "object",
      "required": [
        "file"
      ],
      "properties": {
        "file": {
          "type": "string",
          "contentEncoding": "binary"
        }
      }
    }
    ```
