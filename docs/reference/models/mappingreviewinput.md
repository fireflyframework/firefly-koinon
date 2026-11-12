<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MappingReviewInput

[All wire models](index.md)

Model aliases: `MappingReviewInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `connection_id` | `string` | Yes | Not specified |
| `drive_id` | `string` | Yes | Not specified |
| `root_id` | `string` | Yes | Not specified |
| `destination` | [`BulkDestination`](bulkdestination.md) | Yes | Not specified |
| `recursive` | `boolean` | Yes | Not specified |
| `removal_policy` | `string` | Yes | Not specified |
| `schema_version` | `integer` | No | `1` |
| `mode` | `string` | No | `"document"` |
| `hierarchy` | `string` | No | `"preserve"` |
| `excluded_ids` | Array of `string` | No | Not specified |
| `formats` | Array of `string` | No | Not specified |
| `schedule` | [`ManualSchedule`](manualschedule.md) or [`IntervalSchedule`](intervalschedule.md) or [`CalendarSchedule`](calendarschedule.md) | No | Not specified |
| `replacement_resolutions` | Array of [`ReplacementResolutionInput`](replacementresolutioninput.md) | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### connection_id

- Minimum length: `1`
- Maximum length: `64`

### drive_id

- Minimum length: `1`
- Maximum length: `1024`

### root_id

- Minimum length: `1`
- Maximum length: `1024`

### removal_policy

- Allowed values: `"retire"`, `"pause_for_review"`

### schema_version

- Exact value: `1`

### mode

- Allowed values: `"document"`, `"dataset"`

### hierarchy

- Allowed values: `"preserve"`, `"flatten"`

### excluded_ids

- Maximum items: `1000`

### formats

- Minimum items: `1`
- Maximum items: `100`

### schedule

- Discriminator field: `kind`
- For `"calendar"`: [`CalendarSchedule`](calendarschedule.md)
- For `"interval"`: [`IntervalSchedule`](intervalschedule.md)
- For `"manual"`: [`ManualSchedule`](manualschedule.md)

### replacement_resolutions

- Maximum items: `16`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "connection_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Connection Id",
          "type": "string"
        },
        "drive_id": {
          "maxLength": 1024,
          "minLength": 1,
          "title": "Drive Id",
          "type": "string"
        },
        "root_id": {
          "maxLength": 1024,
          "minLength": 1,
          "title": "Root Id",
          "type": "string"
        },
        "destination": {
          "$ref": "#/$defs/BulkDestination"
        },
        "recursive": {
          "title": "Recursive",
          "type": "boolean"
        },
        "removal_policy": {
          "enum": [
            "retire",
            "pause_for_review"
          ],
          "title": "Removal Policy",
          "type": "string"
        },
        "schema_version": {
          "const": 1,
          "default": 1,
          "title": "Schema Version",
          "type": "integer"
        },
        "mode": {
          "default": "document",
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "hierarchy": {
          "default": "preserve",
          "enum": [
            "preserve",
            "flatten"
          ],
          "title": "Hierarchy",
          "type": "string"
        },
        "excluded_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 1000,
          "title": "Excluded Ids",
          "type": "array"
        },
        "formats": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "minItems": 1,
          "title": "Formats",
          "type": "array"
        },
        "schedule": {
          "discriminator": {
            "mapping": {
              "calendar": "#/$defs/CalendarSchedule",
              "interval": "#/$defs/IntervalSchedule",
              "manual": "#/$defs/ManualSchedule"
            },
            "propertyName": "kind"
          },
          "oneOf": [
            {
              "$ref": "#/$defs/ManualSchedule"
            },
            {
              "$ref": "#/$defs/IntervalSchedule"
            },
            {
              "$ref": "#/$defs/CalendarSchedule"
            }
          ],
          "title": "Schedule"
        },
        "replacement_resolutions": {
          "items": {
            "$ref": "#/$defs/ReplacementResolutionInput"
          },
          "maxItems": 16,
          "title": "Replacement Resolutions",
          "type": "array"
        }
      },
      "required": [
        "connection_id",
        "drive_id",
        "root_id",
        "destination",
        "recursive",
        "removal_policy"
      ],
      "title": "MappingReviewInput",
      "type": "object"
    }
    ```
