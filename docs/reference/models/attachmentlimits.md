<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentLimits

[All wire models](index.md)

Model aliases: `AttachmentLimits`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `max_file_bytes` | `integer` | Yes | Not specified |
| `max_image_bytes` | `integer` | Yes | Not specified |
| `max_selected` | `integer` | Yes | Not specified |
| `max_thread_files` | `integer` | Yes | Not specified |
| `max_thread_bytes` | `integer` | Yes | Not specified |
| `max_model_text_chars` | `integer` | Yes | Not specified |
| `max_model_binary_bytes` | `integer` | Yes | Not specified |
| `extraction_timeout_seconds` | `integer` | Yes | Not specified |
| `ttl_seconds` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "max_file_bytes": {
          "title": "Max File Bytes",
          "type": "integer"
        },
        "max_image_bytes": {
          "title": "Max Image Bytes",
          "type": "integer"
        },
        "max_selected": {
          "title": "Max Selected",
          "type": "integer"
        },
        "max_thread_files": {
          "title": "Max Thread Files",
          "type": "integer"
        },
        "max_thread_bytes": {
          "title": "Max Thread Bytes",
          "type": "integer"
        },
        "max_model_text_chars": {
          "title": "Max Model Text Chars",
          "type": "integer"
        },
        "max_model_binary_bytes": {
          "title": "Max Model Binary Bytes",
          "type": "integer"
        },
        "extraction_timeout_seconds": {
          "title": "Extraction Timeout Seconds",
          "type": "integer"
        },
        "ttl_seconds": {
          "title": "Ttl Seconds",
          "type": "integer"
        }
      },
      "required": [
        "max_file_bytes",
        "max_image_bytes",
        "max_selected",
        "max_thread_files",
        "max_thread_bytes",
        "max_model_text_chars",
        "max_model_binary_bytes",
        "extraction_timeout_seconds",
        "ttl_seconds"
      ],
      "title": "AttachmentLimits",
      "type": "object"
    }
    ```
