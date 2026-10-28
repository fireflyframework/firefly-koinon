// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonChatComposer } from '../../../../chat/page/src/composer/chat-composer';
async function mount() {
  TestBed.configureTestingModule({ imports: [KoinonChatComposer] });
  const fixture = TestBed.createComponent(KoinonChatComposer);
  fixture.componentRef.setInput('value', 'Review this knowledge');
  fixture.componentRef.setInput('canSend', true);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture;
}
it('sends on Enter while preserving composition and newline shortcuts', async () => {
  const fixture = await mount();
  let sent = 0;
  fixture.componentInstance.sendRequested.subscribe(() => ++sent);
  const input = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
  input.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true }),
  );
  input.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true }),
  );
  expect(sent).toBe(0);
  input.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }),
  );
  expect(sent).toBe(1);
  fixture.componentRef.setInput('running', true);
  fixture.detectChanges();
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  expect(sent).toBe(1);
});
it('forwards selected files and resets the picker for repeat selection', async () => {
  const fixture = await mount();
  fixture.componentRef.setInput('attachmentsEnabled', true);
  fixture.detectChanges();
  const batches: File[][] = [];
  fixture.componentInstance.filesSelected.subscribe((files) => batches.push(files));
  const file = new File(['Controlled knowledge'], 'notes.txt', { type: 'text/plain' });
  const input = fixture.nativeElement.querySelector('input[type=file]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: [file], configurable: true });
  input.dispatchEvent(new Event('change'));
  expect(batches).toEqual([[file]]);
  expect(input.value).toBe('');
});
it('claims file paste only when attachment capability is enabled', async () => {
  const fixture = await mount();
  const batches: File[][] = [];
  fixture.componentInstance.filesSelected.subscribe((files) => batches.push(files));
  const paste = () => {
    const event = new Event('paste', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { files: [new File(['test'], 'notes.txt')] },
    });
    fixture.nativeElement.querySelector('textarea').dispatchEvent(event);
    return event;
  };
  expect(paste().defaultPrevented).toBe(false);
  fixture.componentRef.setInput('attachmentsEnabled', true);
  fixture.detectChanges();
  expect(paste().defaultPrevented).toBe(true);
  expect(batches).toHaveLength(1);
});
it('toggles its context menu and restores the trigger on Escape', async () => {
  const fixture = await mount();
  fixture.componentRef.setInput('attachmentsEnabled', true);
  fixture.detectChanges();
  const trigger = fixture.nativeElement.querySelector('[aria-haspopup=menu]') as HTMLButtonElement;
  trigger.click();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.menuOpen()).toBe(true);
  trigger.click();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.menuOpen()).toBe(false);
  trigger.click();
  fixture.detectChanges();
  await fixture.whenStable();
  const menu = document.querySelector('[role=menu]')!;
  menu.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
  );
  fixture.detectChanges();
  expect(fixture.componentInstance.menuOpen()).toBe(false);
  expect(document.activeElement).toBe(trigger);
});
it('closes an open menu when disabled and prevents stale context actions', async () => {
  const fixture = await mount();
  fixture.componentRef.setInput('canChooseKnowledge', true);
  fixture.componentRef.setInput('canAddKnowledge', true);
  fixture.detectChanges();
  let requests = 0;
  fixture.componentInstance.libraryRequested.subscribe(() => ++requests);
  fixture.componentInstance.addKnowledgeRequested.subscribe(() => ++requests);
  fixture.nativeElement.querySelector('[aria-haspopup=menu]').click();
  fixture.detectChanges();
  expect(fixture.componentInstance.menuOpen()).toBe(true);
  fixture.componentRef.setInput('disabled', true);
  fixture.detectChanges();
  expect(fixture.componentInstance.menuOpen()).toBe(false);
  fixture.componentInstance.chooseKnowledge();
  fixture.componentInstance.addKnowledge();
  expect(requests).toBe(0);
});
it('closes its custom overlay on Tab without preventing normal focus navigation', async () => {
  const fixture = await mount();
  fixture.componentRef.setInput('attachmentsEnabled', true);
  fixture.detectChanges();
  fixture.nativeElement.querySelector('[aria-haspopup=menu]').click();
  fixture.detectChanges();
  await fixture.whenStable();
  const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
  document.querySelector('[role=menu]')!.dispatchEvent(event);
  fixture.detectChanges();
  expect(fixture.componentInstance.menuOpen()).toBe(false);
  expect(event.defaultPrevented).toBe(false);
});
