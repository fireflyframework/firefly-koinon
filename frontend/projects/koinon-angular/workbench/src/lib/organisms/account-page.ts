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
import {NgComponentOutlet} from '@angular/common';
import {KOINON_COMMUNICATIONS_LOADER} from '../services/chat-loader';
import {KoinonFacade} from '../koinon-facade';
import {signal,type Type} from '@angular/core';
interface NotificationTarget {kind:'invitation'|'workspace'|'access'|'none';id:string}
type AccountSection = 'profile' | 'tokens' | 'applications' | 'notifications' | 'notification-preferences';
registerKoinonSpanish(PANEL_SPANISH);
@Component({
  selector: 'ffk-account-page',
  imports: [NgComponentOutlet,KoinonTextPipe, KoinonIcon, KoinonAccountPanel],
  templateUrl: './account-page.html',
  styleUrl: './account-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAccountPage implements OnChanges {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly communicationsLoader=inject(KOINON_COMMUNICATIONS_LOADER,{optional:true});
  readonly communications=signal<Type<unknown>|null>(null);
  readonly communicationsError=signal('');
  readonly communicationActions={modeChanged:(mode:'notifications'|'notification-preferences')=>this.sectionChange.emit(mode),signOut:()=>this.signOutRequested.emit(),target:(target:NotificationTarget)=>this.openNotificationTarget(target)};
  async loadCommunications(){if(this.communications())return;if(!this.communicationsLoader){this.communicationsError.set('Notifications are not enabled in this application.');return;}try{this.communications.set(await this.communicationsLoader('center'));}catch{this.communicationsError.set('Notifications could not be opened. Refresh this page and try again.');}}
  @Input() section: AccountSection = 'profile';
  @Output() sectionChange = new EventEmitter<AccountSection>();
  @Output() signOutRequested = new EventEmitter<void>();
  private readonly facade=inject(KoinonFacade);
  async openNotificationTarget(target:NotificationTarget){
    if(target.kind==='access'){this.sectionChange.emit('profile');return;}
    if(target.kind!=='workspace')return;
    const workspace=this.facade.context()?.workspaces.find(row=>row.id===target.id);if(!workspace)return;
    await this.facade.bootstrap(workspace.tenant_id);
    if(!this.facade.context()?.workspaces.some(row=>row.id===target.id&&row.tenant_id===workspace.tenant_id))return;
    await this.facade.setWorkspace(target.id);this.libraryRequested.emit();
  }
  @Output() libraryRequested = new EventEmitter<void>();
  ngOnChanges() {
    if(this.section==='notifications'||this.section==='notification-preferences')void this.loadCommunications();
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
    { id: 'notifications', label: 'Notifications', icon: 'bell' },
    { id: 'notification-preferences', label: 'Notification preferences', icon: 'settings' },
    { id: 'tokens', label: 'API tokens', icon: 'shield' },
    { id: 'applications', label: 'Authorized applications', icon: 'link' },
  ];
  title() {
    return this.sections.find((row) => row.id === this.section)!.label;
  }
}
