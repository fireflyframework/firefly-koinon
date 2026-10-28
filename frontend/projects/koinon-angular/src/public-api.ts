// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
export { KoinonFacade } from '@fireflyframework/koinon-angular/workbench';
export {
  KOINON_CLIENT,
  KOINON_TRANSPORT,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular/workbench';
export type { KoinonScope, KoinonView } from '@fireflyframework/koinon-angular/workbench';
export { KoinonCitationPanel } from '@fireflyframework/koinon-angular/workbench';
export { KoinonButton } from '@fireflyframework/koinon-angular/workbench';
export { KoinonBadge } from '@fireflyframework/koinon-angular/workbench';
export { KoinonSkeleton } from '@fireflyframework/koinon-angular/workbench';
export { KoinonIcon } from '@fireflyframework/koinon-angular/workbench';
export { KoinonCodeBlock } from '@fireflyframework/koinon-angular/workbench';
export { KoinonFormField } from '@fireflyframework/koinon-angular/workbench';
export { KoinonSearchField } from '@fireflyframework/koinon-angular/workbench';
export { KoinonBreadcrumb } from '@fireflyframework/koinon-angular/workbench';
export { KoinonResourceList } from '@fireflyframework/koinon-angular/workbench';
export { KoinonShell, type PrimaryDestination } from '@fireflyframework/koinon-angular/workbench';
export { KoinonLibraryTemplate } from '@fireflyframework/koinon-angular/workbench';

export { KoinonFolderTree } from '@fireflyframework/koinon-angular/workbench';
export { KoinonInspector } from '@fireflyframework/koinon-angular/workbench';

export {
  KOINON_CHAT_LOADER,
  KOINON_SETTINGS_LOADER,
  KOINON_INVITATION_LOADER,
  KOINON_SHARED_CONVERSATION_LOADER,
} from '@fireflyframework/koinon-angular/workbench';
export { KoinonAssistant } from '@fireflyframework/koinon-angular/workbench';
export { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench';

export { KoinonPagination } from '@fireflyframework/koinon-angular/workbench';
export { friendlyStatus } from '@fireflyframework/koinon-angular/workbench';
export type { FolderPageState } from '@fireflyframework/koinon-angular/workbench';

export {
  KoinonI18n,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular/workbench';

export { KoinonFilterBar } from './lib/molecules/filter-bar';
export { KoinonSidePanel } from '@fireflyframework/koinon-angular/workbench';

export { KoinonConversationGroups } from './lib/services/conversation-groups';
export type {
  ConversationPage,
  ConversationBranch,
} from './lib/services/conversation-group-models';

export {
  KoinonCommandPalette,
  type KoinonCommand,
} from '@fireflyframework/koinon-angular/workbench';

export { KoinonEvidenceGroups } from './lib/services/evidence-groups';

import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { SPANISH } from './lib/foundations/spanish';
registerKoinonSpanish(SPANISH);
