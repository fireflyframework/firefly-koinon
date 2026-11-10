// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  afterNextRender,
  Injector,
  ChangeDetectionStrategy,
  Component,
  Output,
  Input,
  EventEmitter,
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
  KoinonDatePipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import {
  DOCUMENT_FIELDS,
  STRUCTURED_FIELDS,
  KoinonKnowledgeBehaviorConfiguration,
  type KnowledgeBehaviorField,
} from './knowledge-behavior-configuration';
import { KnowledgeModePreparation } from './knowledge-mode-preparation';
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
    KoinonDatePipe,
  ],
  providers: [KnowledgeModePreparation, KoinonKnowledgeBehaviorConfiguration],
  templateUrl: './knowledge-behavior.html',
  styleUrl: './knowledge-behavior.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeBehavior {
  @Input() canOpenResource = false;
  @Output() resourceRequested = new EventEmitter<string>();
  @Output() indexRequested = new EventEmitter<string>();
  readonly stageLabels: Record<string, string> = {
    discovery: 'Discovering documents',
    preflight: 'Checking model assignments',
    repair_views: 'Preparing document views',
    prepare_indexes: 'Preparing document indexes',
    verify: 'Verifying current knowledge',
    activate: 'Activating requested mode',
  };
  @Output() sectionRequested = new EventEmitter<string>();
  reviewAssignments() {
    if (this.c.f.tenantPermissions().has('providers:write')) this.sectionRequested.emit('models');
  }
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
      ...(mode === 'rag' ? ['documents.embedding'] : []),
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
  updateField(field: KnowledgeBehaviorField, input: HTMLInputElement) {
    this.c.set(this.id(field), input.value);
    this.revealField(input);
  }
  revealField(input: HTMLInputElement) {
    afterNextRender(
      () => {
        if (!input.isConnected || !input.matches(':focus') || !this.c.dirty()) return;
        const footer = input.closest('form')?.querySelector('footer');
        if (footer && input.getBoundingClientRect().bottom + 8 > footer.getBoundingClientRect().top)
          input.scrollIntoView({ block: 'center' });
      },
      { injector: this.injector },
    );
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
