<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeRole

[All wire models](index.md)

Model aliases: `KnowledgeRole`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `domain` | `string` | Yes | Not specified |
| `label` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `purposes` | Array of `string` | Yes | Not specified |
| `supports_current_agent` | `boolean` | Yes | Not specified |
| `compatible_index_required` | `boolean` | Yes | Not specified |
| `assignment` | `string` or `null` | No | `null` |
| `status` | `string` | Yes | Not specified |
| `runtime_qualification` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### domain

- Allowed values: `"documents"`, `"structured"`

### kind

- Allowed values: `"embedding"`, `"generative"`

### assignment

- anyOf branch 1 (`string`): Allowed values: `"tenant"`, `"workspace"`

### status

- Allowed values: `"needs_setup"`, `"assigned"`, `"disabled"`

### runtime_qualification

- Exact value: `"not_run"`


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
        "domain": {
          "enum": [
            "documents",
            "structured"
          ],
          "title": "Domain",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        },
        "kind": {
          "enum": [
            "embedding",
            "generative"
          ],
          "title": "Kind",
          "type": "string"
        },
        "purposes": {
          "items": {
            "type": "string"
          },
          "title": "Purposes",
          "type": "array"
        },
        "supports_current_agent": {
          "title": "Supports Current Agent",
          "type": "boolean"
        },
        "compatible_index_required": {
          "title": "Compatible Index Required",
          "type": "boolean"
        },
        "assignment": {
          "anyOf": [
            {
              "enum": [
                "tenant",
                "workspace"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Assignment"
        },
        "status": {
          "enum": [
            "needs_setup",
            "assigned",
            "disabled"
          ],
          "title": "Status",
          "type": "string"
        },
        "runtime_qualification": {
          "const": "not_run",
          "title": "Runtime Qualification",
          "type": "string"
        }
      },
      "required": [
        "id",
        "domain",
        "label",
        "kind",
        "purposes",
        "supports_current_agent",
        "compatible_index_required",
        "status",
        "runtime_qualification"
      ],
      "title": "KnowledgeRole",
      "type": "object"
    }
    ```
