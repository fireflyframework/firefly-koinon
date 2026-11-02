<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Follow a complete workflow

Choose the work you need to complete, then follow its steps through the resulting evidence. Your current organization, workspace roles and credential limits determine the actions available. A role name in this guide does not grant access or make every Settings page available.

| Your task | Start with | Finish by checking |
| --- | --- | --- |
| Read knowledge or ask a dataset question | [Reader and analyst](#read-knowledge-and-inspect-an-answer) | Authorized sources, recorded values and the answer's audit. |
| Import, update or curate knowledge | [Knowledge editor](#import-and-maintain-knowledge) | Processing, current availability and retained original versions. |
| Configure people, models and communications | [Organization administrator](#administer-an-organization) | Saved configuration and the operation it enables, using an end-user account too. |
| Install or change protected infrastructure | [Deployment operator](#operate-the-installation) | Migrations, grants, storage, workers and a representative functional exercise. |
| Connect an application or external agent | [Integration owner](#connect-an-application) | Its own authenticated read, permitted mutation and revocation checks. |

## Read knowledge and inspect an answer

1. Sign in to the intended installation. Open **Library** and choose a space you can access. Projects and folders organize that space and currently inherit its permissions; a project name does not establish a separate access policy. Private chat projects have a different purpose. Start with [Library](library.md).
2. Open a document or dataset and inspect its availability. A listed resource can still be processing, unavailable or awaiting an index. For a dataset, inspect the registered tables and schema before asking about a column. A filename is not its SQL table name.
3. Open **Chat**, choose the intended knowledge scope and ask a bounded question. For a first check, use the [fictional acceptance sources](knowledge-setup.md#complete-the-first-acceptance-exercise), whose answers you know independently. A dataset question also needs current query authority.
4. Open **Audit** on the completed reply. Inspect the selected document passage or dataset snapshot, tool outcomes and executed SQL where relevant. Follow the citation to its recorded source. A successful stream or plausible sentence is not enough; [Agents and chat](agents.md) explains the output evidence.
5. Ask a question that the sources cannot answer. Expect an insufficient-evidence response rather than a general-knowledge substitute. If a stream disconnects, reconnect to the retained operation instead of starting another generation merely to recover its display.
6. Use [versions and lineage](lineage.md) to distinguish the source used by an older answer from today's version. If you need an export or authenticated share, follow the separate [review and confirmation workflow](exports-sharing.md). A share grants no access to its sources, and private-derived answers have additional restrictions.

Keep personal conversation memory and private attachments separate from shared knowledge. Enabling memory for your chat project does not share another conversation or its files. Read [conversation memory](conversation-memory.md) before approving remembered context in a share or publication.

## Import and maintain knowledge

1. Confirm the destination space, project, folder and current write authority. Choose **document** for passage retrieval or **dataset** for table processing. Review [formats and effective limits](intake-formats.md) before selecting files.
2. Use **Add files**, inspect the intake review and submit once. For durable intake, retain the batch identity and its current state. Acceptance of an upload or batch does not mean processing or indexing has finished.
3. Inspect the resource's processing and availability. If the original was stored but its outcome could not be confirmed, open **Retained uploads** and review that same batch. Signing in or reopening the panel does not submit it again. Follow [bulk intake](bulk-intake.md) and [same-original recovery](../operations/durable-bulk.md) before deciding on an offered action.
4. Verify the original version, extracted parts or tables, and an independently known answer. Test a reader outside the source's space as well: the excluded source must not appear in their results.
5. Make a supported metadata edit, move, archive or versioned replacement using the current revision. Reload after a conflict and review the new state. Protected installation roots cannot be moved or archived. A folder move does not grant a new person access. See [Library maintenance](library.md#maintain-and-inspect) and [source history](lineage.md).
6. After replacing content, ask again. Check that the new answer uses the replacement while the older answer retains its immutable evidence. Preserve failed or partial intake records; an uncertain original is not a reason to upload it again.
7. To curate one completed assistant reply, choose **Save as knowledge**. Edit the title and body, select a permitted destination and request **Review proposal**. Inspect the server's before/after content and evidence, then make the separate confirmation. **Draft** is the default. Publishing requires its own explicit decision, and remembered context requires the separate unchecked consent. [The curation walkthrough](agents.md#save-a-reviewed-answer-as-knowledge) covers conflicts and pending outcomes.

![Retained uploads with an explicitly selected batch](../assets/screenshots/retained-uploads-1440.png)

This is controlled example data from the [recorded screenshot provenance](../assets/screenshots/retained-uploads.provenance.json). It illustrates the workflow, not a live deployment's recovery result.

## Administer an organization

1. Confirm current organization-wide administrator membership. Open your avatar menu, **Settings**, then the intended organization. A workspace administrator does not automatically receive organization-wide Settings access. Use [the setting map](administration.md#find-a-setting) when locating a control.
2. Review **Access**, people and identity separately. Names, departments and email addresses do not grant membership. Use the supported invitation or membership workflow; do not change an identity-provider subject to repair access. [People and organization](people-and-organization.md) explains these boundaries.
3. For a new organization, follow [guided configuration](knowledge-setup.md). For an existing one, use [the configuration lifecycle](configuration-lifecycle.md): capture the current provider, role assignments and active targets before changing them.
4. Verify the organization's chat default and a small source-backed answer. Creating an agent alone does not select it for everyone. Check a permitted reader and a denied source, then inspect source and execution evidence.
5. Open **Communications** to review the operator-verified sender, permitted channels, administrator schedules and delivery history. Before expecting email, establish recipient eligibility. An administrator can use an [operator-approved delivery contact](../reference/operator-delivery-contacts.md) without enabling directory synchronization; invitations and ordinary recipient lanes keep their own directory requirements. A welcome-only contact is not recurring-summary authorization.
6. Preview the actual HTML and plain-text email and review the next scheduled time. Saving a policy or previewing a message does not send it or establish delivery. Record provider acceptance and confirmed mailbox arrival separately. See [communications](../operations/communications.md).
7. Use **Platform health**, processing outcomes and audit to investigate missing prerequisites. Unknown or expired observations are not successful checks. Recheck authority after a role change and verify that a revoked application can no longer read the affected content.

## Operate the installation

1. Complete [first start](../operations/first-start.md) with the reviewed database roles, migrations, encryption keys, identity configuration and public origin. A successful external sign-in does not by itself create product membership.
2. Verify persistent final storage and independent bulk staging, then start the appropriate [worker role and consumers](../operations/workers.md). API readiness alone does not consume queued work.
3. Establish the first administrators through the native audited initialization workflow. For ongoing administrator email, follow [operator delivery contacts](../reference/operator-delivery-contacts.md) with a separate approved operator role. This is not a way to create users or grant membership.
4. Hand organization configuration to its administrator and complete the document/dataset acceptance exercise together. Record the release, original identities, current permissions, active indexes and observed outcomes.
5. Before upgrading, test the released migrations and scoped grants against an isolated restored copy. Preserve previous image and configuration references, and use [backup and restore](../operations/backup-restore.md). A code rollback requires compatibility with the resulting schema; it is not permission to downgrade retained data.

## Connect an application

Start with the complete [Python](headless-python.md), [TypeScript](headless-typescript.md) or [Java 21+](headless-java.md) walkthrough. Keep its authentication setup, imports, request types and error handling together. Use the [permission guide](api-permissions.md) to select the required scopes and resource limits; a credential cannot exceed its owner's current access.

For MCP, follow the appropriate [client connection guide](integrations.md) and [external-agent operations](external-agent-management.md). Use the deployment's actual endpoint and registered authentication configuration. Package validation does not establish that a hosted client completed authorization, renders review UI or supports every management action. Publishing proposed knowledge still needs explicit human review in a supported flow.

Test an authenticated read, a permitted revision-checked mutation and a denied operation. For an unknown write outcome, inspect the retained operation before any explicit replay decision. Finally revoke the connection and verify the next protected operation fails. Record this client acceptance separately from source, SDK, package and deployment checks.

## Keep an acceptance record

Use fictional inputs until this path works. Record what was actually checked; leave unavailable evidence explicit.

| Record | Include |
| --- | --- |
| Configuration | Release, organization/workspace, selected model roles and relevant revisions; no credentials. |
| Knowledge | Original/version IDs, processing outcome, active index and the independently expected result. |
| Authorization | Allowed actor and scope, excluded source, and the outcome after revocation. |
| Answer | Exact source or dataset snapshot, output audit and completed-stream reconnect outcome. |
| Communication | Recipient eligibility, preview language/sender, outbox status, provider acceptance and separately confirmed receipt. |
| Recovery | The same retained operation and original bytes, the reviewed decision and the observed result. |

Local tests and controlled screenshots document implementation behavior. They do not fill in untested provider, recipient, external-client or deployment outcomes.
