<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Administration

Configure how your organization uses koinon: who can access it, how knowledge is processed and which applications may connect. Organization settings and protected installation configuration have different owners.

## Set up an organization

Follow [guided configuration](knowledge-setup.md) for the setup sequence, or use the [administration guide](administration.md) to find a particular setting. [Identity and appearance](../operations/identity-appearance.md) covers the installation's name, logos and colors.

## Manage people and connected applications

[People and organization](people-and-organization.md) explains the directory, organization structure and access controls. Use [Authorized applications](authorized-applications.md) to review a connection. [Register applications](register-applications.md) covers the deployment's OAuth configuration.

A personal API token and an authorized application have different lifecycles. The [profile and API token guide](../operations/profiles-and-tokens.md) describes personal credentials and their permission bounds.

## Choose knowledge behavior

Use [organization knowledge behavior](../operations/organization-knowledge.md) for RAG, RLM and retrieval settings. [Agents, embeddings and knowledge engines](../concepts/knowledge-runtime.md) explains how these choices fit together.

## Configure infrastructure

An operator manages databases, storage, encryption and deployment observations. Start with [Operations](../operations/README.md) and [file storage](../operations/storage.md). Organization model settings do not change a storage bucket or database binding.
