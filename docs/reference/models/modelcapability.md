<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ModelCapability

[All wire models](index.md)

Model aliases: `ModelCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `image_input` | [`CapabilityState`](capabilitystate.md) | No | Not specified |
| `audio_input` | [`CapabilityState`](capabilitystate.md) | No | Not specified |
| `option_fields` | Array of `string` | No | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `chat` | [`CapabilityState`](capabilitystate.md) | Yes | Not specified |
| `streaming` | [`CapabilityState`](capabilitystate.md) | Yes | Not specified |
| `tools` | [`CapabilityState`](capabilitystate.md) | Yes | Not specified |
| `observed_tools` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "image_input": {
          "$ref": "#/$defs/CapabilityState"
        },
        "audio_input": {
          "$ref": "#/$defs/CapabilityState"
        },
        "option_fields": {
          "items": {
            "type": "string"
          },
          "title": "Option Fields",
          "type": "array"
        },
        "model_id": {
          "title": "Model Id",
          "type": "string"
        },
        "chat": {
          "$ref": "#/$defs/CapabilityState"
        },
        "streaming": {
          "$ref": "#/$defs/CapabilityState"
        },
        "tools": {
          "$ref": "#/$defs/CapabilityState"
        },
        "observed_tools": {
          "items": {
            "type": "string"
          },
          "title": "Observed Tools",
          "type": "array"
        }
      },
      "required": [
        "model_id",
        "chat",
        "streaming",
        "tools"
      ],
      "title": "ModelCapability",
      "type": "object"
    }
    ```
