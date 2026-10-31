<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpReviewSupport

[All wire models](index.md)

Model aliases: `McpReviewSupport`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `supported` | `boolean` | Yes | Not specified |
| `mechanism` | `string` | No | `"mcp_apps"` |
| `resource_uri` | `string` | No | `"ui://koinon/knowledge-review"` |
| `mime_type` | `string` | No | `"text/html;profile=mcp-app"` |
| `external_redirect` | `boolean` | No | `false` |
| `client_support` | `string` | No | `"not_observed"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### mechanism

- Exact value: `"mcp_apps"`

### resource_uri

- Exact value: `"ui://koinon/knowledge-review"`

### mime_type

- Exact value: `"text/html;profile=mcp-app"`

### external_redirect

- Exact value: `false`

### client_support

- Exact value: `"not_observed"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "supported": {
          "title": "Supported",
          "type": "boolean"
        },
        "mechanism": {
          "const": "mcp_apps",
          "default": "mcp_apps",
          "title": "Mechanism",
          "type": "string"
        },
        "resource_uri": {
          "const": "ui://koinon/knowledge-review",
          "default": "ui://koinon/knowledge-review",
          "title": "Resource Uri",
          "type": "string"
        },
        "mime_type": {
          "const": "text/html;profile=mcp-app",
          "default": "text/html;profile=mcp-app",
          "title": "Mime Type",
          "type": "string"
        },
        "external_redirect": {
          "const": false,
          "default": false,
          "title": "External Redirect",
          "type": "boolean"
        },
        "client_support": {
          "const": "not_observed",
          "default": "not_observed",
          "title": "Client Support",
          "type": "string"
        }
      },
      "required": [
        "supported"
      ],
      "title": "McpReviewSupport",
      "type": "object"
    }
    ```
