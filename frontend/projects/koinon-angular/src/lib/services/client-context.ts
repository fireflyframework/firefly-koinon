// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {Injectable,inject,signal} from '@angular/core';
import type {KoinonClient} from '@fireflyframework/koinon-sdk';
import {KOINON_CLIENT} from '../client-provider';
@Injectable({providedIn:'root'})
export class KoinonClientContext{
 private client=inject(KOINON_CLIENT,{optional:true});
 readonly revision=signal(0);
 bind(client:KoinonClient){this.client=client;this.revision.update(x=>x+1);}
 get():KoinonClient{if(!this.client)throw new Error('The host application has not connected this workspace. Contact the application owner.');return this.client;}
}
