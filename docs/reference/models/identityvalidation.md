<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityValidation

[All wire models](index.md)

Model aliases: `IdentityValidation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `candidate_revision` | `integer` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `checks` | Array of [`IdentityCheck`](identitycheck.md) | Yes | Not specified |
| `status` | `string` | No | `"pending"` |
| `authorization_url` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### expires_at

- Format: `"date-time"`

### status

- Allowed values: `"pending"`, `"verified"`, `"failed"`, `"consumed"`


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
        "candidate_revision": {
          "title": "Candidate Revision",
          "type": "integer"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "checks": {
          "items": {
            "$ref": "#/$defs/IdentityCheck"
          },
          "title": "Checks",
          "type": "array"
        },
        "status": {
          "default": "pending",
          "enum": [
            "pending",
            "verified",
            "failed",
            "consumed"
          ],
          "title": "Status",
          "type": "string"
        },
        "authorization_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Authorization Url"
        }
      },
      "required": [
        "id",
        "candidate_revision",
        "expires_at",
        "checks"
      ],
      "title": "IdentityValidation",
      "type": "object"
    }
    ```
