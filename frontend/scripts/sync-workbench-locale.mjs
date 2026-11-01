// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import ts from 'typescript';
const root = resolve('projects/koinon-angular');
function dictionary(file) {
  const text = readFileSync(file, 'utf8'),
    source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const imports = new Map();
  for (const statement of source.statements)
    if (ts.isImportDeclaration(statement)) {
      for (const item of statement.importClause.namedBindings.elements)
        imports.set(item.name.text, resolve(dirname(file), statement.moduleSpecifier.text + '.ts'));
    }
  const declaration = source.statements.find((s) => ts.isVariableStatement(s)).declarationList
    .declarations[0];
  const result = {};
  for (const property of declaration.initializer.properties) {
    if (ts.isSpreadAssignment(property))
      Object.assign(result, dictionary(imports.get(property.expression.text)));
    else result[property.name.text] = property.initializer.text;
  }
  return result;
}
function sources(path, panels = false) {
  return readdirSync(path, { withFileTypes: true }).flatMap((item) =>
    item.isDirectory()
      ? sources(resolve(path, item.name), panels)
      : !item.name.endsWith('.spec.ts') &&
          !['workbench-spanish.generated.ts', 'panel-spanish.generated.ts'].includes(item.name) &&
          /^(account-(?:panel|page)|authorized-applications(?:-panel)?|mcp-connection-panel|workbench-dialogs|move-folder|table-lineage-panel|table-coordinates)\./.test(
            item.name,
          ) === panels &&
          item.name !== 'assistant.ts' &&
          /\.(ts|html)$/.test(item.name)
        ? [readFileSync(resolve(path, item.name), 'utf8')]
        : [],
  );
}
const all = dictionary(resolve(root, 'src/lib/foundations/spanish.ts'));
const content = sources(resolve(root, 'workbench/src/lib')).join('\n');
const selected = Object.fromEntries(
  Object.entries(all).filter(
    ([key]) => content.includes(key) || content.includes(key.replaceAll("'", "\\'")),
  ),
);
const output =
  '// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0\n// Library vocabulary. Regenerate with npm run sync:locale after editing the canonical Spanish dictionaries.\nexport const WORKBENCH_SPANISH:Readonly<Record<string,string>>=' +
  JSON.stringify(selected, null, 2) +
  ';\n';
const target = resolve(root, 'workbench/src/lib/foundations/workbench-spanish.generated.ts');
const panelContent = sources(resolve(root, 'workbench/src/lib'), true).join('\n');
const panelSelected = Object.fromEntries(
  Object.entries(all).filter(
    ([key]) => panelContent.includes(key) || panelContent.includes(key.replaceAll("'", "\\'")),
  ),
);
const panelOutput =
  '// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0\n// Panel vocabulary. Regenerate with npm run sync:locale.\nexport const PANEL_SPANISH:Readonly<Record<string,string>>=' +
  JSON.stringify(panelSelected, null, 2) +
  ';\n';
const panelTarget = resolve(root, 'workbench/src/lib/foundations/panel-spanish.generated.ts');
if (process.argv.includes('--check')) {
  if (readFileSync(panelTarget, 'utf8') !== panelOutput)
    throw new Error('Panel Spanish vocabulary is stale.');
} else writeFileSync(panelTarget, panelOutput);
if (process.argv.includes('--check')) {
  if (readFileSync(target, 'utf8') !== output)
    throw new Error('Workbench Spanish vocabulary is stale. Run npm run sync:locale.');
} else writeFileSync(target, output);
console.log(
  `${Object.keys(selected).length} Library translations (${Buffer.byteLength(output)} bytes source)`,
);
