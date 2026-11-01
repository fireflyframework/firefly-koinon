<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ObservedCost

[All wire models](index.md)

Model aliases: `ObservedCost`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `amount` | `number` or `string` or `null` | No | `null` |
| `currency` | `string` or `null` | No | `null` |
| `status` | `string` | Yes | Not specified |
| `source` | `string` or `null` | No | `null` |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### amount

- anyOf branch 1 (`number`): Minimum: `0.0`

### currency

- anyOf branch 1 (`string`): Pattern: `"^[A-Z]{3}$"`

### status

- Allowed values: `"observed"`, `"partial"`, `"unavailable"`

### source

- anyOf branch 1 (`string`): Maximum length: `120`

### reason

- anyOf branch 1 (`string`): Maximum length: `80`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "amount": {
          "anyOf": [
            {
              "minimum": 0.0,
              "type": "number"
            },
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Amount"
        },
        "currency": {
          "anyOf": [
            {
              "pattern": "^[A-Z]{3}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Currency"
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
        "source": {
          "anyOf": [
            {
              "maxLength": 120,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source"
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
      "title": "ObservedCost",
      "type": "object"
    }
    ```
