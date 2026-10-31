// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  PendingTasks,
  effect,
  untracked,
  signal,
  inject,
} from '@angular/core';
import { KoinonOrganizationDirectory } from '../services/organization-directory';
import { KoinonTextPipe, KoinonDatePipe, registerKoinonSpanish } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { ORGANIZATION_PROFILE_SPANISH } from './organization-spanish';
registerKoinonSpanish(ORGANIZATION_PROFILE_SPANISH);
import { KoinonOrganizationColleagues } from './organization-colleagues';
@Component({
  selector: 'ffk-organization-information',
  imports: [KoinonTextPipe, KoinonDatePipe, KoinonButton, KoinonOrganizationColleagues],
  providers: [KoinonOrganizationDirectory],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section aria-labelledby="your-organization-heading">
    <header>
      <h2 id="your-organization-heading">{{ 'Your organization information' | ffkText }}</h2>
      <p>{{ s.f.tenant()?.name }}</p>
    </header>
    <p>
      {{
        'Your organization administrator manages this information. Contact them to request a correction.'
          | ffkText
      }}
    </p>
    @if (s.error()) {
      <p role="alert">{{ s.error() | ffkText }}</p>
      <ffk-button variant="quiet" (click)="s.loadSelf()">{{ 'Retry' | ffkText }}</ffk-button>
    }
    @if (s.busy().has('self')) {
      <p role="status">{{ 'Loading organization information…' | ffkText }}</p>
    }
    @if (s.self(); as person) {
      <dl>
        <div>
          <dt>{{ 'Job title' | ffkText }}</dt>
          <dd>{{ person.job_title || ('Not provided' | ffkText) }}</dd>
        </div>
        <div>
          <dt>{{ 'Department' | ffkText }}</dt>
          <dd>{{ person.department?.name || ('Not provided' | ffkText) }}</dd>
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
        <div>
          <dt>{{ 'Information source' | ffkText }}</dt>
          <dd>
            {{
              person.source === 'provider'
                ? person.provider_name || ('Identity provider' | ffkText)
                : ((person.source === 'manual' ? 'Managed locally' : 'Not provided') | ffkText)
            }}
          </dd>
        </div>
        @if (person.source === 'provider') {
          <div>
            <dt>{{ 'Source status' | ffkText }}</dt>
            <dd>
              {{
                (person.observation_status === 'current'
                  ? 'Verified at last sign-in'
                  : 'Waiting for a verified update'
                ) | ffkText
              }}
            </dd>
          </div>
        }
        @if (person.updated_at) {
          <div>
            <dt>{{ 'Updated' | ffkText }}</dt>
            <dd>{{ person.updated_at | ffkDate }}</dd>
          </div>
        }
        @if (person.observed_at) {
          <div>
            <dt>{{ 'Last observed' | ffkText }}</dt>
            <dd>{{ person.observed_at | ffkDate }}</dd>
          </div>
        }
      </dl>
    }
    @if (canBrowse()) {
      <ffk-button variant="quiet" (click)="browsing.set(!browsing())">{{
        (browsing() ? 'Close directory' : 'View people and teams') | ffkText
      }}</ffk-button>
      @if (browsing()) {
        @defer (when browsing()) {
          <ffk-organization-colleagues />
        }
      }
    }
  </section>`,
  styles: `
    :host {
      display: block;
      margin-top: 36px;
    }
    section {
      border-top: 1px solid var(--ui-line);
      padding-top: 28px;
    }
    h2 {
      font: 600 17px/1.5 var(--ffk-font);
      margin: 0;
    }
    p {
      font: 400 13px/1.7 var(--ffk-font);
      color: var(--ui-muted);
      max-width: 65ch;
    }
    dl {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      margin: 24px 0;
    }
    dt {
      font-size: 12px;
      color: var(--ui-muted);
      margin-bottom: 6px;
    }
    dd {
      margin: 0;
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    @media (max-width: 600px) {
      dl {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class KoinonOrganizationInformation {
  readonly browsing = signal(false);
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  canBrowse() {
    return (
      this.s.settings()?.visibility === 'shared_workspaces' &&
      !!this.s.f.workspaceId() &&
      this.s.f.permissions().has('catalog:read')
    );
  }
  constructor() {
    effect(() => {
      this.s.contextIdentity();
      untracked(() => {
        this.browsing.set(false);
        if (!this.s.denied())
          this.tasks.run(async () => {
            await this.s.loadSelf();
            if (this.s.self()) await this.s.loadSettings();
          });
      });
    });
  }
}
