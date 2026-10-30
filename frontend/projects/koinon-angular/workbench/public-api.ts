// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export { KoinonWorkbench } from './src/lib/koinon-angular';
export { KoinonFacade } from './src/lib/koinon-facade';
export { KOINON_CLIENT, KOINON_TRANSPORT, provideKoinonClient } from './src/lib/client-provider';
export { KOINON_TENANT_RESOLVER, type KoinonTenantResolver } from './src/lib/client-provider';
export type { KoinonScope, KoinonView } from './src/lib/models';
export { KoinonCitationPanel } from './src/lib/citation-panel';
export { KoinonButton } from './src/lib/atoms/button';
export { KoinonBadge } from './src/lib/atoms/badge';
export { KoinonSkeleton } from './src/lib/atoms/skeleton';
export { KoinonIcon } from './src/lib/atoms/icon';
export { KoinonCodeBlock } from './src/lib/atoms/code-block';
export { KoinonFormField } from './src/lib/molecules/form-field';
export { KoinonSearchField } from './src/lib/molecules/search-field';
export { KoinonBreadcrumb } from './src/lib/molecules/breadcrumb';
export { KoinonResourceList } from './src/lib/organisms/resource-list';
export { KoinonShell, type PrimaryDestination } from './src/lib/organisms/shell';
export { KoinonLibraryTemplate } from './src/lib/templates/library-template';

export { KoinonFolderTree } from './src/lib/organisms/folder-tree';
export { KoinonInspector } from './src/lib/organisms/inspector';

export {
  KOINON_CHAT_LOADER,
  KOINON_SETTINGS_LOADER,
  KOINON_INVITATION_LOADER,
  KOINON_SHARED_CONVERSATION_LOADER,
} from './src/lib/services/chat-loader';
export { KoinonAssistant } from './src/lib/services/assistant';
export { KoinonClientContext } from './src/lib/services/client-context';

export { KoinonPagination } from './src/lib/molecules/pagination';
export { friendlyStatus } from './src/lib/services/library-tree';
export type { FolderPageState } from './src/lib/models';

export {
  KoinonI18n,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonValuePipe,
} from './src/lib/foundations/i18n';

export { KoinonSidePanel } from './src/lib/molecules/side-panel';

export { KoinonCommandPalette, type KoinonCommand } from './src/lib/organisms/command-palette';

export { registerKoinonSpanish } from './src/lib/foundations/i18n';

export { KoinonBranding } from './src/lib/services/branding';
export {
  contrast,
  previewBrandStyles,
  DEFAULT_BRANDING,
  resolveBranding,
  brandStyles,
  brandImage,
  brandSymbol,
  validateBranding,
  PALETTE_FIELDS,
} from './src/lib/services/branding-values';

export { KoinonOrganizationDirectory } from './src/lib/services/organization-directory';
