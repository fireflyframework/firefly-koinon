// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  PendingTasks,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonClientContext,
  KoinonFacade,
  KoinonIcon,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import {
  KoinonBranding,
  DEFAULT_BRANDING,
  resolveBranding,
  PALETTE_FIELDS,
  brandImage,
  brandSymbol,
  validateBranding,
  registerKoinonSpanish,
} from '@fireflyframework/koinon-angular/workbench';
import type { OrganizationBranding } from '@fireflyframework/koinon-sdk';
import { IDENTITY_SPANISH } from './identity-spanish';
registerKoinonSpanish(IDENTITY_SPANISH);
import { KoinonIdentityPreview } from './identity/identity-preview';
import { KoinonIdentityAssetField } from './identity/identity-asset-field';
import { applyBrandColor, paletteChecks } from './identity/identity-palette';
type Asset = 'logo_light' | 'logo_dark' | 'symbol' | 'favicon';
@Component({
  selector: 'ffk-identity-appearance',
  imports: [
    FormsModule,
    KoinonIdentityPreview,
    KoinonIdentityAssetField,
    KoinonButton,
    KoinonIcon,
    KoinonTextPipe,
  ],
  templateUrl: './identity-appearance.html',
  styleUrl: './identity-appearance.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonIdentityAppearance implements OnInit, OnDestroy {
  readonly editorTab = signal<'identity' | 'colors'>('identity');
  readonly previewOpen = signal(false);
  readonly brandColor = signal('#ffb34a');
  readonly validBrandColor = computed(() => /^#[0-9a-fA-F]{6}$/.test(this.brandColor()));
  readonly checks = computed(() => paletteChecks(this.draft().palette[this.previewTheme()]));
  readonly brand = inject(KoinonBranding);
  readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private imageEpoch = 0;
  private imageVersions: Partial<Record<Asset, number>> = {};
  readonly uploading = signal(0);
  private invalidateImages() {
    ++this.imageEpoch;
    this.uploading.set(0);
  }
  private epoch = 0;
  private key = '';
  readonly allowed = computed(() => this.f.tenantPermissions().has('settings:write'));
  readonly settings = signal<OrganizationBranding | null>(null);
  readonly draft = signal<ReturnType<typeof resolveBranding>>(structuredClone(DEFAULT_BRANDING));
  readonly previewTheme = signal<'light' | 'dark'>('light');
  readonly inheriting = signal(false);
  readonly pending = signal(false);
  readonly saving = signal(false);
  readonly stale = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly problems = computed(() => validateBranding(this.draft()));
  readonly changed = computed(
    () =>
      !!this.settings() &&
      (this.inheriting()
        ? this.settings()!.origin !== 'deployment'
        : JSON.stringify(this.draft()) !==
          JSON.stringify(resolveBranding(this.settings()!.branding))),
  );
  readonly canSave = computed(
    () =>
      this.allowed() &&
      this.changed() &&
      !this.problems().length &&
      !this.pending() &&
      !this.saving() &&
      !this.uploading() &&
      !this.stale(),
  );
  fallback(key: Asset) {
    if (key === 'symbol') return brandSymbol(this.draft(), this.brand.assetBase());
    if (key === 'favicon')
      return this.draft().product_name === 'koinon'
        ? this.brand.assetBase() + '/logos/koinon-symbol-color.svg'
        : '';
    return brandImage(this.draft(), key === 'logo_dark' ? 'dark' : 'light', this.brand.assetBase());
  }
  applyColor() {
    try {
      this.draft.set(applyBrandColor(this.draft(), this.brandColor()));
      this.inheriting.set(false);
      this.notice.set('Brand color applied to both previews. Save changes to use it.');
      this.error.set('');
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Enter a six-digit hex color.');
    }
  }
  tabKey(event: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    this.editorTab.set(
      event.key === 'Home'
        ? 'identity'
        : event.key === 'End'
          ? 'colors'
          : this.editorTab() === 'identity'
            ? 'colors'
            : 'identity',
    );
    const parent = (event.currentTarget as HTMLElement).parentElement;
    queueMicrotask(() => parent?.querySelector<HTMLButtonElement>('[aria-selected=true]')?.focus());
  }
  readonly assets: { key: Asset; label: string; hint: string }[] = [
    {
      key: 'logo_light',
      label: 'Light theme logo',
      hint: 'Shown in navigation. Deployment logos also appear at sign-in.',
    },
    {
      key: 'logo_dark',
      label: 'Dark theme logo',
      hint: 'Use a version that works on dark backgrounds.',
    },
    { key: 'symbol', label: 'Assistant symbol', hint: 'Shown beside assistant messages.' },
    { key: 'favicon', label: 'Browser icon', hint: 'Used by the standalone application.' },
  ];
  readonly colors = PALETTE_FIELDS;
  font(value: 'Manrope' | 'Inter') {
    if (!['Manrope', 'Inter'].includes(value)) return;
    this.draft.update((draft) => ({ ...draft, font_family: value }));
    this.inheriting.set(false);
  }
  readonly labels: Record<string, string> = {
    surface: 'Surface',
    canvas: 'Background',
    text: 'Text',
    muted: 'Secondary text',
    line: 'Borders',
    action: 'Primary button',
    action_text: 'Button text',
    accent: 'Links & focus',
  };
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        this.invalidateImages();
        this.pending.set(false);
        this.saving.set(false);
        this.settings.set(null);
        this.draft.set(structuredClone(DEFAULT_BRANDING));
        this.error.set('');
        this.notice.set('');
        this.tasks.run(() => this.load());
      }
    });
  }
  ngOnInit() {
    this.tasks.run(() => this.brand.loadDefaults());
    if (!this.key) {
      this.key = this.contextKey();
      this.tasks.run(() => this.load());
    }
  }
  private contextKey() {
    return (
      this.clients.revision() +
      ':' +
      this.f.tenantId() +
      ':' +
      (this.f.context()?.subject || '') +
      ':' +
      this.allowed()
    );
  }
  private current(epoch: number) {
    return epoch === this.epoch && this.key === this.contextKey() && this.allowed();
  }
  async load() {
    if (!this.allowed()) return;
    const epoch = ++this.epoch;
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    this.stale.set(true);
    try {
      const tenant = this.f.tenantId();
      const value = await this.clients.get().branding.get(tenant);
      if (value.tenant_id !== tenant) throw new Error('Organization identity mismatch');
      if (!this.current(epoch)) return;
      if (value.tenant_id !== tenant) throw new Error('Organization identity mismatch');
      this.settings.set(value);
      this.draft.set(resolveBranding(structuredClone(value.branding)));
      this.inheriting.set(value.origin === 'deployment');
      this.stale.set(false);
      this.brandColor.set(this.draft().palette.light.action);
    } catch {
      if (this.current(epoch)) this.error.set('Identity settings could not be loaded. Try again.');
    } finally {
      if (this.current(epoch)) this.pending.set(false);
    }
  }
  name(key: 'product_name' | 'assistant_name', value: string) {
    this.inheriting.set(false);
    this.draft.update((current) => ({ ...current, [key]: value }));
    this.notice.set('');
  }
  color(key: (typeof PALETTE_FIELDS)[number], value: string) {
    this.inheriting.set(false);
    const theme = this.previewTheme();
    this.draft.update((current) => ({
      ...current,
      palette: { ...current.palette, [theme]: { ...current.palette[theme], [key]: value } },
    }));
    this.notice.set('');
  }
  remove(key: Asset) {
    this.invalidateImages();
    this.inheriting.set(false);
    this.draft.update((current) => ({ ...current, [key]: null }));
  }
  async upload(key: Asset, event: Event) {
    const input = event.target as HTMLInputElement,
      file = input.files?.[0];
    input.value = '';
    if (file) await this.uploadFile(key, file);
  }
  async uploadFile(key: Asset, file: File) {
    this.error.set('');
    const epoch = this.epoch;
    const imageEpoch = this.imageEpoch,
      version = (this.imageVersions[key] ?? 0) + 1;
    this.imageVersions[key] = version;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 256 * 1024) {
      this.error.set('Choose a PNG, JPEG or WebP image up to 256 KB.');
      return;
    }
    this.uploading.update((value) => value + 1);
    const current = () =>
      this.current(epoch) && imageEpoch === this.imageEpoch && this.imageVersions[key] === version;
    try {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error());
        reader.readAsDataURL(file);
      });
      if (!current()) return;
      await new Promise<void>((resolve, reject) => {
        const image = new Image();
        image.onload = () =>
          image.naturalWidth <= 2048 && image.naturalHeight <= 2048
            ? resolve()
            : reject(new Error('Choose an image no larger than 2048 pixels.'));
        image.onerror = () =>
          reject(new Error('This image could not be opened. Choose another file.'));
        image.src = data;
      });
      if (!current()) return;
      this.inheriting.set(false);
      this.draft.update((current) => ({ ...current, [key]: data }));
    } catch (error) {
      if (current())
        this.error.set(
          error instanceof Error && error.message
            ? error.message
            : 'This image could not be opened. Choose another file.',
        );
    } finally {
      if (imageEpoch === this.imageEpoch) this.uploading.update((value) => Math.max(0, value - 1));
    }
  }
  restore() {
    if (!this.brand.defaultsReady()) return;
    this.invalidateImages();
    this.draft.set(resolveBranding(structuredClone(this.brand.deployment())));
    this.inheriting.set(true);
    this.notice.set('Deployment defaults are ready to review. Save changes to apply them.');
  }
  discard() {
    this.invalidateImages();
    const value = this.settings();
    if (value) {
      this.draft.set(resolveBranding(structuredClone(value.branding)));
      this.inheriting.set(value.origin === 'deployment');
      this.error.set('');
      this.notice.set('');
    }
  }
  async save() {
    if (!this.canSave()) return;
    const epoch = this.epoch,
      tenant = this.f.tenantId(),
      revision = this.settings()!.revision;
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const client = this.clients.get();
      const value = await (this.inheriting()
        ? client.branding.reset(tenant, { expected_revision: revision })
        : client.branding.update(tenant, { expected_revision: revision, branding: this.draft() }));
      if (!this.current(epoch)) return;
      if (value.tenant_id !== tenant) throw new Error('Organization identity mismatch');
      this.settings.set(value);
      this.draft.set(resolveBranding(structuredClone(value.branding)));
      this.inheriting.set(value.origin === 'deployment');
      this.brand.accept(value);
      this.notice.set('Identity saved.');
    } catch (error) {
      if (this.current(epoch)) {
        const conflict = error instanceof Error && 'status' in error && error.status === 409;
        if (conflict) this.stale.set(true);
        this.error.set(
          conflict
            ? 'Identity settings changed. Reload before saving again.'
            : 'Identity could not be saved. Review your images and colors, then try again.',
        );
      }
    } finally {
      if (this.current(epoch)) this.saving.set(false);
    }
  }
  ngOnDestroy() {
    this.invalidateImages();
    ++this.epoch;
  }
}
