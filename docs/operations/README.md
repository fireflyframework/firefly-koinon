# Operations

firefly koinon runs as a headless API. Forge and other applications can use REST or the SDK without deploying the Angular frontend. The backend owns authorization, catalog scope, durable jobs and shared sessions; installing a UI does not change those controls.

## Choose an installation path

| Task | Start here |
|---|---|
| Understand the deployment | [Reference architecture](../concepts/architecture.md#reference-deployment) |
| Install released packages | [Install koinon](installation.md) |
| Evaluate or develop locally | [Local environment](local-deployment.md) |
| Configure the first organization | [First start in production](first-start.md), then [guided setup](../guides/knowledge-setup.md) |
| Upgrade or recover retained data | [Migrations](migrations.md) and [backup and restore](backup-restore.md) |

Deploy HTTP and background execution as separate [process roles](workers.md), with durable SQL queues and shared storage across replicas.

Read [local deployment](local-deployment.md), [migrations](migrations.md), [production](production.md), [configuration and observations](configuration.md), [file persistence and cloud storage](storage.md), [organization knowledge behavior](organization-knowledge.md), and [backup and recovery](backup-restore.md). [Qualification](qualification.md) separates observed local behavior from untested templates and external providers.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
