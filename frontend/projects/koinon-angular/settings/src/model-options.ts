// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { ModelParameters } from '@fireflyframework/koinon-sdk';
export interface ModelOptionField {
  name: keyof ModelParameters;
  label: string;
  type: 'number' | 'select' | 'boolean' | 'list';
  integer: boolean;
  minimum?: number;
  maximum?: number;
  defaultValue?: string;
  options: string[];
  maxItems?: number;
  minLength?: number;
  maxLength?: number;
}
export type ModelOptionValues = Record<string, string | string[]>;
const LABELS: Record<keyof ModelParameters, string> = {
  max_tokens: 'Maximum output tokens',
  temperature: 'Temperature',
  top_p: 'Top P',
  top_k: 'Top K',
  seed: 'Seed',
  stop_sequences: 'Stop sequences',
  request_timeout: 'Request timeout (seconds)',
  reasoning: 'Reasoning effort',
  reasoning_budget_tokens: 'Reasoning token budget',
  parallel_tool_calls: 'Parallel tool calls',
  store_responses: 'Provider response storage',
  output_verbosity: 'Response detail',
};
function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
function number(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
export function describeModelOptions(
  schema: Record<string, unknown> | undefined,
  supported: readonly string[],
): ModelOptionField[] {
  const root = record(schema),
    properties = record(root['properties']);
  return Object.entries(properties).flatMap(([name, raw]) => {
    if (!Object.hasOwn(LABELS, name) || !supported.includes(name)) return [];
    const source = record(raw),
      alternatives = source['anyOf'],
      nullable = Array.isArray(alternatives)
        ? alternatives.map(record).find((value) => value['type'] !== 'null')
        : undefined;
    let property = nullable ?? source;
    const ref = property['$ref'];
    if (typeof ref === 'string' && ref.startsWith('#/$defs/'))
      property = record(record(root['$defs'])[ref.slice(8)]);
    const options = Array.isArray(property['enum'])
      ? property['enum'].filter((value): value is string => typeof value === 'string')
      : [];
    const type = options.length
      ? 'select'
      : property['type'] === 'integer' || property['type'] === 'number'
        ? 'number'
        : property['type'] === 'boolean'
          ? 'boolean'
          : property['type'] === 'array'
            ? 'list'
            : null;
    if (!type) return [];
    const items = record(property['items']),
      defaultValue = source['default'];
    return [
      {
        name: name as keyof ModelParameters,
        label: LABELS[name as keyof ModelParameters],
        type,
        integer: property['type'] === 'integer',
        minimum: number(property['minimum']),
        maximum: number(property['maximum']),
        defaultValue:
          defaultValue === null || defaultValue === undefined ? undefined : String(defaultValue),
        options,
        maxItems: number(property['maxItems']),
        minLength: number(items['minLength']),
        maxLength: number(items['maxLength']),
      },
    ];
  });
}
export function parseModelOptions(
  fields: ModelOptionField[],
  values: ModelOptionValues,
): { value: ModelParameters; errors: Record<string, string> } {
  const value: Record<string, unknown> = {},
    errors: Record<string, string> = {};
  for (const [name, raw] of Object.entries(values)) {
    if (raw === '' || (Array.isArray(raw) && raw.length === 0)) continue;
    const field = fields.find((field) => field.name === name);
    if (!field) {
      errors[name] = 'This option is not supported by the selected model API.';
      continue;
    }
    if (field.type === 'number') {
      const parsed = typeof raw === 'string' ? Number(raw) : NaN;
      if (
        !Number.isFinite(parsed) ||
        (field.integer && !Number.isInteger(parsed)) ||
        (field.minimum !== undefined && parsed < field.minimum) ||
        (field.maximum !== undefined && parsed > field.maximum)
      )
        errors[name] = field.integer
          ? 'Enter a whole number within the displayed limits.'
          : 'Enter a number within the displayed limits.';
      else value[name] = parsed;
    } else if (field.type === 'select') {
      if (typeof raw !== 'string' || !field.options.includes(raw))
        errors[name] = 'Choose one of the available values.';
      else value[name] = raw;
    } else if (field.type === 'boolean') {
      if (raw !== 'true' && raw !== 'false') errors[name] = 'Choose one of the available values.';
      else value[name] = raw === 'true';
    } else {
      if (
        !Array.isArray(raw) ||
        (field.maxItems !== undefined && raw.length > field.maxItems) ||
        raw.some(
          (item) =>
            (field.minLength !== undefined && [...item].length < field.minLength) ||
            (field.maxLength !== undefined && [...item].length > field.maxLength),
        )
      )
        errors[name] = 'Stop sequences must be nonempty and within the displayed limits.';
      else value[name] = [...raw];
    }
  }
  return { value: value as ModelParameters, errors };
}
