// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

/** An HTTP problem returned by the API, with its native request reference. */
public final class ApiException extends RuntimeException {
  private static final long serialVersionUID = 1L;
  private final int status;
  private final String code;
  private final String requestId;

  public ApiException(int status, String code, String message, String requestId) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }

  public int status() {
    return status;
  }

  public String code() {
    return code;
  }

  public String requestId() {
    return requestId;
  }
}
