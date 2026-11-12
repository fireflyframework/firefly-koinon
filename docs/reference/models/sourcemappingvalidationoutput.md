<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingValidationOutput

[All wire models](index.md)

Model aliases: `SourceMappingValidationOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `validation_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `state` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `continuation_token` | `string` or `null` | No | `null` |
| `enumeration_complete` | `boolean` | Yes | Not specified |
| `observed_count` | `integer` or `null` | No | `null` |
| `total` | `integer` or `null` | No | `null` |
| `manifest_sha256` | `string` or `null` | No | `null` |
| `reason_code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### validation_id

- Format: `"uuid"`

### state

- Allowed values: `"scanning"`, `"verifying"`, `"checking_changes"`, `"complete"`, `"blocked"`, `"stale"`, `"cleaning"`, `"abandoned"`, `"expired"`

### expires_at

- Format: `"date-time"`

### manifest_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### reason_code

- anyOf branch 1 (`string`): Allowed values: `"SOURCE_NAME_COLLISION"`, `"SOURCE_DESTINATION_COLLISION"`, `"SOURCE_LOCAL_EDIT"`, `"SOURCE_CHANGED"`, `"SOURCE_AUTHORITY_CHANGED"`, `"SOURCE_SCAN_LIMIT_EXCEEDED"`, `"SOURCE_VALIDATION_CAPACITY"`, `"SOURCE_UNAVAILABLE"`, `"SOURCE_VALIDATION_REFRESH_REQUIRED"`, `"SOURCE_INVALID_SELECTION"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "validation_id": {
          "format": "uuid",
          "title": "Validation Id",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "state": {
          "enum": [
            "scanning",
            "verifying",
            "checking_changes",
            "complete",
            "blocked",
            "stale",
            "cleaning",
            "abandoned",
            "expired"
          ],
          "title": "State",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "continuation_token": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Continuation Token"
        },
        "enumeration_complete": {
          "title": "Enumeration Complete",
          "type": "boolean"
        },
        "observed_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed Count"
        },
        "total": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Total"
        },
        "manifest_sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Manifest Sha256"
        },
        "reason_code": {
          "anyOf": [
            {
              "enum": [
                "SOURCE_NAME_COLLISION",
                "SOURCE_DESTINATION_COLLISION",
                "SOURCE_LOCAL_EDIT",
                "SOURCE_CHANGED",
                "SOURCE_AUTHORITY_CHANGED",
                "SOURCE_SCAN_LIMIT_EXCEEDED",
                "SOURCE_VALIDATION_CAPACITY",
                "SOURCE_UNAVAILABLE",
                "SOURCE_VALIDATION_REFRESH_REQUIRED",
                "SOURCE_INVALID_SELECTION"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason Code"
        }
      },
      "required": [
        "validation_id",
        "revision",
        "state",
        "expires_at",
        "enumeration_complete"
      ],
      "title": "SourceMappingValidationOutput",
      "type": "object"
    }
    ```
