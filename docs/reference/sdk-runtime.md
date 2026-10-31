<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# SDK runtime reference

Use this reference for client configuration, request options and helpers that sit around the [canonical API operations](api/index.md). For a complete working task, use the [Python](../guides/headless-python.md), [TypeScript](../guides/headless-typescript.md) or [Java](../guides/headless-java.md) guide. The [wire model index](models/index.md) describes payloads; transport objects such as downloads and event streams also carry language-specific resource ownership.

## Client configuration

=== "Python"

    Import `KoinonClient` from `koinon_sdk`. It is asynchronous and accepts these constructor arguments.

    | Argument | Type | Behavior |
    | --- | --- | --- |
    | `base_url` | `str` | API base address. The client normalizes its trailing slash. |
    | `token_provider` | Callable returning `str` or an awaitable string | Required keyword argument. Called for every request so credentials can rotate. Empty tokens are rejected. |
    | `transport` | `httpx.AsyncBaseTransport` or `None` | Optional HTTPX transport, including an in-process test transport. |
    | `timeout` | `float` | Defaults to 30 seconds. Passed to the owned HTTPX client. |

    Use `async with` or call `await client.aclose()`. Closing releases the owned HTTPX client, including its configured transport. Redirect following is disabled. Keep the client open while consuming its streams.

=== "TypeScript"

    Construct `KoinonClient` with a `KoinonTransport`. The supplied `FetchTransport` accepts `FetchTransportOptions`.

    | Option | Type | Behavior |
    | --- | --- | --- |
    | `baseUrl` | `string` | Required API base address. Resource methods supply relative paths. |
    | `accessToken` | Function returning a nullable string or its promise | Called for each request. A supplied bearer token takes precedence over session CSRF handling. |
    | `csrfToken` | Function returning a nullable string or its promise | Used for non-GET requests when no bearer token is supplied. |
    | `credentials` | `RequestCredentials` | Defaults to `include`. Choose appropriately for the host's session boundary. |
    | `fetch` | `typeof globalThis.fetch` | Optional custom Fetch implementation. |

    `FetchTransport` rejects absolute resource paths and redirects. It does not expose a client close method. The caller owns request abort signals and any object URLs it creates from returned blobs. The `KoinonTransport` interface supports typed `request` and `stream` methods for custom host integration.

=== "Java"

    Start with `KoinonClient.builder(URI)`. The builder validates an absolute HTTP or HTTPS API address without credentials, query parameters or a fragment.

    | Builder method | Argument | Behavior |
    | --- | --- | --- |
    | `bearerToken` | `Supplier<String>` | Retrieves the current credential for each request. |
    | `httpClient` | `HttpClient` | Optional caller-owned HTTP client. Its redirect policy must be `NEVER`. |
    | `connectTimeout` | `Duration` | Positive connection timeout; defaults to 10 seconds for an internally created client. |
    | `build` | None | Creates the typed client. |

    `KoinonClient` implements `AutoCloseable`. Use try-with-resources or call `close()`. Closing cancels tracked requests and releases open streams. The SDK closes an HTTP client it created; a caller-supplied HTTP client remains the caller's responsibility.

Authentication does not grant additional permissions. Credentials remain subject to current membership, scopes, expiry and resource bounds. See [API permissions and writes](../guides/api-permissions.md). Configure credentials through a secret provider; avoid putting them in source code or URLs.

## Request options and typed filters

Use each operation's typed filter for supported query fields. Do not infer filters from another list endpoint. Omitting a field, sending `null` and sending an empty string can have different meanings; the [model reference](models/index.md) preserves those differences.

### Python

Python methods expose endpoint-specific keyword arguments and named input/filter models. There is no shared public `RequestOptions` object. The API-area pages record the wire parameter names; consult the language workflow for the Python method signature. HTTP timeouts are configured on the client. Standard asynchronous task cancellation applies to an awaited request.

### TypeScript

Methods that accept `RequestOptions` forward its `signal` and operation-appropriate headers through the transport. Resource methods set their own body, response type and typed filter query values; use their declared arguments rather than trying to replace those values through generic options.

| Property | Type | Purpose |
| --- | --- | --- |
| `signal` | `AbortSignal` | Abort an in-flight request or stream. |
| `headers` | `Record<string, string>` | Operation-appropriate HTTP headers. |
| `query` | Record of string, number, boolean or undefined values | Generic transport query values; undefined values are omitted. Resource helpers may replace this with their typed filter. |
| `body` | `unknown` | Generic transport payload. JSON is serialized; `FormData` and `Blob` pass through. Resource helpers normally supply this. |
| `responseType` | `json`, `blob` or `download` | Generic transport response handling. Resource helpers choose the correct type. |

The transport sets `Authorization` from its current token callback and JSON `Content-Type` when it serializes a JSON body. Avoid manually setting a multipart boundary: let Fetch encode `FormData`.

### Java

`RequestOptions` is immutable. Each helper returns a new options value. `defaults()` uses empty query/header maps and a 30-second request timeout. Its constructor defensively copies maps and rejects a non-positive timeout.

| Method | Purpose |
| --- | --- |
| `query(name, value)` | Adds a string, long or boolean query value; a null string removes the key. Prefer the operation's typed filter where available. |
| `header(name, value)` | Adds an explicit header. |
| `timeout(Duration)` | Sets a positive per-request timeout. |
| `idempotencyKey(value)` | Sets `Idempotency-Key` for an operation that declares it. |
| `lastEventId(value)` | Sets the last fully processed opaque stream event ID; rejects null and line-break/NUL characters. |
| `ifMatch(value)` | Sets `If-Match`. High-level content methods accept and quote the revision using their declared precondition argument. |
| `documentRevision(sourceVersionId, extractionId)` | Sets paired source-version and extraction UUID headers. Supplying only one is rejected. |

