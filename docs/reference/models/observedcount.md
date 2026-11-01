<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ObservedCount

[All wire models](index.md)

Model aliases: `ObservedCount`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `value` | `integer` or `null` | No | `null` |
| `status` | `string` | Yes | Not specified |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### value

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### status

- Allowed values: `"observed"`, `"partial"`, `"unavailable"`

### reason

- anyOf branch 1 (`string`): Maximum length: `80`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "value": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Value"
        },
        "status": {
          "enum": [
            "observed",
            "partial",
            "unavailable"
          ],
          "title": "Status",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "maxLength": 80,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        }
      },
      "required": [
        "status"
      ],
      "title": "ObservedCount",
      "type": "object"
    }
    ```
