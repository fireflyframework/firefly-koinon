<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Administration

Configure how your organization uses koinon: who can access it, how knowledge is processed and which applications may connect. Organization settings and protected installation configuration have different owners.

## Start with the task

| What you need to do | Follow this path | Result to check |
| --- | --- | --- |
| Install the product and establish the first administrator | [First start in production](../operations/first-start.md) | The verified account has the intended organization membership; API and worker roles use the migrated stores. |
| Configure an existing organization for its first useful answer | [Guided configuration](knowledge-setup.md) | A representative source is processed and an authorized user receives a source-backed answer. |
| Find a particular administration control | [Administration guide](administration.md#find-a-setting) | The correct page, organization and authority are identified before a change. |
| Choose models and document RAG or RLM behavior | [Knowledge behavior](../operations/organization-knowledge.md) | Current model assignments, supported capabilities and saved policy agree. |
| Configure original files and durable processing | [Storage providers](../operations/storage-configuration.md), then [durable staging](../operations/durable-bulk.md) | Final objects and staged originals survive process replacement; the relevant consumers are enabled. |
| Diagnose an unavailable service or index | [Platform health](../operations/platform-health.md) | The observation, coverage and next action are understood without treating unknown as healthy. |

Open Settings from the avatar menu in the intended installation. An account with one authorized organization enters that organization without a selector. Only accounts with several authorized organizations need to choose one using the organization selector. The browser administration area requires organization administrator access. Deployment operators use protected installation configuration for infrastructure; scoped API permissions do not automatically open browser administration. See the [role boundaries](administration.md#people-and-access) before assigning authority.

## Set up an organization

Follow [guided configuration](knowledge-setup.md) for the setup sequence, or use the [administration guide](administration.md) to find a particular setting. [Identity and appearance](../operations/identity-appearance.md) covers the installation's name, logos and colors.

## Manage people and connected applications

[People and organization](people-and-organization.md) explains the directory, organization structure and access controls. Use [Authorized applications](authorized-applications.md) to review a connection. [Register applications](register-applications.md) covers the deployment's OAuth configuration.

A personal API token and an authorized application have different lifecycles. The [profile and API token guide](../operations/profiles-and-tokens.md) describes personal credentials and their permission bounds.

[Corporate profile synchronization](corporate-profile-sync.md) explains organization names, photos and positions, verified identity bindings, provider requirements and refresh status. Personal preferences and access roles retain their separate ownership.

## Choose knowledge behavior

Use [organization knowledge behavior](../operations/organization-knowledge.md) for RAG, RLM and retrieval settings. [Agents, embeddings and knowledge engines](../concepts/knowledge-runtime.md) explains how these choices fit together.

## Configure infrastructure

An operator manages databases, storage, encryption and deployment observations. Start with [Operations](../operations/README.md) and [file storage](../operations/storage.md). Organization model settings do not change a storage bucket or database binding. Final document, structured and private-file profiles are separate from durable bulk staging; configure both the needed stores and the workers that consume them.

## Check a change before extending it

Save the smallest useful configuration, reload it and run the intended operation with representative example data. Repeat the read with an end-user account and a source outside that account's scope. Inspect processing state, source versions and answer audit rather than relying only on a success message in the form.

The [first-run acceptance exercise](knowledge-setup.md#7-import-representative-knowledge-and-inspect-an-answer) gives a repeatable sequence. Keep its outcomes with the deployment's change record. Provider readiness, a completed import and a published answer are different observations, and none replaces a tested backup and restore.
