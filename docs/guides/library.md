# Work with the knowledge library

The library is the main place to find organizational knowledge. A space contains team folders; folders contain documents and datasets. Technical records such as chunks, tables, snapshots and index versions belong in an item's details rather than the main navigation.

The interface is under active integrated qualification. Use the [qualification record](../operations/qualification.md) to distinguish validated behavior from work still in progress.

## Spaces, projects and folders

A **space** is a knowledge boundary. Its documents and datasets keep that space's identity in both native knowledge engines, and every operation checks the caller's current access. A folder name or a tag does not grant access. Create separate spaces when teams or clients need different permissions; do not rely on sibling folders for confidentiality.

Inside a space, Library projects and nested folders organize content. They inherit the space's permissions. A Library project is different from a chat project, which groups conversations and can enable the owner's shared conversation memory. Moving a Library folder does not move a conversation or publish conversation memory.

The installation can provide system spaces and system folders. **System space** or **System folder** identifies these retained defaults. Their names and descriptions can be maintained with the appropriate permission, but their system identity cannot be removed. They cannot be deleted, archived or moved, even through an administrator's API token. Creating a subfolder beneath a system folder does not make the new folder a system folder.

Choose the current destination, then create the next project or folder. Nested collection and corpus folders can contain further folders, documents and datasets. Nesting is bounded so the complete path can always be checked; a rejected depth limit requires a shallower destination. Ordinary empty folders can be deleted. Archive retains ordinary content and hides it until restored.

<figure>
  <img src="../assets/screenshots/library-create-folder.png" alt="Create a Library folder with its name, description and current destination" width="1440" height="1000" loading="lazy">
  <figcaption>Compiled interface with controlled example data. Create a folder and Add knowledge remain separate actions.</figcaption>
</figure>

### Move a folder safely

Select an ordinary organizational folder and its destination inside the same Library project and space. A move retains the folder and asset IDs, native source bindings, historical versions and previously recorded response evidence. The audit event records the old and new parent. New reads use the current path and current permissions.

The request includes the parent and update timestamp you last observed. If another person changed the folder, reload it and review the destination rather than repeating the old request. Moves reject cycles, archived destinations, excessive nesting and pending processing. Tokens restricted to individual assets cannot move a whole folder; the caller needs current write access to the knowledge space.

A move between spaces or Library projects returns `KNOWLEDGE_TRANSFER_REQUIRED`. This operation deliberately does not rewrite native scopes, indexes or source provenance. Cross-boundary transfer needs its own reviewed migration; it is not implemented by changing a parent identifier.

## Find and open

Choose the organization and space you have access to. Browse folders with the list, breadcrumb or knowledge tree. Search narrows the current context; clear the search to return to the folder. Opening an item and inspecting its details are separate actions, so a details drawer does not interrupt browsing.

A document keeps its source and extracted evidence. A dataset exposes its table and column definitions, immutable snapshots and governed query results. Names are for people; canonical identifiers and source bindings remain on the server.

## Read and filter a folder

The list shows each item's name, type and available content details, metadata tags and last update. Folders show the content visible to you. Documents can show recorded pages and file size; datasets can show registered tables and recorded row or column counts. Missing statistics remain unknown. An original upload's size is not the total size of a dataset with several files.

Choose **Name**, **Type & contents** or **Updated** to change the server's ordering. The type column groups resource types; it does not sort by an inferred quantity. On a small screen, use the sort selector. **More filters** includes format, status, tags and **Recently added**. Apply the selection to filter the whole folder, including pages you have not opened. Active filter chips show what is applied and let you remove individual conditions.

Format and language labels come from recorded metadata or a supported file suffix. Custom tags keep their display spelling. These labels do not call a model or create new knowledge. Choosing a tag uses its recorded value as the server filter. Folder names alone do not establish a file format.

The page controls keep their labels and values together. Change the page size to return to the first page. Moving to another folder clears the previous folder's filters. Mobile rows retain the name, useful content details and tags without requiring the full desktop grid.

