// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';

export const appConfig: ApplicationConfig = {
  providers: [provideBrowserGlobalErrorListeners()],
};
