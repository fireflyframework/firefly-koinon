<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileReviewView

[All wire models](index.md)

Model aliases: `ExternalFileReviewView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `authorization_digest` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `content_type` | `string` or `null` | Yes | Not specified |
| `mode` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `destination` | [`KnowledgeDestination`](knowledgedestination.md) | Yes | Not specified |
| `received_chunks` | `integer` | Yes | Not specified |
| `total_chunks` | `integer` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `submitted_by` | `string` | Yes | Not specified |
| `credential_id` | `string` | Yes | Not specified |
| `application_id` | `string` or `null` | Yes | Not specified |
| `origin` | `string` | No | `"external_proposal"` |
| `authority` | `string` | No | `"unverified"` |
| `provider` | `null` | No | `null` |
| `model` | `null` | No | `null` |
| `source_id` | `string` or `null` | No | `null` |
| `intake_status` | `string` or `null` | No | `null` |
| `receipt` | [`ExternalFileReceipt`](externalfilereceipt.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### revision

- Minimum: `1`

### authorization_digest

- Pattern: `"^[a-f0-9]{64}$"`

### status

- Allowed values: `"uploading"`, `"preview"`, `"ingesting"`, `"committed"`, `"cancelled"`, `"unresolved"`

### mode

- Allowed values: `"document"`, `"dataset"`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### expires_at

- Format: `"date-time"`

### credential_id

- Minimum length: `1`
- Maximum length: `64`

### application_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### origin

- Exact value: `"external_proposal"`

### authority

- Exact value: `"unverified"`

### source_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "authorization_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Authorization Digest",
          "type": "string"
        },
        "status": {
          "enum": [
            "uploading",
            "preview",
            "ingesting",
            "committed",
            "cancelled",
            "unresolved"
          ],
          "title": "Status",
          "type": "string"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "content_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Content Type"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "destination": {
          "$ref": "#/$defs/KnowledgeDestination"
        },
        "received_chunks": {
          "title": "Received Chunks",
          "type": "integer"
        },
        "total_chunks": {
          "title": "Total Chunks",
          "type": "integer"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "submitted_by": {
          "title": "Submitted By",
          "type": "string"
        },
        "credential_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Credential Id",
          "type": "string"
        },
        "application_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Application Id"
        },
        "origin": {
          "const": "external_proposal",
          "default": "external_proposal",
          "title": "Origin",
          "type": "string"
        },
        "authority": {
          "const": "unverified",
          "default": "unverified",
          "title": "Authority",
          "type": "string"
        },
        "provider": {
          "default": null,
          "title": "Provider",
          "type": "null"
        },
        "model": {
          "default": null,
          "title": "Model",
          "type": "null"
        },
        "source_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Id"
        },
        "intake_status": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Intake Status"
        },
        "receipt": {
          "anyOf": [
            {
              "$ref": "#/$defs/ExternalFileReceipt"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "tenant_id",
        "revision",
        "authorization_digest",
        "status",
        "filename",
        "content_type",
        "mode",
        "size_bytes",
        "sha256",
        "destination",
        "received_chunks",
        "total_chunks",
        "expires_at",
        "submitted_by",
        "credential_id",
        "application_id"
      ],
      "title": "ExternalFileReviewView",
      "type": "object"
    }
    ```
