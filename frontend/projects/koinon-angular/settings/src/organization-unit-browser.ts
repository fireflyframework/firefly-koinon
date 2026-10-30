// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  ElementRef,
  Injector,
  afterNextRender,
  Component,
  EventEmitter,
  Input,
  Output,
  PendingTasks,
  effect,
  untracked,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonButton, KoinonTextPipe, KoinonPagination } from '@fireflyframework/koinon-angular';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
import type { OrganizationUnit, OrganizationUnitSummary } from '@fireflyframework/koinon-sdk';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { ORGANIZATION_SPANISH } from './organization-spanish';
registerKoinonSpanish(ORGANIZATION_SPANISH);
@Component({
  selector: 'ffk-organization-unit-browser',
  imports: [FormsModule, KoinonButton, KoinonTextPipe, KoinonPagination],
  providers: [KoinonOrganizationDirectory],
  templateUrl: './organization-unit-browser.html',
  styleUrl: './organization-directory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationUnitBrowser {
  @Input() picking = false;
  @Output() unitSelected = new EventEmitter<OrganizationUnitSummary>();
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private focusBranch() {
    afterNextRender(
      () => {
        const element = this.host.nativeElement;
        const target =
          element.querySelector<HTMLElement>('.branch-path [aria-current]') ||
          element.querySelector<HTMLElement>('.branch-path button');
        target?.focus();
      },
      { injector: this.injector },
    );
  }
  readonly path = signal<OrganizationUnit[]>([]);
  readonly editing = signal<OrganizationUnit | null | undefined>(undefined);
  readonly removing = signal<OrganizationUnit | null>(null);
  name = '';
  kind: OrganizationUnit['kind'] = 'department';
  query = '';
  private appliedQuery = '';
  readonly parentChoice = signal<OrganizationUnitSummary | null | undefined>(undefined);
  readonly choosingParent = signal(false);
  constructor() {
    effect(() => {
      this.s.contextIdentity();
      untracked(() => {
        this.path.set([]);
        this.editing.set(undefined);
        this.removing.set(null);
        if (!this.s.denied()) this.tasks.run(() => this.load());
      });
    });
  }
  apply() {
    this.appliedQuery = this.query;
    return this.load();
  }
  load(page = 1) {
    return this.s.loadUnits({
      parent_id: this.path().at(-1)?.id,
      q: this.appliedQuery || undefined,
      page,
    });
  }
  async enter(unit: OrganizationUnit) {
    if (this.path().length >= 32) return;
    this.path.update((path) => [...path, unit]);
    this.query = '';
    this.appliedQuery = '';
    const loaded = await this.load();
    this.focusBranch();
    return loaded;
  }
  async back(index: number) {
    this.path.update((path) => path.slice(0, index));
    this.query = '';
    this.appliedQuery = '';
    const loaded = await this.load();
    this.focusBranch();
    return loaded;
  }
  begin(unit: OrganizationUnit | null) {
    this.editing.set(unit);
    this.removing.set(null);
    this.name = unit?.name ?? '';
    this.kind = unit?.kind ?? 'department';
    this.parentChoice.set(undefined);
    this.choosingParent.set(false);
  }
  chooseParent(unit: OrganizationUnitSummary | null) {
    this.parentChoice.set(unit);
    this.choosingParent.set(false);
  }
  async save() {
    const unit = this.editing();
    if (unit === undefined || !this.name.trim()) return;
    const base = { name: this.name.trim(), kind: this.kind };
    const chosen = this.parentChoice();
    const input = unit
      ? {
          ...base,
          expected_revision: unit.revision,
          ...(chosen !== undefined ? { parent_id: chosen?.id ?? null } : {}),
        }
      : {
          ...base,
          parent_id: chosen === undefined ? (this.path().at(-1)?.id ?? null) : (chosen?.id ?? null),
        };
    if (await this.s.saveUnit(unit, input)) {
      this.editing.set(undefined);
      await this.load();
      this.focusBranch();
    }
  }
  async remove() {
    const unit = this.removing();
    if (unit && (await this.s.deleteUnit(unit))) {
      this.removing.set(null);
      await this.load();
      this.focusBranch();
    }
  }
  label(kind: string) {
    return kind === 'division' ? 'Division' : kind === 'department' ? 'Department' : 'Team';
  }
}
