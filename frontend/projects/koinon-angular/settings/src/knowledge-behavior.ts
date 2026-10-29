// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  afterNextRender,
  Injector,
  ChangeDetectionStrategy,
  Component,
  PendingTasks,
  computed,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonIcon,
  KoinonSkeleton,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import {
  DOCUMENT_FIELDS,
  STRUCTURED_FIELDS,
  KoinonKnowledgeBehaviorConfiguration,
  type KnowledgeBehaviorField,
} from './knowledge-behavior-configuration';
import { KNOWLEDGE_BEHAVIOR_SPANISH } from './knowledge-behavior-spanish';
registerKoinonSpanish(KNOWLEDGE_BEHAVIOR_SPANISH);
@Component({
  selector: 'ffk-knowledge-behavior',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonIcon,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonValuePipe,
  ],
  providers: [KoinonKnowledgeBehaviorConfiguration],
  templateUrl: './knowledge-behavior.html',
  styleUrl: './knowledge-behavior.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeBehavior {
  readonly c = inject(KoinonKnowledgeBehaviorConfiguration);
  private readonly tasks = inject(PendingTasks);
  private readonly injector = inject(Injector);
  readonly groups = [
    {
      label: 'Document search and answers',
      description: 'Control how document passages are found and used to answer.',
      fields: DOCUMENT_FIELDS.slice(0, 6),
    },
    {
      label: 'Document analysis',
      description:
        'More analysis steps, calls or independent attempts can increase response time and model usage.',
      fields: DOCUMENT_FIELDS.slice(6),
    },
    {
      label: 'Dataset queries',
      description:
        'Dataset questions use schema context and SQL generation, review and explanation.',
      fields: STRUCTURED_FIELDS,
    },
  ];
  readonly requiredRoles = computed(() => {
    const values = this.c.values(),
      mode = values['documents.answer_mode'];
    const ids = [
      'documents.embedding',
      mode === 'rlm'
        ? this.c.settings()?.capabilities.documents.rlm_model_role
        : 'documents.answer',
      'structured.embedding',
      'structured.grounding',
      'structured.generation',
      'structured.explainer',
    ];
    if (values['documents.query_expansion_enabled'] && !ids.includes('documents.answer'))
      ids.push('documents.answer');
    if (Number(values['structured.max_refine_retries']) > 0) ids.push('structured.critic');
    return this.c.roles()?.filter((role) => ids.includes(role.id)) ?? [];
  });
  constructor() {
    effect(() => {
      this.c.contextKey();
      untracked(() => this.tasks.run(() => this.c.load()));
    });
  }
  id(field: KnowledgeBehaviorField) {
    return field.domain + '.' + field.name;
  }
  status(value: string) {
    return value === 'assigned' ? 'Assigned' : value === 'disabled' ? 'Disabled' : 'Not assigned';
  }
  async save(form: HTMLFormElement) {
    await this.c.save();
    if (Object.values(this.c.errors()).some(Boolean))
      afterNextRender(
        () => {
          const invalid = form.querySelector<HTMLElement>('[aria-invalid=true]');
          const details = invalid?.closest('details');
          if (details) details.open = true;
          invalid?.focus();
        },
        { injector: this.injector },
      );
  }
}
