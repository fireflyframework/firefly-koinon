# Provision knowledge before the first sign-in

An operator can provision initial model connections, optional team-defined spaces, compatible empty indexes and the organization chat agent before any administrator signs in. This is a deployment command, not a public HTTP endpoint. It uses native pyfly dependency injection, repositories, transactions, encryption and existing domain services. It records `system:installation` as the audit actor and never creates a user, session, token or membership.

Apply migrations through the current release head (including `koinon_0043_ordinary_folders`) and run the normal scoped-role grant step first. The installation ledger introduced by `koinon_0036_installation` is writable only by the privileged installation/migration database identity. The API and worker identities must have no ledger privileges. The operator requires the normal named Canon and Structured data sources and their restricted native provisioning capabilities. PostgreSQL is required for this operator workflow; SQLite does not admit an installation.

## Prepare a protected manifest

Start from [`installation-plan.json.example`](https://github.com/fireflyframework/firefly-koinon/blob/main/deploy/production/installation-plan.json.example). Set an existing organization ID, approved provider endpoints and model IDs. Configure the real `koinon.assistants.allowed_provider_hosts` allowlist for those hosts. The normal provider address policy remains in force. Credentials are read from the environment names in `secret_env`; the manifest must not contain keys or URL credentials. Mount both the manifest and secret inputs through your deployment's protected configuration mechanism.

The supplied manifest configures providers, organization-wide model connections and the default agent. Its `catalog` and `indexes` arrays are empty: installation does not create a prescribed Library structure. Keeping model configuration separate from folder creation lets each team decide how to organize its knowledge.

### Choose your initial structure

Start in Library with **Create a space**, then create a project and the document or dataset folders you need. Names and descriptions belong to your team. There are no protected system folders. An authorized user can rename, move, archive or delete folders within the normal hierarchy, access and content-retention rules. Deleting a populated folder is not a shortcut around those rules.

Operators who deliberately want to provision a structure can still declare `catalog` entries in the manifest. These become ordinary folders, with installation provenance retained for recovery and auditing. `indexes` may reference only workspaces explicitly declared in that same manifest. With an empty Library, configure and qualify the embedding index for each workspace after creating it; registering an embedding provider alone does not create a serving index or establish ingestion readiness.

Upgrades preserve the IDs, source bindings, permissions, contents and installation receipts of earlier default folders. Migration 43 removes their special archive, move and deletion restrictions without deleting any rows. The original installation keys remain internal historical provenance, not a protection flag or an access grant. Do not rerun an old bootstrap to reorganize a populated installation. Drain old application and worker replicas before this migration, then start the matching release; an old binary can still impose the retired restrictions.

Installed records retain the audit subject `system:installation`. The public author display for that exact subject is **koinon**, including on branded installations. This attribution identifies the software action and does not create a person or grant access. Unknown historical authors remain unknown. Later edits retain the identity of the actual editor.

See [Work with the knowledge library](../guides/library.md) for browsing, folder maintenance, upload states and source history. The initial provisioning command creates and qualifies empty indexes; it does not yet publish an introductory document into those indexes. A successful setup receipt alone therefore does not establish that the assistant can answer questions about the product itself.

Use stable keys, including context in child keys when multiple workspaces contain similarly named folders. Keys are unique within each manifest section. Keep the same `plan_key`, folder keys and manifest content for retries of the same plan.

```bash
chmod 600 /run/installation/knowledge.json
python deploy/bootstrap_knowledge.py \
  --manifest /run/installation/knowledge.json --validate-only
```

Validation parses bounded typed inputs and checks their references. It starts no application, resolves no credentials and makes no network request. It does not attest that a provider, database or index is operational.

## Apply through the operator job

Run the following in the released deployment bundle using its installed product packages and normal production configuration. Bind the primary source to the privileged operator credential only for this job. Never give that credential to the API or worker, and never grant the runtime role ledger writes to make this command pass.

```bash
python deploy/bootstrap_knowledge.py --manifest /run/installation/knowledge.json
```

The command checks its database capability before any installation write. It creates encrypted provider records through the same domain writer used by ordinary administration, discovers the declared models and performs bounded synthetic native chat/streaming qualification. An agent that needs tools must also complete one fixed, data-free health tool cycle. These checks use the exact configured model options; they do not execute organizational knowledge tools or inspect customer content. Provider charges may apply.

Initial embeddings are qualified with two bounded synthetic inputs. The operator releases its database transaction before these provider requests, then rechecks the installation lease, provider revision and workspace ownership before saving the index intent. A concurrent configuration change stops that write; it does not produce an intent qualified against the old provider. Replaying an already recorded intent checks its retained revision without another embedding probe. An index is allocated only for an empty workspace owned by this installation plan. Its native configuration, actual dimensions, ANN structure and active pointer must pass the existing domain checks before the matching embedding role is installed. Existing manual indexes, populated native scopes or conflicting serving pointers stop the plan. This command does not reindex existing content or replace an existing model binding.

Generative role assignments are created explicitly. The agent is organization-wide; its subsequent user executions remain subject to current membership, token ceilings and knowledge ACLs. The organization default is set with compare-and-swap only if it is empty. Existing manual providers, same-scope role assignments, folders or default agents are preserved and reported as conflicts rather than adopted or overwritten.

## Recover a partial attempt

The ledger is bound to the installation UUID, organization, stable plan key and the hash of the complete nonsecret manifest. Every committed step has an immutable receipt. Native storage operations and external model calls are not presented as a single cross-database transaction.

A partial or expired attempt requires the operator to inspect its retained state and explicitly resume the **same** manifest:

```bash
python deploy/bootstrap_knowledge.py \
  --manifest /run/installation/knowledge.json --resume
```

A live owner lease blocks another operator. Resume increments the owner generation and fences the old process. Deterministic native target IDs and immutable provenance checks reconcile an uncertain prior native write; completed steps are not recreated. Any changed provider revision, folder identity, role revision, index lifecycle or manual default stops recovery. A changed manifest cannot reuse the same plan key.

A completed plan returns its historical receipt without probing providers or changing configuration. This is not a claim that a later manually modified installation is currently healthy. Verify authenticated chat, native knowledge tools, streaming, ingestion and MCP against the deployed URLs after installation. Keep operator execution logs and recovery receipts protected. Automatic ledger downgrade/deletion is unsupported; use a reviewed restore procedure.
