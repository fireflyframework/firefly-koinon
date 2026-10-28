// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {InjectionToken,type Type} from '@angular/core';
export const KOINON_CHAT_LOADER=new InjectionToken<()=>Promise<Type<unknown>>>('Koinon optional Chat component');
export const KOINON_SETTINGS_LOADER=new InjectionToken<()=>Promise<Type<unknown>>>('Koinon optional Settings component');

export const KOINON_INVITATION_LOADER=new InjectionToken<()=>Promise<Type<unknown>>>('Koinon optional invitation component');
export const KOINON_SHARED_CONVERSATION_LOADER=new InjectionToken<()=>Promise<Type<unknown>>>('Koinon optional shared conversation component');
