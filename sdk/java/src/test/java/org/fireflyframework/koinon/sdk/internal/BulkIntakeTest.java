// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import javax.net.ssl.*;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.api.FileBatchesApi;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class BulkIntakeTest {
  static final class InertHttp extends HttpClient {
    final List<HttpRequest> requests = new ArrayList<>();
    final List<byte[]> bodies = new ArrayList<>();
    int status = 200;
    String response = "{}";
    Runnable beforeBody = () -> {};
    @Override public Optional<CookieHandler> cookieHandler(){return Optional.empty();}
    @Override public Optional<Duration> connectTimeout(){return Optional.empty();}
    @Override public Redirect followRedirects(){return Redirect.NEVER;}
    @Override public Optional<ProxySelector> proxy(){return Optional.empty();}
    @Override public SSLContext sslContext(){try{return SSLContext.getDefault();}catch(Exception error){throw new IllegalStateException(error);}}
    @Override public SSLParameters sslParameters(){return new SSLParameters();}
    @Override public Optional<Authenticator> authenticator(){return Optional.empty();}
    @Override public Version version(){return Version.HTTP_1_1;}
    @Override public Optional<Executor> executor(){return Optional.empty();}
    @Override public <T> HttpResponse<T> send(HttpRequest request,HttpResponse.BodyHandler<T> handler){throw new AssertionError("No real HTTP");}
    @Override public <T> CompletableFuture<HttpResponse<T>> sendAsync(HttpRequest request,HttpResponse.BodyHandler<T> handler,HttpResponse.PushPromiseHandler<T> push){return sendAsync(request,handler);}
    @SuppressWarnings("unchecked")
    @Override public <T> CompletableFuture<HttpResponse<T>> sendAsync(HttpRequest request,HttpResponse.BodyHandler<T> handler){
      requests.add(request);
      beforeBody.run();
      var received=new ByteArrayOutputStream();
      var completed=new CompletableFuture<byte[]>();
      request.bodyPublisher().ifPresentOrElse(publisher->publisher.subscribe(new Flow.Subscriber<ByteBuffer>(){
        public void onSubscribe(Flow.Subscription subscription){subscription.request(Long.MAX_VALUE);}
        public void onNext(ByteBuffer chunk){byte[] bytes=new byte[chunk.remaining()];chunk.get(bytes);received.writeBytes(bytes);}
        public void onError(Throwable error){completed.completeExceptionally(error);}
        public void onComplete(){completed.complete(received.toByteArray());}
      }),()->completed.complete(new byte[0]));
      bodies.add(completed.join());
      HttpResponse<InputStream> result=new HttpResponse<>(){
        public int statusCode(){return status;}
        public HttpRequest request(){return request;}
        public Optional<HttpResponse<InputStream>> previousResponse(){return Optional.empty();}
        public HttpHeaders headers(){return HttpHeaders.of(Map.of(),(a,b)->true);}
        public InputStream body(){return new ByteArrayInputStream(response.getBytes(StandardCharsets.UTF_8));}
        public Optional<SSLSession> sslSession(){return Optional.empty();}
        public URI uri(){return request.uri();}
        public Version version(){return Version.HTTP_1_1;}
      };
      return CompletableFuture.completedFuture((HttpResponse<T>)result);
    }
  }

  @Test void elevenOperationsUseExplicitScopeRevisionsAndExactRawBytes() throws Exception {
    var http=new InertHttp();var tokens=new AtomicInteger();
    try(var transport=new Transport(URI.create("https://inert.test/api/v1"),http,false,
        ()->"fresh-"+tokens.incrementAndGet(),new JsonCodec())){
      var api=new FileBatchesApi(transport,"north/office");var action=new BulkAction(7);
      api.capabilities(new FileBatchScope("workspace"));
      api.create(FileBatchCreate.empty(),"create-key");api.list(new FileBatchFilter(2,3));
      api.get("batch/one");api.items("batch/one",new FileBatchFilter(2,3));
      byte[] source={1,2,3};var upload=new BulkFileUpload(source);source[0]=9;
      api.upload("batch/one","item/one",upload,"upload-key");
      api.receipt("batch/one","item/one");api.submit("batch/one",action,"submit-key");
      api.cancel("batch/one",action,"cancel-key");api.reconcile("batch/one","item/one",action,"inspect-key");
      new FileBatchesApi(transport,"south").recoverOriginal("batch/one","item/one",action,"original-key");
      assertEquals(11,http.requests.size());assertEquals(11,tokens.get());
      assertTrue(http.requests.get(5).uri().getRawPath().contains("north%2Foffice/sources/batches/batch%2Fone/items/item%2Fone/content"));
      assertEquals("application/octet-stream",http.requests.get(5).headers().firstValue("Content-Type").orElseThrow());
      assertEquals("upload-key",http.requests.get(5).headers().firstValue("Idempotency-Key").orElseThrow());
      assertArrayEquals(new byte[]{1,2,3},http.bodies.get(5));
      assertEquals("{\"expected_revision\":7}",new String(http.bodies.get(10),StandardCharsets.UTF_8));
      assertTrue(http.requests.get(10).uri().getRawPath().contains("/tenants/south/"));
    }
  }

  @Test void unknownMutationHasOneDispatchAndImmutableUploadBounds() {
    var http=new InertHttp();http.status=503;http.response="{\"code\":\"BULK_NATIVE_OUTCOME_UNRESOLVED\"}";
    try(var transport=new Transport(URI.create("https://inert.test/api/v1"),http,false,()->"token",new JsonCodec())){
      var api=new FileBatchesApi(transport,"north");
      assertThrows(ApiException.class,()->api.submit("batch",new BulkAction(1),"stable-key"));
      assertEquals(1,http.requests.size());
      assertThrows(IllegalArgumentException.class,()->new BulkFileUpload(new byte[0]));
    }
  }

  @Test void verifiedPathUploadUsesFilePublisherAndRejectsChangedManifest(
      @org.junit.jupiter.api.io.TempDir java.nio.file.Path directory) throws Exception {
    var file = directory.resolve("evidence.xlsx");
    java.nio.file.Files.writeString(file, "evidence");
    var digest = java.util.HexFormat.of().formatHex(
        java.security.MessageDigest.getInstance("SHA-256").digest("evidence".getBytes(StandardCharsets.UTF_8)));
    var http = new InertHttp();
    http.response = "{\"receipt_id\":\"receipt\",\"batch_id\":\"batch\",\"item_id\":\"item\","
        + "\"sha256\":\"" + digest + "\",\"size_bytes\":8,\"status\":\"staged\"}";
    try (var transport = new Transport(URI.create("https://inert.test/api/v1"), http, false,
        () -> "current-token", new JsonCodec())) {
      var api = new FileBatchesApi(transport, "north/office");
      var original = new BulkFilePath(file, 8, digest);
      assertEquals(8, api.uploadPath("batch", "item", original, "file-key").sizeBytes());
      assertEquals(8, api.uploadPathAsync("batch", "item", original, "file-key").join().sizeBytes());
      assertEquals(2, http.requests.size());
      assertArrayEquals("evidence".getBytes(StandardCharsets.UTF_8), http.bodies.getFirst());
      assertEquals(8, http.requests.getFirst().bodyPublisher().orElseThrow().contentLength());
      assertEquals("file-key", http.requests.getFirst().headers().firstValue("Idempotency-Key").orElseThrow());
      java.nio.file.Files.writeString(file, "changed!");
      assertThrows(IllegalArgumentException.class, () -> api.uploadPath("batch", "item", original, "file-key"));
      assertEquals(2, http.requests.size());
    }
  }

  @Test void sourceReplacementAfterPreparationCannotChangeThePublishedBody(
      @org.junit.jupiter.api.io.TempDir java.nio.file.Path directory) throws Exception {
    var file = directory.resolve("evidence");
    java.nio.file.Files.writeString(file, "evidence");
    var digest = java.util.HexFormat.of().formatHex(
        java.security.MessageDigest.getInstance("SHA-256").digest("evidence".getBytes(StandardCharsets.UTF_8)));
    var http = new InertHttp();
    http.beforeBody = () -> {
      try { java.nio.file.Files.writeString(file, "changed!"); }
      catch (IOException error) { throw new UncheckedIOException(error); }
    };
    try (var transport = new Transport(URI.create("https://inert.test/api/v1"), http, false,
        () -> "token", new JsonCodec())) {
      new FileBatchesApi(transport, "north").uploadPath(
          "batch", "item", new BulkFilePath(file, 8, digest), "key");
      assertArrayEquals("evidence".getBytes(StandardCharsets.UTF_8), http.bodies.getFirst());
      assertEquals("changed!", java.nio.file.Files.readString(file));
    }
  }
}
