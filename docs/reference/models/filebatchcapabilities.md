<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FileBatchCapabilities

[All wire models](index.md)

Model aliases: `FileBatchCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `configured` | `boolean` | Yes | Not specified |
| `modes` | Array of `string` | Yes | Not specified |
| `processing_policy` | `string` | No | `"extract_only_v1"` |
| `staging_backend` | `string` | No | `"private_local_posix"` |
| `staging_topology` | `string` | No | `"single_host_shared_durable_posix"` |
| `writer_fence` | `string` | No | `"primary_database_generation_lease"` |
| `worker` | `string` | No | `"external_native_worker"` |
| `automatic_unknown_replay` | `boolean` | No | `false` |
| `max_files` | `integer` | Yes | Not specified |
| `max_file_bytes` | `integer` | Yes | Not specified |
| `max_batch_bytes` | `integer` | Yes | Not specified |
| `max_active_batches_per_subject` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### modes

- Each item: Allowed values: `"document"`, `"dataset"`

### processing_policy

- Exact value: `"extract_only_v1"`

### staging_backend

- Allowed values: `"private_local_posix"`, `"private_azure_blob"`, `"private_gcs_object"`

### staging_topology

- Allowed values: `"single_host_shared_durable_posix"`, `"shared_private_object_store"`

### writer_fence

- Exact value: `"primary_database_generation_lease"`

### worker

- Exact value: `"external_native_worker"`

### automatic_unknown_replay

- Exact value: `false`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "modes": {
          "items": {
            "enum": [
              "document",
              "dataset"
            ],
            "type": "string"
          },
          "title": "Modes",
          "type": "array"
        },
        "processing_policy": {
          "const": "extract_only_v1",
          "default": "extract_only_v1",
          "title": "Processing Policy",
          "type": "string"
        },
        "staging_backend": {
          "default": "private_local_posix",
          "enum": [
            "private_local_posix",
            "private_azure_blob",
            "private_gcs_object"
          ],
          "title": "Staging Backend",
          "type": "string"
        },
        "staging_topology": {
          "default": "single_host_shared_durable_posix",
          "enum": [
            "single_host_shared_durable_posix",
            "shared_private_object_store"
          ],
          "title": "Staging Topology",
          "type": "string"
        },
        "writer_fence": {
          "const": "primary_database_generation_lease",
          "default": "primary_database_generation_lease",
          "title": "Writer Fence",
          "type": "string"
        },
        "worker": {
          "const": "external_native_worker",
          "default": "external_native_worker",
          "title": "Worker",
          "type": "string"
        },
        "automatic_unknown_replay": {
          "const": false,
          "default": false,
          "title": "Automatic Unknown Replay",
          "type": "boolean"
        },
        "max_files": {
          "title": "Max Files",
          "type": "integer"
        },
        "max_file_bytes": {
          "title": "Max File Bytes",
          "type": "integer"
        },
        "max_batch_bytes": {
          "title": "Max Batch Bytes",
          "type": "integer"
        },
        "max_active_batches_per_subject": {
          "title": "Max Active Batches Per Subject",
          "type": "integer"
        }
      },
      "required": [
        "configured",
        "modes",
        "max_files",
        "max_file_bytes",
        "max_batch_bytes",
        "max_active_batches_per_subject"
      ],
      "title": "FileBatchCapabilities",
      "type": "object"
    }
    ```
