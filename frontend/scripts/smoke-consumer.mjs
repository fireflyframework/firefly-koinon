// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url)),
  host = fileURLToPath(new URL('../smoke/angular-host/', import.meta.url));
const [{ filename }] = JSON.parse(
  execFileSync('npm', ['pack', './dist/koinon-angular', '--pack-destination', 'dist', '--json'], {
    cwd: root,
    encoding: 'utf8',
  }),
);
execFileSync(
  'npm',
  [
    'install',
    fileURLToPath(new URL('../dist/' + filename, import.meta.url)),
    '--no-save',
    '--no-package-lock',
    '--force',
    '--no-audit',
    '--no-fund',
  ],
  { cwd: host, stdio: 'inherit' },
);
for (const entry of [
  'fireflyframework-koinon-angular',
  'fireflyframework-koinon-angular-workbench',
  'fireflyframework-koinon-angular-chat',
  'fireflyframework-koinon-angular-chat-page',
  'fireflyframework-koinon-angular-chat-evidence',
  'fireflyframework-koinon-angular-settings',
  'fireflyframework-koinon-angular-communications',
  'fireflyframework-koinon-angular-communications-runtime',
  'fireflyframework-koinon-angular-communications-invitations',
  'fireflyframework-koinon-angular-communications-inbox',
  'fireflyframework-koinon-angular-communications-preferences',
  'fireflyframework-koinon-angular-communications-admin',
  'fireflyframework-koinon-angular-communications-schedule',
  'fireflyframework-koinon-angular-communications-email-preview',
  'fireflyframework-koinon-angular-activity',
  'fireflyframework-koinon-angular-activity-window',
]) {
  const built = readFileSync(
      new URL('../dist/koinon-angular/fesm2022/' + entry + '.mjs', import.meta.url),
    ),
    installed = readFileSync(
      new URL(
        '../smoke/angular-host/node_modules/@fireflyframework/koinon-angular/fesm2022/' +
          entry +
          '.mjs',
        import.meta.url,
      ),
    );
  if (!built.equals(installed))
    throw new Error('Installed package differs from the current build: ' + entry);
}
execFileSync('npm', ['run', 'build'], { cwd: host, stdio: 'inherit' });
