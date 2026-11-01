// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { createApplication } from '@angular/platform-browser';
import { createCustomElement } from '@angular/elements';
import { KOINON_ACTIVITY_LOADER,KOINON_COMMUNICATIONS_LOADER,KOINON_CHAT_LOADER,KOINON_SETTINGS_LOADER,KOINON_SHARED_CONVERSATION_LOADER,KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
async function register(): Promise<void> {
  if (customElements.get('firefly-koinon')) return;
  const app = await createApplication({ providers: [{provide:KOINON_ACTIVITY_LOADER,useValue:()=>import('@fireflyframework/koinon-angular/activity').then(module=>module.KoinonActivityPanel)},{provide:KOINON_COMMUNICATIONS_LOADER,useValue:(kind:'trigger'|'center'|'email')=>kind==='trigger'?import('@fireflyframework/koinon-angular/communications/runtime').then(module=>module.KoinonNotificationCenterTrigger):kind==='email'?import('@fireflyframework/koinon-angular/communications/invitations').then(module=>module.KoinonEmailInvitationAcceptance):import('@fireflyframework/koinon-angular/communications/inbox').then(module=>module.KoinonNotificationCenter)},{provide:KOINON_SHARED_CONVERSATION_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/chat/page").then(module=>module.KoinonSharedConversation)},{provide:KOINON_CHAT_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/chat/page").then(module=>module.KoinonChatPage)},{provide:KOINON_SETTINGS_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/settings").then(module=>module.KoinonSettingsPage)}] });
  const element = createCustomElement(KoinonWorkbench, { injector: app.injector });
  customElements.define('firefly-koinon', element);
}
void register();
