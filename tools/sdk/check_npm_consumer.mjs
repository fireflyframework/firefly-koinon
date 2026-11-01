// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {access, copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const archive = path.resolve(process.argv[2] ?? '');
assert.ok(process.argv[2], 'Pass the built npm archive');
await access(archive);
const sdkCheckDir = await mkdtemp(path.join(tmpdir(), 'koinon-sdk-consumer-'));
const consumer = path.join(sdkCheckDir, 'sdk/typescript');
function run(command, args) {
  const result = spawnSync(command, args, {cwd: consumer, stdio: 'inherit', timeout: 120_000});
  if (result.error) throw result.error;
  assert.equal(result.status, 0, 'Installed SDK consumer check failed');
}
try {
  await mkdir(path.join(consumer, 'test'), {recursive: true});
  await mkdir(path.join(sdkCheckDir, 'sdk/contract'), {recursive: true});
  await copyFile(path.join(repository, 'sdk/contract/operations.json'), path.join(sdkCheckDir, 'sdk/contract/operations.json'));
  await copyFile(path.join(repository, 'sdk/contract/fixtures.json'), path.join(sdkCheckDir, 'sdk/contract/fixtures.json'));
  await writeFile(path.join(consumer, 'package.json'), JSON.stringify({private: true, type: 'module'}));
  run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['install', '--ignore-scripts', '--no-audit', '--no-fund', archive]);
  const installed = path.join(consumer, 'node_modules/@fireflyframework/koinon-sdk');
  await writeFile(path.join(consumer, 'policy-consumer.ts'), `
import {KoinonClient,type OrganizationKnowledgeSettingsInput,type OrganizationKnowledgeSnapshot,type SearchResponse,type AnswerAudit} from '@fireflyframework/koinon-sdk';
declare const client:KoinonClient;
async function position(tenant:string){
 const page=await client.organizationPeople.list(tenant,{q:'Alex',page:1,page_size:25});
 const person=page.items.find(item=>item.id!==null);
 if(person?.id && person.revision!==undefined){
  return client.organizationPeople.update(tenant,person.id,{
   expected_revision:person.revision,job_title:'Knowledge Operations Lead',manager_id:null});
 }
}
// @ts-expect-error Positions cannot change authorization roles.
client.organizationPeople.update('north','person',{expected_revision:1,roles:['admin']});
async function policy(tenant:string){
 const current=await client.organizationKnowledge.get(tenant);
 const input:OrganizationKnowledgeSettingsInput={expected_revision:current.revision,documents:{...current.documents,answer_mode:'rag'},structured:current.structured};
 const saved=await client.organizationKnowledge.update(tenant,input);
 const bound:number=saved.capabilities.documents.bounds.rlm_max_iters.maximum;
 return bound;
}
function captured(response:SearchResponse,audit:AnswerAudit):OrganizationKnowledgeSnapshot|null|undefined{
 return response.knowledge_settings_snapshot??audit.knowledge_settings_snapshot;
}
// @ts-expect-error Knowledge behavior has organization scope, not workspace filters.
client.organizationKnowledge.get('north',{workspace_id:'workspace'});
// @ts-expect-error Updates require both complete policy objects.
client.organizationKnowledge.update('north',{expected_revision:0});
`);
  run(process.execPath,[path.join(repository,'sdk/typescript/node_modules/typescript/bin/tsc'),
    '--strict','--noEmit','--target','ES2022','--module','NodeNext','--moduleResolution','NodeNext','policy-consumer.ts']);
  for (const name of ['LICENSE', 'NOTICE']) {
    assert.deepEqual(await readFile(path.join(installed, name)), await readFile(path.join(repository, name)));
  }
  const files = (await readdir(path.join(repository, 'sdk/typescript/test'))).filter(name => name.endsWith('.test.mjs'));
  for (const name of files) {
    const source = await readFile(path.join(repository, 'sdk/typescript/test', name), 'utf8');
    const installedSource = source
      .replaceAll('../dist/index.js', '@fireflyframework/koinon-sdk')
      .replaceAll('../dist/communications.js', '@fireflyframework/koinon-sdk/communications');
    await writeFile(path.join(consumer, 'test', name), installedSource);
  }
  run(process.execPath, ['--test', ...files.map(name => path.join('test', name))]);
  console.log('Installed npm archive: contract tests and license notices passed.');
} finally {
  await rm(sdkCheckDir, {recursive: true, force: true});
}
