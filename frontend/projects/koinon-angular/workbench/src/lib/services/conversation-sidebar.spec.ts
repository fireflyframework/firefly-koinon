// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { KoinonConversationSidebar } from '../../../../chat/page/src/conversation-sidebar/conversation-sidebar';
function pendingSave(kind: 'create-folder' | 'rename-thread') {
  let resolve!: (value: unknown) => void;
  const response = new Promise<unknown>((settle) => {
    resolve = settle;
  });
  let tracked: Promise<void> | undefined;
  const dismiss = vi.fn(),
    emit = vi.fn();
  const sidebar = Object.assign(Object.create(KoinonConversationSidebar.prototype), {
    edit: () => ({
      kind,
      folder: null,
      thread: kind === 'rename-thread' ? { id: 'thread' } : null,
      revision: 4,
    }),
    canSave: () => true,
    formName: 'Reviewed name',
    tasks: {
      run: (callback: () => Promise<void>): void => {
        tracked = callback();
      },
    },
    s: { createFolder: () => response, renameThread: () => response },
    panel: { dismiss },
    threadChanged: { emit },
  }) as KoinonConversationSidebar;
  return { sidebar, resolve, dismiss, emit, settled: () => tracked };
}
it('closes the editor only after the tracked folder write completes', async () => {
  const state = pendingSave('create-folder');
  state.sidebar.save();
  expect(state.dismiss).not.toHaveBeenCalled();
  await Promise.resolve();
  expect(state.dismiss).not.toHaveBeenCalled();
  state.resolve({ id: 'created-folder' });
  await state.settled();
  expect(state.dismiss).toHaveBeenCalledOnce();
  expect(state.emit).not.toHaveBeenCalled();
});
it('emits the persisted thread before closing and keeps unsuccessful writes open', async () => {
  const state = pendingSave('rename-thread');
  state.sidebar.save();
  const thread = { id: 'thread', title: 'Reviewed name', revision: 5 };
  state.resolve(thread);
  await state.settled();
  expect(state.emit).toHaveBeenCalledWith(thread);
  expect(state.dismiss).toHaveBeenCalledOnce();
  expect(state.emit.mock.invocationCallOrder[0]).toBeLessThan(
    state.dismiss.mock.invocationCallOrder[0],
  );
  const failure = pendingSave('create-folder');
  failure.sidebar.save();
  failure.resolve(null);
  await failure.settled();
  expect(failure.dismiss).not.toHaveBeenCalled();
});

it('removes the active conversation only after a confirmed persisted deletion', async () => {
  for (const successful of [true, false]) {
    let resolve!: (value: boolean) => void;
    const response = new Promise<boolean>((settle) => { resolve = settle; });
    let tracked: Promise<void> | undefined;
    const emit = vi.fn(), dismiss = vi.fn();
    const sidebar = Object.assign(Object.create(KoinonConversationSidebar.prototype), {
      edit: () => ({ kind: 'delete-thread', folder: null, thread: { id: 'owned-thread' }, revision: 3 }),
      canSave: () => true,
      tasks: { run: (action: () => Promise<void>) => { tracked = action(); } },
      s: { deleteThread: () => response },
      threadChanged: { emit: vi.fn() },
      threadDeleted: { emit },
      panel: { dismiss },
    }) as KoinonConversationSidebar;
    sidebar.save();
    expect(emit).not.toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
    resolve(successful);
    await tracked;
    if (successful) {
      expect(emit).toHaveBeenCalledExactlyOnceWith('owned-thread');
      expect(dismiss).toHaveBeenCalledOnce();
    } else {
      expect(emit).not.toHaveBeenCalled();
      expect(dismiss).not.toHaveBeenCalled();
    }
  }
});
