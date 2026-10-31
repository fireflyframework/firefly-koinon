// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  PendingTasks,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonOrganizationDirectory } from '../services/organization-directory';
import { KoinonTextPipe } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonPagination } from '../molecules/pagination';
import type { OrganizationPerson } from '@fireflyframework/koinon-sdk';
@Component({
  selector: 'ffk-organization-colleagues',
  imports: [FormsModule, KoinonTextPipe, KoinonButton, KoinonPagination],
  providers: [KoinonOrganizationDirectory],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: ` <section aria-labelledby="colleagues-heading">
    <h3 id="colleagues-heading">{{ 'People and teams' | ffkText }}</h3>
    <p>{{ 'Only people who share this workspace are shown.' | ffkText }}</p>
    <form (ngSubmit)="apply()">
      <label
        >{{ 'Find a colleague' | ffkText
        }}<input name="colleague-search" [(ngModel)]="query" maxlength="160" /></label
      ><ffk-button type="submit">{{ 'Search' | ffkText }}</ffk-button>
    </form>
    @if (s.error()) {
      <p role="alert">{{ s.error() | ffkText }}</p>
      <ffk-button (click)="search()">{{ 'Retry' | ffkText }}</ffk-button>
    }
    @if (s.busy().has('people')) {
      <p role="status">{{ 'Loading people…' | ffkText }}</p>
    }
    <ul>
      @for (person of s.people()?.items ?? []; track person.id || person.profile_id || $index) {
        <li>
          <div>
            @if (s.avatars()[person.id || person.profile_id || '']) {
              <img
                class="colleague-avatar"
                [src]="s.avatars()[person.id || person.profile_id || '']"
                alt=""
              />
            }
            <strong>{{ person.display_name || ('Name unavailable' | ffkText) }}</strong>
            <p>{{ person.job_title || ('Not provided' | ffkText) }}</p>
            <p>{{ person.unit?.name || ('Not provided' | ffkText) }}</p>
          </div>
          <ffk-button variant="quiet" (click)="s.selectPerson(person); reportsOpen.set(false)">{{
            'Details' | ffkText
          }}</ffk-button>
        </li>
      } @empty {
        @if (!s.busy().has('people') && !s.error()) {
          <li>{{ 'No people match these filters.' | ffkText }}</li>
        }
      }
    </ul>
    <ffk-pagination
      [page]="s.people()"
      [showPageSize]="false"
      [label]="'People' | ffkText"
      (pageChanged)="search($event)"
    />
    @if (s.selected(); as person) {
      <section class="colleague-details">
        <h4>{{ person.display_name || ('Name unavailable' | ffkText) }}</h4>
        <dl>
          <div>
            <dt>{{ 'Job title' | ffkText }}</dt>
            <dd>{{ person.job_title || ('Not provided' | ffkText) }}</dd>
          </div>
          <div>
            <dt>{{ 'Department' | ffkText }}</dt>
            <dd>
              {{
                person.department?.name ||
                  person.presentation?.corporate_department ||
                  ('Not provided' | ffkText)
              }}
            </dd>
          </div>
          <div>
            <dt>{{ 'Team or unit' | ffkText }}</dt>
            <dd>{{ person.unit?.name || ('Not provided' | ffkText) }}</dd>
          </div>
          <div>
            <dt>{{ 'Manager' | ffkText }}</dt>
            <dd>
              {{
                person.manager?.display_name ||
                  ((person.manager_unavailable ? 'Not available' : 'Not provided') | ffkText)
              }}
            </dd>
          </div>
        </dl>
        @if (person.id) {
          <ffk-button variant="quiet" (click)="showReports(person)">{{
            'View direct reports' | ffkText
          }}</ffk-button>
        }
        @if (reportsOpen()) {
          @if (s.busy().has('reports')) {
            <p role="status">{{ 'Loading people…' | ffkText }}</p>
          }
          <ul>
            @for (
              report of s.reports()?.items ?? [];
              track report.id || report.profile_id || $index
            ) {
              <li>
                <strong>{{ report.display_name || ('Name unavailable' | ffkText) }}</strong
                ><ffk-button
                  variant="quiet"
                  (click)="s.selectPerson(report); reportsOpen.set(false)"
                  >{{ 'Details' | ffkText }}</ffk-button
                >
              </li>
            } @empty {
              @if (!s.busy().has('reports')) {
                <li>{{ 'No people in this branch.' | ffkText }}</li>
              }
            }
          </ul>
          <ffk-pagination
            [page]="s.reports()"
            [showPageSize]="false"
            [label]="'Direct reports' | ffkText"
            (pageChanged)="showReports(person, $event)"
          />
        }
      </section>
    }
  </section>`,
  styles: `
    .colleague-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      object-fit: cover;
      margin-right: 10px;
      vertical-align: middle;
    }
    :host {
      display: block;
      margin-top: 24px;
    }
    h3 {
      font-size: 17px;
    }
    h4 {
      font-size: 15px;
    }
    p,
    dt {
      color: var(--ui-muted);
      font-size: 12px;
      line-height: 1.7;
    }
    form {
      display: flex;
      gap: 10px;
      align-items: flex-end;
      flex-wrap: wrap;
    }
    label {
      display: grid;
      gap: 8px;
      flex: 1 1 180px;
      font-size: 12px;
    }
    input {
      min-height: 44px;
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--ui-line);
      border-radius: 8px;
      padding: 10px;
      font: 400 13px var(--ffk-font);
      background: var(--ui-surface);
      color: var(--ui-text);
    }
    input:focus-visible {
      outline: 2px solid var(--ui-accent);
      outline-offset: 3px;
    }
    ul {
      list-style: none;
      margin: 16px 0;
      padding: 0;
    }
    li {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      border-bottom: 1px solid var(--ui-line);
      padding: 14px 0;
      font-size: 13px;
    }
    li p {
      margin: 4px 0;
    }
    dl {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    dd {
      font-size: 13px;
      margin: 4px 0;
      overflow-wrap: anywhere;
    }
    .colleague-details {
      background: var(--ui-subtle);
      border-radius: 10px;
      padding: 16px;
      margin-top: 20px;
    }
    @media (max-width: 600px) {
      dl {
        grid-template-columns: 1fr;
      }
      li {
        align-items: flex-start;
      }
    }
  `,
})
export class KoinonOrganizationColleagues {
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  readonly reportsOpen = signal(false);
  query = '';
  private appliedQuery = '';
  constructor() {
    this.s.workspaceOnly.set(true);
    effect(() => {
      this.s.contextIdentity();
      untracked(() => {
        this.query = '';
        this.appliedQuery = '';
        this.reportsOpen.set(false);
        if (!this.s.denied()) this.tasks.run(() => this.search());
      });
    });
  }
  apply() {
    this.appliedQuery = this.query;
    return this.search();
  }
  search(page = 1) {
    return this.s.loadPeople({ q: this.appliedQuery, page });
  }
  showReports(person: OrganizationPerson, page = 1) {
    if (!person.id) return;
    this.reportsOpen.set(true);
    return this.s.loadReports(person.id, page);
  }
}