## Add knowledge

Start from the destination folder and choose **Add knowledge**. Review the destination, file and processing mode before uploading. The result shows the observed processing state. Uploading bytes, processing a source and making knowledge searchable are distinct states. A failed provider or unsupported format must produce an actionable error; a request reaching the server is not a successful import.

```mermaid
flowchart LR
  Folder[Current folder] --> Select[Choose a file]
  Select --> Review[Review destination and content type]
  Review --> Upload[Upload]
  Upload --> Processing[Process and persist]
  Processing --> Ready[Open the resulting knowledge]
  Processing --> Failure[Inspect error and recover]
```

Editors can add and maintain knowledge in their authorized scope. Viewers can read and ask questions. Analysts can also query datasets. A missing permission should explain the action that requires access without exposing information from another organization or space.

## Maintain and inspect

Keep titles and descriptions recognizable to the team. Inspect original source details, processing state, lineage and references before replacing or retiring knowledge. Dataset query results should identify the snapshot used; source evidence should retain section or page references when supplied by the source format.

Choose the history icon beside a dataset table to open [History & lineage](lineage.md). Versions are paginated, and each detail read keeps the selected historical snapshot separate from the current pointer. A missing original record stays visible rather than being inferred from the latest file.

Document details expose extracted chunks with their citation identities and any supplied page or section. Processing offsets describe the emitted chunk stream, including overlap; they are not positions in the original file. Use page or section references when locating evidence in an original document.

The content API checks the current revision before replacing or reingesting knowledge. A document update requires acknowledgment that previous chunk identities will be invalidated. Existing citation rows remain recorded, and the response reports the actual effects. Dataset table updates preserve historical snapshots. If the revision changed, reload the current state and review it before retrying.

Archive keeps the content and its processing state while hiding the item and its descendants from the library. Restore brings them back. A processing job that finishes while an item is archived updates its saved state without making the item visible again.

### Append a dataset file through the API

`POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/files` requires a stable `Idempotency-Key` and accepts exactly one multipart `file` for an existing dataset. It keeps the dataset identity and appends the file's parsed sheets or sections as new tables, up to 128 tables within the configured upload byte limit. It records a file version, immutable input coordinates and snapshots. Existing table identities and historical snapshots remain retained. The result returns the canonical dataset, file-version and new table identifiers.

The SDK helpers are `append_dataset_file` in Python, `dataset.appendFile` in TypeScript and `datasets(tenant).appendFile` in Java. The caller needs current catalog and ingestion write permissions for the complete ancestry. Datasets with multiple canonical aliases are rejected pending explicit alias reconciliation.

Append takes an exclusive publication claim. Dataset queries and schema reads return `DATASET_NOT_READY` while intake is pending or failed. Native processing commits sections independently: if a later section or canonical publication fails, earlier native effects may remain. Existing files and snapshots are preserved, but the dataset stays unavailable until its retained file version is reconciled. The same key and exact file return the retained completed receipt after current permissions are checked, without repeating native work. The receipt describes the original completed operation; it is not a fresh dataset-readiness check. A changed payload conflicts, and unfinished keys require reconciliation. There is no automatic retry or public reconciliation helper.

This development endpoint has canonical, native-adapter and HTTP regression coverage. Canonical append locking, cancellation, replay and revocation passed eleven PostgreSQL checks with a controlled native port. Full native/provider append acceptance and recovery remain separate qualification steps. It does not provide asynchronous or bulk intake.

Physical deletion is a separate API operation. It rejects nonempty resources and active workspace memberships. Source retention and storage cleanup use their own domain operations.

## Use on a small screen

Navigation and the knowledge tree open as dismissible drawers. Keep the current folder visible when closing them. Open the detail inspector only when needed. Wide dataset results can scroll inside their own region while the page and primary controls remain usable.

Keyboard users should be able to reach search, expand the tree, open a row, inspect details and dismiss dialogs with focus returned to the originating control. Reduced-motion settings disable decorative heartbeat and movement while preserving progress and status information.
