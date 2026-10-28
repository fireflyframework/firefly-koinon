// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ElementRef, Injector, type TemplateRef, type ViewContainerRef } from '@angular/core';
import { Overlay, OverlayContainer } from '@angular/cdk/overlay';
import { TemplatePortal } from '@angular/cdk/portal';
import { KoinonOverlayContainer } from './scoped-overlay';

export function createDialogOverlay(parent: Injector, host: ElementRef<HTMLElement>) {
  const injector = Injector.create({
    parent,
    providers: [
      Overlay,
      { provide: OverlayContainer, useClass: KoinonOverlayContainer },
      { provide: ElementRef, useValue: host },
    ],
  });
  const overlay = injector.get(Overlay);
  return {
    open(tree: boolean, template: TemplateRef<unknown>, view: ViewContainerRef) {
      const ref = overlay.create({
        hasBackdrop: true,
        positionStrategy: tree
          ? overlay.position().global().left('0').top('0')
          : overlay.position().global().centerHorizontally().centerVertically(),
        scrollStrategy: overlay.scrollStrategies.noop(),
        panelClass: tree ? 'koinon-tree-pane' : 'koinon-dialog-pane',
      });
      ref.attach(new TemplatePortal(template, view));
      return ref;
    },
    destroy() {
      injector.destroy();
    },
  };
}
