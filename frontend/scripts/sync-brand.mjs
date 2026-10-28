// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { cp, mkdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const source = new URL('../../brand/', import.meta.url);
const destination = new URL('../.brand/', import.meta.url);
await readFile(new URL('tokens.json', source));
await readFile(new URL('logos/firefly-koinon-lockup-color.svg', source));
await mkdir(destination, { recursive: true });
await cp(fileURLToPath(source), fileURLToPath(destination), { recursive: true });

const libraryDestination = new URL('../projects/koinon-angular/.brand/', import.meta.url);
await mkdir(libraryDestination, { recursive: true });
await cp(fileURLToPath(source), fileURLToPath(libraryDestination), { recursive: true });
const tokens = JSON.parse(await readFile(new URL('tokens.json', source), 'utf8'));
for (const key of [
  'charcoal',
  'paper',
  'amber',
  'ink',
  'muted',
  'gold',
  'stone',
  'line',
  'graphite',
  'white',
  'olive',
  'slate',
])
  if (!/^#[0-9a-f]{6}$/i.test(tokens.palette[key]))
    throw new Error(`Invalid canonical brand color: ${key}`);
const variables = [
  ...Object.entries(tokens.palette).map(([key, value]) => `  --ffk-${key}: ${value};`),
  ...Object.entries(tokens.themes).flatMap(([theme, values]) =>
    Object.entries(values).map(([key, value]) => `  --ffk-${theme}-${key}: ${value};`),
  ),
  `  --ffk-sidebar: ${tokens.layout.sidebar}px;`,
  `  --ffk-reading-max: ${tokens.layout.readingMax}px;`,
  `  --ffk-content-max: ${tokens.layout.contentMax}px;`,
  `  --ffk-gutter: ${tokens.layout.gutterDesktop}px;`,
  `  --ffk-gutter-mobile: ${tokens.layout.gutterMobile}px;`,
  `  --ffk-radius-control: ${tokens.radius.control}px;`,
  `  --ffk-radius-panel: ${tokens.radius.panel}px;`,
  `  --ffk-radius-dialog: ${tokens.radius.dialog}px;`,
];
const { writeFile } = await import('node:fs/promises');
await writeFile(
  new URL('../projects/koinon-angular/workbench/src/lib/_brand-tokens.generated.scss', import.meta.url),
  `// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0\n// Generated from canonical brand/tokens.json; do not edit.\n@mixin tokens {\n${variables.join('\n')}\n}\n`,
);

const legalDestination=new URL('../projects/koinon-angular/.legal/',import.meta.url);
await mkdir(legalDestination,{recursive:true});
for(const name of ['LICENSE','NOTICE'])await cp(fileURLToPath(new URL('../../'+name,import.meta.url)),fileURLToPath(new URL(name,legalDestination)));
