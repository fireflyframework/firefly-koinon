// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ExternalReviewsApi } from './external-reviews.js';
import type { KoinonTransport } from './transport.js';

export function createLazyExternalReviewsApi(transport: KoinonTransport): ExternalReviewsApi {
  let pending: Promise<ExternalReviewsApi> | undefined;
  const load = () => pending ??= import('./external-reviews.js').then(
    module => module.createExternalReviewsApi(transport),
    (error: unknown) => { pending = undefined; throw error; },
  );
  const delegate = <Args extends unknown[], Result>(
    select: (api: ExternalReviewsApi) => (...args: Args) => Promise<Result>,
  ) => async (...args: Args): Promise<Result> => select(await load())(...args);
  return {
    externalReviews: {
      stage: delegate(api => api.externalReviews.stage),
      get: delegate(api => api.externalReviews.get),
      approve: delegate(api => api.externalReviews.approve),
      cancel: delegate(api => api.externalReviews.cancel),
    },
    externalFileReviews: {
      cleanup: delegate(api => api.externalFileReviews.cleanup),
      stage: delegate(api => api.externalFileReviews.stage),
      get: delegate(api => api.externalFileReviews.get),
      chunk: delegate(api => api.externalFileReviews.chunk),
      seal: delegate(api => api.externalFileReviews.seal),
      approve: delegate(api => api.externalFileReviews.approve),
      cancel: delegate(api => api.externalFileReviews.cancel),
    },
  };
}
