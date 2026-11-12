<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceConnectionOutput

[All wire models](index.md)

Model aliases: `SourceConnectionOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `provider` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `account` | [`SourceAccountOutput`](sourceaccountoutput.md) or `null` | Yes | Not specified |
| `display_name` | `string` or `null` | No | `null` |
| `display_address` | `string` or `null` | No | `null` |
| `display_address_verified` | `boolean` | No | `false` |
| `synchronization_available` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Field constraints

### provider

- Allowed values: `"sharepoint"`, `"onedrive"`, `"google_drive"`

### status

- Allowed values: `"pending"`, `"connected"`, `"reconnect_required"`, `"disconnected"`

### display_name

- anyOf branch 1 (`string`): Maximum length: `255`

### display_address

- anyOf branch 1 (`string`): Maximum length: `320`


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
        "provider": {
          "enum": [
            "sharepoint",
            "onedrive",
            "google_drive"
          ],
          "title": "Provider",
          "type": "string"
        },
        "status": {
          "enum": [
            "pending",
            "connected",
            "reconnect_required",
            "disconnected"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "account": {
          "anyOf": [
            {
              "$ref": "#/$defs/SourceAccountOutput"
            },
            {
              "type": "null"
            }
          ]
        },
        "display_name": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Display Name"
        },
        "display_address": {
          "anyOf": [
            {
              "maxLength": 320,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Display Address"
        },
        "display_address_verified": {
          "default": false,
          "title": "Display Address Verified",
          "type": "boolean"
        },
        "synchronization_available": {
          "default": false,
          "title": "Synchronization Available",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "provider",
        "status",
        "revision",
        "account"
      ],
      "title": "SourceConnectionOutput",
      "type": "object"
    }
    ```
