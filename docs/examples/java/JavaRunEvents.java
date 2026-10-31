// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.StreamEvent;

public final class JavaRunEvents {
    public static void observe(KoinonClient client, String tenant, String runId,
            String lastProcessedId, Consumer<StreamEvent> process,
            Consumer<String> saveCursor) throws Exception {
        var options = RequestOptions.defaults();
        if (lastProcessedId != null) options = options.lastEventId(lastProcessedId);
        var terminal = new CompletableFuture<Void>();
        try (var stream = client.chat(tenant).events(runId, options)) {
            stream.subscribe(new Flow.Subscriber<StreamEvent>() {
                private Flow.Subscription subscription;
                public void onSubscribe(Flow.Subscription value) {
                    subscription = value;
                    value.request(1);
                }
                public void onNext(StreamEvent event) {
                    try {
                        process.accept(event);
                        if (event.id() != null) saveCursor.accept(event.id());
                        if ("completed".equals(event.type())) terminal.complete(null);
                        else if ("failed".equals(event.type()) || "cancelled".equals(event.type())) {
                            terminal.completeExceptionally(new IOException("Run ended: " + event.type()));
                        }
                    } catch (RuntimeException error) {
                        terminal.completeExceptionally(error);
                    }
                    if (terminal.isDone()) subscription.cancel();
                    else subscription.request(1);
                }
                public void onError(Throwable error) { terminal.completeExceptionally(error); }
                public void onComplete() {
                    if (!terminal.isDone()) terminal.completeExceptionally(
                        new IOException("Stream ended without a terminal event"));
                }
            });
            try {
                terminal.get(180, TimeUnit.SECONDS);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                throw error;
            }
        }
    }
}