Resource APIs provide synchronous methods and asynchronous overloads returning `CompletableFuture`. Cancel an asynchronous future to cancel its transport request. A request timeout or lost response does not prove that a write was rolled back; use the operation's idempotency or revision protocol before deciding what to do next.

## Exact numeric values

Opaque JSON does not silently convert application numbers to another type. Use these explicit helpers before putting exact values into JSON cells. Integers within the inclusive range from `-9007199254740991` to `9007199254740991` can be emitted as JSON numbers; larger integers are emitted as decimal strings.

| Language | Helper | Input and result |
| --- | --- | --- |
| Python | `exact_integer` | Accepts an `int`, rejects booleans and implicit coercion; returns an `int` in the safe range or an exact string outside it. |
| Python | `exact_decimal` | Accepts a finite `decimal.Decimal`; returns a plain decimal string. Binary floats are rejected. |
| TypeScript | `exactInteger` | Accepts a `bigint`; returns a number in the safe range or an exact string outside it. |
| TypeScript | `exactDecimal` | Accepts a plain finite decimal string with an optional sign and fractional part. Whitespace and exponent notation are rejected. Returns the original string. |
| Java | `ExactValues.integer` | Accepts `BigInteger`; returns a numeric or text `JsonNode` according to the safe range. |
| Java | `ExactValues.decimal` | Accepts `BigDecimal`; returns a text node using `toPlainString()`. |
| Java | `ExactValues.integerValue` | Reads an integer numeric or text node into `BigInteger`; rejects fractional or non-numeric values. |
| Java | `ExactValues.decimalValue` | Reads a numeric or text node into `BigDecimal`, including valid exponent notation; rejects null and non-numeric values. |

An exact numeric string remains a string on the wire. Only convert it back where the business schema calls for a number. Construct decimals from exact source text, rather than converting a rounded binary floating-point value.

## Pagination

The fetch callback owns the endpoint, tenant, typed filters and page size. Helpers fetch lazily and do not retry writes or invent a server total.

| Language | Numbered pages | Cursor pages | Yielded value |
| --- | --- | --- | --- |
| Python | `offset_pages(fetch, first_page=1)` | `cursor_pages(fetch)` | Complete `Page[T]` objects. |
| TypeScript | `offsetPages(fetch, firstPage=1, signal?)` | `cursorPages(fetch, signal?)` | Complete `Page<T>` objects. |
| Java | `Pages.numbered(fetch, firstPage)` | `Pages.cursor(fetch)` | Items of type `T`, through a lazy `Iterable<T>`. |

Numbered helpers reject an invalid first page or an inconsistent returned page number. Python and TypeScript stop when the server does not provide enough page metadata to determine the next page. Java also uses returned item count and size when available. Cursor helpers start without a cursor, use the next opaque server cursor and reject repeated cursors. TypeScript passes its abort signal to the callback and checks it between pages.

See the pagination examples in the language guides. Retained glossary lists use their own offset/limit/has-more contract; do not substitute a numbered-page assumption.

## Downloads and file ownership

| Language | Result | Ownership |
| --- | --- | --- |
| Python | `BinaryDownload` with `content`, `content_type`, `etag`, `filename`, `not_modified` | Bytes are already read. Save them explicitly to a caller-controlled location. |
| TypeScript | `BinaryDownload` with `blob`, `content_type`, `etag`, `filename`, `not_modified` | The caller owns any blob URL it creates and must revoke it when no longer needed. |
| Java | `BinaryResponse` with `content()`, `contentType()`, `etag()`, `filename()`, `notModified()` | Byte arrays are defensively copied. |
| Java | `FileDownload` from supported `download…` resource helpers | The caller supplies a target path and byte limit. Existing files are not overwritten. The completed result records path, byte count and response metadata. |

Inspect `not_modified` or `notModified()` before replacing cached content after a conditional avatar request. The returned filename is metadata, not a trusted filesystem path. Preserve a document's source version and extraction identity when you need reproducible provenance; downloading its current original is a separate operation from downloading a particular retained version.

## Event streams and cancellation

Python `EventStream` is an asynchronous iterator and context manager; close it with `aclose()` when stopping early. TypeScript transport streams are async iterables; finishing iteration or aborting releases the reader. Java `EventStream<T>` is an `AutoCloseable`, single-subscriber `Flow.Publisher<T>` with demand-aware delivery; close it or cancel its subscription to release the HTTP body.

All three parsers bound an SSE frame to 1 MiB. Preserve opaque event IDs and resume only after the last fully processed event, using the operation's declared resumption argument/header. The parser does not automatically reconnect or decide whether an application event has been processed successfully.

Closing a stream or cancelling an HTTP request releases that connection. It does not cancel a durable chat run or job. Use the corresponding [chat](api/chat.md) or [job](api/platform.md) cancellation operation when the intention is to stop server work. See [Python conversations](../guides/python-conversations.md), [TypeScript conversations](../guides/typescript-conversations.md) and [Java conversations](../guides/java-conversations.md) for complete run and stream workflows.

## Errors and request references

| Language | Error type | Available fields |
| --- | --- | --- |
| Python | `ApiError` | `status`, `code`, `request_id` and the compatibility alias `transaction_id`; message through the exception. |
| TypeScript | `KoinonError` | `status`, `code`, `requestId`, `problem` and the error message. |
| Java | `ApiException` | `status()`, `code()`, `requestId()` and `getMessage()`. |

Keep the request reference when reporting a problem; redact credentials and sensitive payloads. Local argument, parsing and transport failures can be ordinary language/runtime exceptions rather than API errors. Operation pages list declared success statuses, not an exhaustive error catalog. The server remains authoritative for authorization, revision conflicts and resource visibility.
