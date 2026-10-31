// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {KoinonClient,McpOAuthClientInput,McpOAuthClientPatch,McpOAuthClientRevision,McpOAuthClientReadiness,McpOAuthClientPage,McpOAuthClientCredential,McpOAuthClient,McpConnectionDescriptor,McpOAuthScope,McpOAuthClientFilter} from '../src/index.js';
export function typedOperations(client:KoinonClient){
 const scope:McpOAuthScope='catalog:read';
 const input:McpOAuthClientInput={name:'Research',client_type:'public',redirect_uris:['https://client.example/callback'],scopes:[scope]};
 const patch:McpOAuthClientPatch={expected_revision:1,enabled:false};
 const revision:McpOAuthClientRevision={expected_revision:2};
 const filter:McpOAuthClientFilter={status:'enabled',sort:'updated_at',order:'desc',page:1,page_size:25};
 const readiness:Promise<McpOAuthClientReadiness>=client.mcpOAuthClients.readiness('north');
 const list:Promise<McpOAuthClientPage>=client.mcpOAuthClients.list('north',{query:filter});
 const create:Promise<McpOAuthClientCredential>=client.mcpOAuthClients.create('north',input);
 const get:Promise<McpOAuthClient>=client.mcpOAuthClients.get('north','row');
 const update:Promise<McpOAuthClient>=client.mcpOAuthClients.update('north','row',patch);
 const rotate:Promise<McpOAuthClientCredential>=client.mcpOAuthClients.rotateSecret('north','row',revision);
 const global:Promise<McpConnectionDescriptor>=client.mcp.connection();
 const scoped:Promise<McpConnectionDescriptor>=client.mcp.organizationConnection('north');
 // @ts-expect-error Administrative scopes are outside the knowledge OAuth contract.
 const invalidScope:McpOAuthScope='identity:manage';
 // @ts-expect-error The registry filter has a closed status set.
 const invalidFilter:McpOAuthClientFilter={status:'active'};
 // @ts-expect-error A mutation always supplies the current revision.
 client.mcpOAuthClients.update('north','row',{enabled:false});
 // @ts-expect-error Client credentials are minted by the server, never input fields.
 client.mcpOAuthClients.create('north',{...input,client_secret:'injected'});
 return {readiness,list,create,get,update,rotate,global,scoped,invalidScope,invalidFilter};
}
