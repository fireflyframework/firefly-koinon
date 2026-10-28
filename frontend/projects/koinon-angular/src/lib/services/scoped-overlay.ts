// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {ElementRef,Injectable,inject} from '@angular/core';
import {OverlayContainer} from '@angular/cdk/overlay';
@Injectable()
export class KoinonOverlayContainer extends OverlayContainer {
 private readonly host=inject<ElementRef<HTMLElement>>(ElementRef);
 protected override _createContainer():void{
  const root=this.host.nativeElement.shadowRoot;
  if(!root)throw new Error('The embedded dialog requires its own shadow root.');
  const style=this._document.createElement('style');
  style.textContent='.cdk-overlay-container{position:fixed;inset:0;z-index:1000;pointer-events:none}.cdk-global-overlay-wrapper{display:flex;position:absolute;inset:0;pointer-events:none}.cdk-overlay-pane{position:absolute;pointer-events:auto;box-sizing:border-box;max-width:100%;max-height:100%}.cdk-overlay-backdrop{position:absolute;inset:0;pointer-events:auto;-webkit-tap-highlight-color:transparent;background:#10110f66}.koinon-dialog-pane{max-height:calc(100dvh - 40px);max-width:calc(100vw - 40px)}';
  this._containerElement=this._document.createElement('div');
  this._containerElement.classList.add('cdk-overlay-container');
  this._containerElement.appendChild(style);root.appendChild(this._containerElement);
 }
 protected override _loadStyles():void{
  // The default CDK loader would inject global styles into the embedding application.
 }
}
