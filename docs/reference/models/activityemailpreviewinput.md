<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ActivityEmailPreviewInput

[All wire models](index.md)

Model aliases: `ActivityEmailPreviewInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `preferences` | [`NotificationPreferencesInput`](notificationpreferencesinput.md) | Yes | Not specified |
| `window` | [`ActivityWindow`](activitywindow.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### tenant_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "preferences": {
          "$ref": "#/$defs/NotificationPreferencesInput"
        },
        "window": {
          "$ref": "#/$defs/ActivityWindow"
        }
      },
      "required": [
        "tenant_id",
        "preferences",
        "window"
      ],
      "title": "ActivityEmailPreviewInput",
      "type": "object"
    }
    ```
