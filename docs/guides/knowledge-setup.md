<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Configure your corporate brain

Follow this path for a new installation or organization. It connects deployment prerequisites, visual configuration and a small acceptance exercise. The linked screenshots use controlled example data; they illustrate the screens and do not establish that your provider or deployment is ready.

On a phone, open navigation, choose **Settings**, then use **Settings section** to choose a page. On a larger screen, use the settings navigation. Confirm the selected organization before saving organization-wide changes.

## 1. Prepare the installation

Configure the public/base URL, trusted proxy behavior, identity provider, PostgreSQL datasources, object storage, encryption material and worker resources through the protected deployment configuration. Apply the three migration histories with separate migration authority before starting the updated application. Runtime credentials must not have migration authority.

For a new production installation, use [First start in production](../operations/first-start.md) for the migration, sign-in and verified-subject bootstrap order. For loopback development, use [local deployment](../operations/local-deployment.md), then rehearse [backup and restore](../operations/backup-restore.md). Decide where original documents, dataset artifacts and private chat files persist; configuring only a knowledge index is insufficient. [File persistence and storage](../operations/storage.md) covers local, S3, Azure Blob Storage and Google Cloud Storage profiles and the current bulk-operation boundaries.

## 2. Establish people and access

After signing in to the running installation, obtain the verified canonical subject from `GET /auth/me` and create the first organization administrator through the [audited bootstrap procedure](../operations/first-start.md#4-sign-in-verify-the-subject-then-bootstrap). An identity-provider login alone does not grant product membership. Open **Access** to invite people or assign the smallest useful organization/workspace role. Configure supported corporate group mappings separately from manual grants.

Use **People** and **Organization structure** for positions, departments, teams and managers. These values do not grant permissions. Choose directory visibility explicitly, and let each person manage their own avatar and preferences. The [people guide](people-and-organization.md) covers the complete flow and SDK operations.

## 3. Apply the product identity

Open **Identity & appearance** in the **Organization** settings group. Review product and assistant names, light/dark assets, browser icon and palettes. Check both themes and the preview before saving. Installation branding controls the signed-out experience; private organization overrides apply after authentication.

[![Identity and logo editing with a contextual preview](../assets/screenshots/identity-editor.png)](../assets/screenshots/identity-editor.png)

[![Palette configuration and measured contrast](../assets/screenshots/identity-colors.png)](../assets/screenshots/identity-colors.png)

Follow [identity and appearance](../operations/identity-appearance.md) for image constraints, inheritance, revision conflicts and embedded-host branding. Check mobile navigation and account screens as well as the desktop preview.

## 4. Connect and validate model providers

Open **Providers**, connect an approved endpoint, select the actual protocol and provide credentials when required. Save, then run the offered checks. A model being listed establishes discovery, not successful streaming, tool calling or vision.

[![Provider configuration before its connection and model checks](../assets/screenshots/provider-connection.png)](../assets/screenshots/provider-connection.png)

Start with the model needed for your first bounded scenario. Check its supported settings instead of assuming that all models on the endpoint share capabilities. A changed connection or model configuration invalidates previous validation observations.

## 5. Assign processing models and choose RAG or RLM

Open **Knowledge models**. Configure the document and structured roles needed by your selected workflow. Embeddings require an explicit compatible model, dimensions and space. Organization defaults and workspace overrides have different authority and behavior; a disabled override blocks fallback.

In **Knowledge behavior**, read the current policy, capabilities and bounds. Choose **RAG** for the document retrieval path or **RLM** only after its recorded-view, secure execution and model prerequisites are met. Review both the document and structured policy before saving. Reload and review a revision conflict rather than overwriting another administrator's changes.

[Agents, embeddings and knowledge engines](../concepts/knowledge-runtime.md) explains the choice. [Organization knowledge behavior](../operations/organization-knowledge.md) gives the exact settings, RLM restrictions and typed examples. Keep unsupported capabilities disabled; a mode selector does not qualify a provider.

## 6. Configure the organization's chat agent

In **Agents**, choose a provider/model, allowed knowledge tools and instructions. Validate the agent, then set the organization default. Standard chat resolves that central setting for the current caller. No agent can broaden the caller's memberships or token resource bounds.

Check a reader account as well as an administrator. Verify that the reader can ask about an allowed source and cannot access a source outside its workspace. [Agents and chat](agents.md) covers conversation folders, private files, memory, SSE and audit.

## 7. Import representative knowledge and inspect an answer

Create a recognizable Library destination. Upload a small fictional document and a representative dataset in the actual format you will use, such as XLSX. Inspect processing, extracted sections, schema and immutable source history before asking a question.

[![Reviewing files, intake mode and destination before upload](../assets/screenshots/upload-review.png)](../assets/screenshots/upload-review.png)

Ask a question with an independently known answer. Open **Audit** and verify the cited document part or dataset snapshot, executed SQL where relevant, tool outcomes and recorded policy. Replace the test source through an authorized revision-checked operation and confirm that the older answer still resolves its original evidence.

[![An answer's execution audit and recorded SQL](../assets/screenshots/answer-audit.png)](../assets/screenshots/answer-audit.png)

For RLM, verify actual content-use records and final citations, not just a successful analysis action. For private files, verify owner/conversation isolation and expiry. Obtain explicit approval before publishing a proposed conclusion as organizational knowledge.

## 8. Connect an application and prepare release acceptance

Use a scoped personal token for an SDK integration or a configured OAuth application for delegated access. Test reads and the authorized maintenance operations the application actually needs. Follow the complete [Python](headless-python.md), [TypeScript](headless-typescript.md) or [Java 21+](headless-java.md) guide. The [API reference](../reference/sdk-api.md) maps every canonical operation across languages.

For external assistants, follow [Claude](connect-claude.md), [ChatGPT](connect-chatgpt.md) and [authorized applications](authorized-applications.md). The deployment determines the MCP URL and OAuth callback registration. A hosted client needs network access to that deployment; local configuration alone is not a hosted-client acceptance test.

Before shipping, validate the built artifacts, retained-data migration, permissions, file persistence, worker behavior, real model answers, responsive interface and published documentation for the exact release. Record the remaining provider/client limitations in [qualification](../operations/qualification.md). Passing a source test or viewing a screenshot is one part of that evidence, not the whole deployment result.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
