<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BulkFileUpload

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `string`.


## Model constraints

- Content encoding: `"binary"`
- Exact admitted original bytes, 1..134217728 bytes; raw application/octet-stream, never JSON/base64/multipart.

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "type": "string",
      "contentEncoding": "binary",
      "description": "Exact admitted original bytes, 1..134217728 bytes; raw application/octet-stream, never JSON/base64/multipart."
    }
    ```
