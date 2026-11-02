<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Start with koinon

<p class="doc-home-lead">Find what your organization knows, ask questions and inspect the evidence. koinon brings documents, datasets and reviewed knowledge together, with access controlled by your organization.</p>

## Choose your starting point

<div class="doc-entry-list" markdown="0">
  <section class="doc-entry">
    <h3>Use shared knowledge</h3>
    <div><p>Find a source, explore an answer and check its recorded evidence.</p><p><a href="guides/library/">Browse the Library</a> <a href="guides/agents/">Use agents and chat</a></p></div>
  </section>
  <section class="doc-entry">
    <h3>Administer an organization</h3>
    <div><p>Set up access, people, model connections and knowledge behavior.</p><p><a href="guides/configuration-overview/">Administration overview</a> <a href="guides/knowledge-setup/">Guided setup</a></p></div>
  </section>
  <section class="doc-entry">
    <h3>Build an integration</h3>
    <div><p>Use the headless API, typed SDKs or embedded components in your product.</p><p><a href="guides/integrations/">Integration overview</a> <a href="guides/embedding/">Embed the interface</a></p></div>
  </section>
  <section class="doc-entry">
    <h3>Operate a deployment</h3>
    <div><p>Install a release, connect its infrastructure and establish the first organization.</p><p><a href="operations/installation/">Install koinon</a> <a href="concepts/architecture/#reference-deployment">Reference architecture</a> <a href="operations/first-start/">First start</a></p></div>
  </section>
</div>

## Set up a working organization

Installation and organization configuration are separate tasks. An operator prepares the services and protected storage; an administrator chooses access, models and organization policy. Use this sequence to connect those tasks:

1. [Establish the installation and its first administrators](operations/first-start.md). Verify the migrated databases, identity, persistent objects, staging and worker roles before importing real material.
2. [Configure the organization](guides/knowledge-setup.md). Follow the actual Settings pages for people, appearance, providers, knowledge behavior and the central chat agent.
3. [Complete a small acceptance exercise](guides/knowledge-setup.md#complete-the-first-acceptance-exercise). Import a fictional document and dataset, ask questions with known answers, check source evidence and repeat with a restricted reader.
4. [Inspect health and diagnose failures](operations/platform-health.md#diagnose-a-problem-in-order). Distinguish saved configuration, current observations and successful operations, then keep a tested [recovery procedure](operations/backup-restore.md).

Already operating an organization? Follow a [complete workflow by role](guides/user-journeys.md), or use [the configuration lifecycle](guides/configuration-lifecycle.md) to change a provider, model, index or delivery policy. The [administration guide](guides/administration.md#find-a-setting) maps each setting to its task and explains permissions, revisions and common failures.

## Connect your tools

<div class="doc-connection-paths" markdown="0">
  <section>
    <h3>Develop with a typed SDK</h3>
    <p>Keep authentication, scope and explicit review in your application's workflow.</p>
    <ul><li><a href="guides/headless-python/">Python</a></li><li><a href="guides/headless-typescript/">TypeScript</a></li><li><a href="guides/headless-java/">Java 21 and later</a></li></ul>
  </section>
  <section>
    <h3>Use an AI client</h3>
    <p>Connect your authorized repository and review changes inside a compatible host.</p>
    <ul><li><a href="guides/connect-claude/">Connect Claude</a></li><li><a href="guides/connect-chatgpt/">Connect ChatGPT</a></li><li><a href="guides/mcp-knowledge-management/">Understand in-chat review</a></li></ul>
  </section>
</div>

## See the workflow

<figure class="doc-product-preview">
  <a href="guides/interface-tour/"><img src="assets/screenshots/chat-answer.png" alt="koinon Chat with a source-based answer, a query-results table and an Audit control" width="1440" height="1000" loading="lazy"></a>
  <figcaption>Controlled API fixture showing Chat and query results for layout review. The example data is illustrative. <a href="guides/interface-tour/">Follow the visual walkthrough</a> for Library, configuration and source inspection.</figcaption>
</figure>

Library keeps sources organized. Chat helps you explore them. Settings gives administrators control over access and configuration. Proposed knowledge updates require review before they change the repository. Read the [architecture guide](concepts/architecture.md) for identities and persistence boundaries.

## Version 26.11.5

koinon uses CalVer `YY.MM.Patch`. Read the [release notes](releases/26.11.5.md), follow the [guided setup](guides/knowledge-setup.md), and configure your environment with the [deployment guide](operations/production.md). The [qualification history](operations/qualification.md) records the scope and results of individual checks.
