<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Integrate koinon

Use koinon's authorized API from your product, connect an AI client, or embed selected interface components. Each path uses the same knowledge and permission boundaries. You do not need to deploy the management frontend to use the headless API.

## Choose your SDK

Start with [headless integration](headless.md) for authentication and the shared API boundary. Choose a language for installation, typed examples and complete workflows.

=== "Python"

    The [Python SDK guide](headless-python.md) covers an asynchronous client without the backend or Angular package. Continue with [knowledge](python-knowledge.md), [conversations](python-conversations.md) or [administration](python-administration.md).

=== "TypeScript"

    The [TypeScript SDK guide](headless-typescript.md) covers a client independent of Angular. Continue with [knowledge](typescript-knowledge.md), [conversations](typescript-conversations.md) or [administration](typescript-administration.md).

=== "Java"

    The [Java SDK guide](headless-java.md) covers Java 21 and later. Continue with [knowledge](java-knowledge.md), [conversations](java-conversations.md) or [administration and operations](java-operations.md).

Use [API permissions and writes](api-permissions.md) to select access for your use case. The [API and SDK reference](../reference/sdk-api.md) lists the methods and schemas; the language guides explain how to put them together.

## Connect Claude or ChatGPT

Follow the guide for [Claude](connect-claude.md) or [ChatGPT](connect-chatgpt.md). [In-chat knowledge management](mcp-knowledge-management.md) explains the review flow. The [desktop MCP extension](../integrations/desktop.md) and [integration privacy guide](../integrations/privacy.md) describe local setup and data flow.

## Embed the interface

The [embedding guide](embedding.md) covers Angular components and custom elements. The host supplies its authentication and the connection to the backend; embedding a component does not grant access.

## Understand the architecture

Read [system architecture](../concepts/architecture.md) and [MCP architecture](../architecture/mcp.md) before changing a deployment boundary. Check the [26.10.2 release notes](../releases/26.10.2.md) for package versions and integration requirements.
