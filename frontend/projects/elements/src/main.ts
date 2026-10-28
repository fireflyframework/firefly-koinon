// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { createApplication } from '@angular/platform-browser';
import { createCustomElement } from '@angular/elements';
import { KOINON_CHAT_LOADER,KOINON_SETTINGS_LOADER,KOINON_SHARED_CONVERSATION_LOADER,KoinonWorkbench } from '@fireflyframework/koinon-angular';
async function register(): Promise<void> {
  if (customElements.get('firefly-koinon')) return;
  const app = await createApplication({ providers: [{provide:KOINON_SHARED_CONVERSATION_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/chat/page").then(module=>module.KoinonSharedConversation)},{provide:KOINON_CHAT_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/chat/page").then(module=>module.KoinonChatPage)},{provide:KOINON_SETTINGS_LOADER,useValue:()=>import("@fireflyframework/koinon-angular/settings").then(module=>module.KoinonSettingsPage)}] });
  const element = createCustomElement(KoinonWorkbench, { injector: app.injector });
  customElements.define('firefly-koinon', element);
}
void register();
