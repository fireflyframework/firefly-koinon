<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BinaryDownload

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `string`.


## Model constraints

- Content encoding: `"binary"`
- Authenticated HTTP binary response. SDK metadata wrapper includes bytes/blob, Content-Type, ETag, RFC5987 filename and not_modified. Only authorized avatar304 is accepted.

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "description": "Authenticated HTTP binary response. SDK metadata wrapper includes bytes/blob, Content-Type, ETag, RFC5987 filename and not_modified. Only authorized avatar304 is accepted.",
      "type": "string",
      "contentEncoding": "binary"
    }
    ```
