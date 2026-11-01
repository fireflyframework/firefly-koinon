// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { CatalogEntry, ResourceKind } from '@fireflyframework/koinon-sdk';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';

interface Draft {
  subject: string;
  tenant: string;
  parent: string;
  workspace: string;
  project: string;
  dialog: 'create' | 'edit';
  kind: ResourceKind;
  entry: CatalogEntry | null;
  name?: string;
  description?: string;
}

/** Tab-memory only. It retains editable text, never a request or a promise to resubmit. */
export class LibrarySessionDraft {
  private open: Draft | null = null;
  private saved: Draft | null = null;
  constructor(private readonly w: KoinonWorkbench) {}
  track(): void {
    if (this.w.f.authRequired()) {
      this.capture();
      return;
    }
    const dialog = this.w.dialog();
    if (dialog !== 'create' && dialog !== 'edit') {
      this.open = null;
      return;
    }
    const subject = this.w.f.context()?.subject;
    if (subject)
      this.open = {
        subject,
        tenant: this.w.f.tenantId(),
        parent: this.w.f.parentId(),
        workspace: this.w.f.workspaceId(),
        project: this.w.f.projectId(),
        dialog,
        kind: this.w.formKind,
        entry: this.w.f.selected(),
      };
  }
  capture(): void {
    if (!this.open || this.w.formName.length > 160 || this.w.formDescription.length > 8000) return;
    this.saved = { ...this.open, name: this.w.formName, description: this.w.formDescription };
    this.open = null;
  }
  clear(): void {
    this.open = this.saved = null;
  }
  async restore(): Promise<boolean> {
    const draft = this.saved;
    this.saved = null;
    if (
      !draft ||
      draft.subject !== this.w.f.context()?.subject ||
      draft.tenant !== this.w.f.tenantId()
    )
      return false;
    if (draft.parent) {
      if (!(await this.w.f.loadResource(draft.parent))) return false;
      const parent = this.w.f.selected();
      if (
        !parent ||
        parent.status === 'archived' ||
        parent.workspace_id !== draft.workspace ||
        (parent.kind === 'project' ? parent.id : (parent.project_id ?? '')) !== draft.project
      )
        return false;
      await this.w.openFolder(draft.parent);
    }
    if (!this.w.f.canWrite()) return false;
    if (draft.dialog === 'edit') {
      if (!draft.entry || !(await this.w.f.loadResource(draft.entry.id))) return false;
      const current = this.w.f.selected();
      if (
        !current ||
        current.system_managed ||
        current.status === 'archived' ||
        !draft.entry.updated_at ||
        current.updated_at !== draft.entry.updated_at ||
        current.parent_id !== draft.entry.parent_id
      )
        return false;
    }
    this.w.formKind = draft.kind;
    this.w.formName = draft.name ?? '';
    this.w.formDescription = draft.description ?? '';
    this.w.showDialog(draft.dialog);
    return true;
  }
}
