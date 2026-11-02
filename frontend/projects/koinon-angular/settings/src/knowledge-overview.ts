// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { KoinonButton, KoinonIcon, KoinonTextPipe } from '@fireflyframework/koinon-angular';
@Component({
  selector: 'ffk-knowledge-overview',
  imports: [KoinonButton, KoinonIcon, KoinonTextPipe],
  templateUrl: './knowledge-overview.html',
  styleUrl: './knowledge-overview.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeOverview {
  @Input() connections: { saved: number; checked: number } | null = null;
  @Input() sections: readonly string[] = [];
  @Output() sectionRequested = new EventEmitter<string>();
  readonly tasks = [
    {
      section: 'providers',
      icon: 'link',
      title: 'Connect model services',
      description:
        'Manage endpoints and credentials, discover available models and run explicit connection checks.',
      action: 'Manage connections',
    },
    {
      section: 'models',
      icon: 'spark',
      title: 'Assign processing models',
      description:
        'Choose document and dataset embeddings for the selected workspace. Specialist processing roles remain configurable separately.',
      action: 'Review assignments',
    },
    {
      section: 'answers',
      icon: 'search',
      title: 'Choose how knowledge is answered',
      description:
        'Set RAG or RLM for document answers and review the organization’s search, analysis and query limits.',
      action: 'Configure answers',
    },
    {
      section: 'agents',
      icon: 'chat',
      title: 'Configure your organization assistant',
      description:
        'Choose the shared chat assistant, its model and tools, and the limits for conversation and project memory.',
      action: 'Configure assistant',
    },
    {
      section: 'storage',
      icon: 'table',
      title: 'Prepare search indexes',
      description:
        'Select a workspace and knowledge domain, inspect compatibility, and explicitly build or activate an index.',
      action: 'Manage indexes',
    },
  ];
  open(section: string) {
    if (this.sections.includes(section)) this.sectionRequested.emit(section);
  }
}
