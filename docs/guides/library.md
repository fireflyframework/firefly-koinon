# Work with the knowledge library

The library is the main place to find organizational knowledge. A space contains team folders; folders contain documents and datasets. Technical records such as chunks, tables, snapshots and index versions belong in an item's details rather than the main navigation.

The interface is under active integrated qualification. Use the [qualification record](../operations/qualification.md) to distinguish validated behavior from work still in progress.

## Find and open

Choose the organization and space you have access to. Browse folders with the list, breadcrumb or knowledge tree. Search narrows the current context; clear the search to return to the folder. Opening an item and inspecting its details are separate actions, so a details drawer does not interrupt browsing.

A document keeps its source and extracted evidence. A dataset exposes its table and column definitions, immutable snapshots and governed query results. Names are for people; canonical identifiers and source bindings remain on the server.

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

This development endpoint has canonical, native-adapter and HTTP regression coverage. Actual PostgreSQL append concurrency, configured-provider acceptance and recovery remain unqualified. It does not provide asynchronous or bulk intake.

Physical deletion is a separate API operation. It rejects nonempty resources and active workspace memberships. Source retention and storage cleanup use their own domain operations.

## Use on a small screen

Navigation and the knowledge tree open as dismissible drawers. Keep the current folder visible when closing them. Open the detail inspector only when needed. Wide dataset results can scroll inside their own region while the page and primary controls remain usable.

Keyboard users should be able to reach search, expand the tree, open a row, inspect details and dismiss dialogs with focus returned to the originating control. Reduced-motion settings disable decorative heartbeat and movement while preserving progress and status information.
