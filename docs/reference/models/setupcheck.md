<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SetupCheck

[All wire models](index.md)

Model aliases: `SetupCheck`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `model_id` | `string` or `null` | No | `null` |
| `capability` | `string` or `null` | No | `null` |
| `supported` | `boolean` or `null` | No | `null` |
| `verified` | `boolean` or `null` | No | `null` |
| `options_key` | `string` or `null` | No | `null` |
| `observed_at` | `string` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `message` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### capability

- anyOf branch 1 (`string`): Allowed values: `"chat"`, `"streaming"`, `"tools"`, `"image_input"`, `"audio_input"`

### status

- Allowed values: `"passed"`, `"failed"`, `"needs_setup"`, `"unverified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Id"
        },
        "capability": {
          "anyOf": [
            {
              "enum": [
                "chat",
                "streaming",
                "tools",
                "image_input",
                "audio_input"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Capability"
        },
        "supported": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Supported"
        },
        "verified": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Verified"
        },
        "options_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Options Key"
        },
        "observed_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "passed",
            "failed",
            "needs_setup",
            "unverified"
          ],
          "title": "Status",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "id",
        "status",
        "message"
      ],
      "title": "SetupCheck",
      "type": "object"
    }
    ```
