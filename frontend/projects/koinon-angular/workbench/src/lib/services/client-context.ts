// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {Injectable,inject,signal} from '@angular/core';
import type {KoinonClient,KoinonTransport} from '@fireflyframework/koinon-sdk';
import {KOINON_CLIENT,KOINON_TRANSPORT} from '../client-provider';
@Injectable({providedIn:'root'})
export class KoinonClientContext{
 private client=inject(KOINON_CLIENT,{optional:true});
 private readonly transport=signal(inject(KOINON_TRANSPORT,{optional:true}));
 readonly revision=signal(0);
 bind(client:KoinonClient,transport?:KoinonTransport|null){this.transport.set(transport!==undefined?transport:this.client===client?this.transport():null);this.client=client;this.revision.update(x=>x+1);}
 getTransport():KoinonTransport|null{return this.transport();}
 get():KoinonClient{if(!this.client)throw new Error('The host application has not connected this workspace. Contact the application owner.');return this.client;}
}
