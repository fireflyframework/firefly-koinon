<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BrandingPalette

[All wire models](index.md)

Model aliases: `BrandingPalette`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `surface` | `string` | Yes | Not specified |
| `canvas` | `string` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `muted` | `string` | Yes | Not specified |
| `line` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `action_text` | `string` | Yes | Not specified |
| `accent` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### surface

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### canvas

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### text

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### muted

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### line

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### action

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### action_text

- Pattern: `"^#[0-9A-Fa-f]{6}$"`

### accent

- Pattern: `"^#[0-9A-Fa-f]{6}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "surface": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Surface",
          "type": "string"
        },
        "canvas": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Canvas",
          "type": "string"
        },
        "text": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Text",
          "type": "string"
        },
        "muted": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Muted",
          "type": "string"
        },
        "line": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Line",
          "type": "string"
        },
        "action": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Action",
          "type": "string"
        },
        "action_text": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Action Text",
          "type": "string"
        },
        "accent": {
          "pattern": "^#[0-9A-Fa-f]{6}$",
          "title": "Accent",
          "type": "string"
        }
      },
      "required": [
        "surface",
        "canvas",
        "text",
        "muted",
        "line",
        "action",
        "action_text",
        "accent"
      ],
      "title": "BrandingPalette",
      "type": "object"
    }
    ```
