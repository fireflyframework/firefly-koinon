<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EvidenceManifest

[All wire models](index.md)

Model aliases: `EvidenceManifest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `revision` | `string` | Yes | Not specified |
| `sources` | Array of [`SourceReference`](sourcereference.md) | No | `[]` |
| `complete` | `boolean` | No | `false` |
| `omissions` | Array of `string` | No | `[]` |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### sources

- Maximum items: `500`

### omissions

- Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "sources": {
          "default": [],
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "maxItems": 500,
          "title": "Sources",
          "type": "array"
        },
        "complete": {
          "default": false,
          "title": "Complete",
          "type": "boolean"
        },
        "omissions": {
          "default": [],
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Omissions",
          "type": "array"
        }
      },
      "required": [
        "revision"
      ],
      "title": "EvidenceManifest",
      "type": "object"
    }
    ```
