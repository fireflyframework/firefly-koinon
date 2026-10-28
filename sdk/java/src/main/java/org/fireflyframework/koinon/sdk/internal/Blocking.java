// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;

/** Keeps synchronous calls consistent with asynchronous error and interruption behavior. */
public final class Blocking {
  private Blocking() {}

  public static <T> T await(CompletableFuture<T> task) {
    try {
      return task.get();
    } catch (InterruptedException error) {
      task.cancel(true);
      Thread.currentThread().interrupt();
      throw new IllegalStateException("API request interrupted", error);
    } catch (ExecutionException error) {
      if (error.getCause() instanceof RuntimeException runtime) throw runtime;
      throw new IllegalStateException("API request failed", error.getCause());
    }
  }
}
