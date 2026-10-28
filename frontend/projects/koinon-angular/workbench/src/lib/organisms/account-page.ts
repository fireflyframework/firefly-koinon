// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Injector,
  Input,
  OnChanges,
  Output,
  afterNextRender,
  inject,
} from '@angular/core';
import { KoinonTextPipe, registerKoinonSpanish } from '../foundations/i18n';
import { PANEL_SPANISH } from '../foundations/panel-spanish.generated';
import { KoinonIcon } from '../atoms/icon';
import { KoinonAccountPanel } from './account-panel';
type AccountSection = 'profile' | 'tokens' | 'applications';
registerKoinonSpanish(PANEL_SPANISH);
@Component({
  selector: 'ffk-account-page',
  imports: [KoinonTextPipe, KoinonIcon, KoinonAccountPanel],
  templateUrl: './account-page.html',
  styleUrl: './account-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAccountPage implements OnChanges {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  @Input() section: AccountSection = 'profile';
  @Output() sectionChange = new EventEmitter<AccountSection>();
  @Output() libraryRequested = new EventEmitter<void>();
  ngOnChanges() {
    afterNextRender(
      () => {
        const element = this.host.nativeElement;
        const content = element.closest('main');
        if (content) content.scrollTop = 0;
        element.querySelector<HTMLElement>('h1')?.focus({ preventScroll: true });
      },
      { injector: this.injector },
    );
  }
  readonly sections: { id: AccountSection; label: string; icon: string }[] = [
    { id: 'profile', label: 'Profile & preferences', icon: 'users' },
    { id: 'tokens', label: 'API tokens', icon: 'shield' },
    { id: 'applications', label: 'Authorized applications', icon: 'link' },
  ];
  title() {
    return this.sections.find((row) => row.id === this.section)!.label;
  }
}
