// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ChatApi } from "./chat-api.js";
import type { KoinonTransport } from "./transport.js";
export function createLazyChatApi(transport: KoinonTransport): ChatApi {
  let pending: Promise<ChatApi> | undefined;
  const load = () =>
    (pending ??= import("./chat-api.js").then(
      (module) => module.createChatApi(transport),
      (error: unknown) => {
        pending = undefined;
        throw error;
      },
    ));
  const delegate =
    <Args extends unknown[], Result>(
      select: (api: ChatApi) => (...args: Args) => Promise<Result>,
    ) =>
    async (...args: Args): Promise<Result> =>
      select(await load())(...args);
  return {
    proposals: {
      get: delegate((api) => api.proposals.get),
      confirm: delegate((api) => api.proposals.confirm),
      cancel: delegate((api) => api.proposals.cancel),
    },
    audit: delegate((api) => api.audit),
    activities: delegate((api) => api.activities),
    attachments: {
      promote: delegate((api) => api.attachments.promote),
      capabilities: delegate((api) => api.attachments.capabilities),
      upload: (...args: Parameters<ChatApi["attachments"]["upload"]>) => {
        const file = args[2],
          filename =
            args[4]?.filename ??
            ("name" in file && typeof file.name === "string"
              ? file.name
              : undefined);
        if (!filename)
          throw new Error(
            "A replacement filename with its supported extension is required",
          );
        return delegate((api) => api.attachments.upload)(...args);
      },
      list: delegate((api) => api.attachments.list),
      get: delegate((api) => api.attachments.get),
      original: delegate((api) => api.attachments.original),
      chunks: delegate((api) => api.attachments.chunks),
      cancel: delegate((api) => api.attachments.cancel),
      retry: delegate((api) => api.attachments.retry),
      remove: delegate((api) => api.attachments.remove),
    },
    get: delegate((api) => api.get),
    update: delegate((api) => api.update),
    delete: delegate((api) => api.delete),
    suggestTitle: delegate((api) => api.suggestTitle),
    folders: {
      get: delegate((api) => api.folders.get),
      list: delegate((api) => api.folders.list),
      create: delegate((api) => api.folders.create),
      update: delegate((api) => api.folders.update),
      delete: delegate((api) => api.folders.delete),
    },
    threads: delegate((api) => api.threads),
    create: delegate((api) => api.create),
    messages: delegate((api) => api.messages),
    submit: delegate((api) => api.submit),
    events: (...args: Parameters<ChatApi["events"]>) => {
      const cursor = args[2]?.lastEventId;
      if (cursor !== undefined && /[\r\n\0]/.test(cursor))
        throw new Error("Last-Event-ID cannot contain line breaks or NUL");
      return (async function* () {
        yield* (await load()).events(...args);
      })();
    },
    cancel: delegate((api) => api.cancel),
    retry: delegate((api) => api.retry),
    result: delegate((api) => api.result),
  };
}
