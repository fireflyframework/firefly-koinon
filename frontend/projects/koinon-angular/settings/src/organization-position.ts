// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  ElementRef,
  Injector,
  afterNextRender,
  Component,
  Input,
  OnChanges,
  EventEmitter,
  Output,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonButton, KoinonPagination, KoinonTextPipe } from '@fireflyframework/koinon-angular';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
import type {
  OrganizationPerson,
  OrganizationPersonPatch,
  OrganizationUnitSummary,
} from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationUnitBrowser } from './organization-unit-browser';
import { positionPatch } from './organization-position-fields';
@Component({
  selector: 'ffk-organization-position',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonTextPipe,
    KoinonPagination,
    KoinonOrganizationUnitBrowser,
  ],
  templateUrl: './organization-position.html',
  styleUrl: './organization-directory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationPosition implements OnChanges {
  @Input({ required: true }) person!: OrganizationPerson;
  @Output() closed = new EventEmitter<void>();
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  readonly unitPicker = signal(false);
  readonly managerPicker = signal(false);
  title = '';
  unit: OrganizationUnitSummary | null = null;
  manager: OrganizationPerson['manager'] = null;
  manageLocally = false;
  managedProviderId = '';
  managerQuery = '';
  ngOnChanges() {
    this.title = this.person.job_title ?? '';
    this.unit = this.person.unit ?? null;
    this.manager = this.person.manager ?? null;
    this.manageLocally = false;
    this.managedProviderId = '';
    this.unitPicker.set(false);
    this.managerPicker.set(false);
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>('h3')?.focus(), {
      injector: this.injector,
    });
  }
  managed(field: 'job_title' | 'unit_id' | 'manager_id') {
    return (
      !!this.managedProviderId ||
      (!this.manageLocally && !!this.person.managed_fields?.includes(field))
    );
  }
  providerPage(page: number) {
    this.managedProviderId = '';
    return this.s.loadProviders(page);
  }
  canChooseSource() {
    return !!this.person.id && this.s.f.tenantPermissions().has('identity:manage');
  }
  chooseUnit(unit: OrganizationUnitSummary) {
    this.unit = unit;
    this.unitPicker.set(false);
  }
  async findManagers(page = 1) {
    await this.s.searchManagers(this.managerQuery, page);
  }
  chooseManager(person: OrganizationPerson) {
    if (!person.id || person.id === this.person.id) return;
    this.manager = { id: person.id, display_name: person.display_name };
    this.managerPicker.set(false);
  }
  async save() {
    const draft: Pick<OrganizationPersonPatch, 'job_title' | 'unit_id' | 'manager_id'> = {
      job_title: this.title.trim() || null,
      unit_id: this.unit?.id ?? null,
      manager_id: this.manager?.id ?? null,
    };
    if (
      await this.s.savePerson(
        this.person,
        positionPatch(this.person, draft, this.manageLocally),
        this.manageLocally,
        this.managedProviderId || undefined,
      )
    )
      this.closed.emit();
  }
}
