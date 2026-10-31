<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java tutorial source

Use JDK 21 or later. These complete classes accompany the four Java chapters. Download the classes you need together; `TutorialMain` uses `JavaHistory`, while the other helpers are explicitly invoked by your host. None uses a web framework or imports the backend.

| Chapter | Complete source files |
| --- | --- |
| Setup | [JavaQuickstart.java](JavaQuickstart.java), [TutorialMain.java](TutorialMain.java) |
| Knowledge | [JavaIntake.java](JavaIntake.java), [JavaContentChanges.java](JavaContentChanges.java), [JavaHistory.java](JavaHistory.java), [JavaCuratedKnowledge.java](JavaCuratedKnowledge.java), [JavaKnowledgeReads.java](JavaKnowledgeReads.java) |
| Conversations | [JavaRuns.java](JavaRuns.java), [JavaRunEvents.java](JavaRunEvents.java), [JavaReviewedActions.java](JavaReviewedActions.java) |
| Administration | [JavaOrganizationSettings.java](JavaOrganizationSettings.java), [JavaOrganizationDirectory.java](JavaOrganizationDirectory.java), [JavaAdministration.java](JavaAdministration.java), [JavaAsyncReads.java](JavaAsyncReads.java), [JavaOriginalDownload.java](JavaOriginalDownload.java) |

Use your operator's verified SDK JAR and its declared Jackson dependencies. `KOINON_SDK_CLASSPATH` is a platform-appropriate classpath containing that JAR, Jackson databind/core/annotations and the Java-time module at the SDK POM's qualified versions. It is not a URL or a credential. A Maven host can obtain those dependencies from the SDK's published/source POM; a local JAR alone does not establish Maven Central publication.

The following commands use the Unix classpath separator. On Windows, use `;` where the classpath is combined.

```sh
mkdir -p classes
javac --release 21 -Xlint:all -Werror \
  -cp "$KOINON_SDK_CLASSPATH" -d classes *.java
java -cp "classes:$KOINON_SDK_CLASSPATH" JavaQuickstart
```

Set `KOINON_API_URL`, `KOINON_TOKEN`, `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` through your secret environment. The API root ends in `/api/v1`. The bearer supplier is evaluated for each request and must return a current API credential, never a provider key or an ID token.

`TutorialMain` provides explicit read-only chapter entry points:

```sh
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain context
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain history
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain threads
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain people
```

History also needs an authorized `KOINON_DOCUMENT_ID`. Each command has its current API scope/resource requirements: context/catalog observation, document history, owner chat state or self profile/tenant projection. A denied command does not justify widening every token scope.

The helper classes contain explicit writes, but these entry points never call them. Supply actual reviewed state and a person decision in your own host. Save a thread before submitting a run; do not use `JavaRuns.submit` as a retry routine because its convenience example creates a thread. `JavaRunEvents` requires host-owned presentation processing and durable checkpoint callbacks. Preserve state/cursor consistency and do not confirm proposals from an event callback.

Keep `KoinonClient` and streams open for their intended lifetime, then close them. The host owns an injected HTTP client. A cancelled future releases its HTTP operation without proving a server mutation rolled back. Bound downloads, retain original operation identities and reconcile unknown outcomes.

Return to [Java setup](../../guides/headless-java.md).
