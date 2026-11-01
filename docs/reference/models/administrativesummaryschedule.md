<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AdministrativeSummarySchedule

[All wire models](index.md)

Model aliases: `AdministrativeSummarySchedule`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `cadence` | `string` | Yes | Not specified |
| `schedule` | [`DigestSchedule`](digestschedule.md) | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### cadence

- Allowed values: `"daily"`, `"weekly"`, `"monthly"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "cadence": {
          "enum": [
            "daily",
            "weekly",
            "monthly"
          ],
          "title": "Cadence",
          "type": "string"
        },
        "schedule": {
          "$ref": "#/$defs/DigestSchedule"
        }
      },
      "required": [
        "cadence"
      ],
      "title": "AdministrativeSummarySchedule",
      "type": "object"
    }
    ```
