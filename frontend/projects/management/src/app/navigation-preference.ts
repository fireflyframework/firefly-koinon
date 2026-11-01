// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
type NavigationWindow = {localStorage: Pick<Storage, 'getItem' | 'setItem'>};
const key = 'koinon-navigation-collapsed';
export function readNavigationPreference(window: NavigationWindow | null): boolean {
  try { return window?.localStorage.getItem(key) === 'true'; } catch { return false; }
}
export function saveNavigationPreference(window: NavigationWindow | null, collapsed: boolean): void {
  try { window?.localStorage.setItem(key, String(collapsed)); } catch { /* Navigation remains usable when storage is disabled. */ }
}
