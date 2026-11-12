<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingPresentation

[All wire models](index.md)

Model aliases: `SourceMappingPresentation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `source_root` | [`SourceRootPresentation`](sourcerootpresentation.md) or `null` | No | `null` |
| `destination` | [`SourceDestinationPresentation`](sourcedestinationpresentation.md) or `null` | No | `null` |
| `unavailable_reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### unavailable_reason

- anyOf branch 1 (`string`): Allowed values: `"access_denied"`, `"reconnect_required"`, `"unavailable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "source_root": {
          "anyOf": [
            {
              "$ref": "#/$defs/SourceRootPresentation"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "destination": {
          "anyOf": [
            {
              "$ref": "#/$defs/SourceDestinationPresentation"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unavailable_reason": {
          "anyOf": [
            {
              "enum": [
                "access_denied",
                "reconnect_required",
                "unavailable"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Unavailable Reason"
        }
      },
      "title": "SourceMappingPresentation",
      "type": "object"
    }
    ```
