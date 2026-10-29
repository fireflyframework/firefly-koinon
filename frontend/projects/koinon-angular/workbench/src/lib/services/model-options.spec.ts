// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { describeModelOptions, parseModelOptions } from '../../../../settings/src/model-options';
const schema = {
  properties: {
    output_mode: { anyOf: [{ type: 'string', enum: ['default', 'native'] }, { type: 'null' }] },
    max_tokens: { type: 'integer', minimum: 64, maximum: 16384, default: 4096 },
    temperature: { anyOf: [{ type: 'number', minimum: 0, maximum: 2 }, { type: 'null' }] },
    reasoning: { anyOf: [{ type: 'string', enum: ['none', 'low', 'high'] }, { type: 'null' }] },
    store_responses: { anyOf: [{ type: 'boolean' }, { type: 'null' }] },
    stop_sequences: {
      anyOf: [
        { type: 'array', maxItems: 8, items: { type: 'string', minLength: 1, maxLength: 256 } },
        { type: 'null' },
      ],
    },
  },
};
describe('native model option form', () => {
  it('keeps Auto omitted and roundtrips explicit output modes through the shared administrator form', () => {
    const fields = describeModelOptions(schema, ['output_mode']);
    expect(fields.map((field) => field.name)).toEqual(['output_mode']);
    expect(parseModelOptions(fields, { output_mode: '' }).value).toEqual({});
    for (const mode of ['default', 'native'])
      expect(parseModelOptions(fields, { output_mode: mode }).value).toEqual({ output_mode: mode });
    expect(parseModelOptions(fields, { output_mode: 'auto' }).errors['output_mode']).toBeTruthy();
  });
  it('shows only schema fields supported by the selected model API', () => {
    expect(
      describeModelOptions(schema, ['max_tokens', 'reasoning']).map((field) => field.name),
    ).toEqual(['max_tokens', 'reasoning']);
  });
  it('rejects invalid bounds, fractional integers, unknown choices and unsupported fields before a write', () => {
    const fields = describeModelOptions(schema, ['max_tokens', 'temperature', 'reasoning']);
    expect(
      parseModelOptions(fields, {
        max_tokens: '64.5',
        temperature: '3',
        reasoning: 'unbounded',
        seed: '1',
      }).errors,
    ).toEqual({
      max_tokens: 'Enter a whole number within the displayed limits.',
      temperature: 'Enter a number within the displayed limits.',
      reasoning: 'Choose one of the available values.',
      seed: 'This option is not supported by the selected model API.',
    });
  });
  it('preserves false and exact stop sequence text including whitespace and newlines', () => {
    const fields = describeModelOptions(schema, [
      'max_tokens',
      'store_responses',
      'stop_sequences',
    ]);
    expect(
      parseModelOptions(fields, {
        max_tokens: '4096',
        store_responses: 'false',
        stop_sequences: [' stop ', '\nEND\n'],
      }).value,
    ).toEqual({ max_tokens: 4096, store_responses: false, stop_sequences: [' stop ', '\nEND\n'] });
  });
});
it('counts Unicode code points for native stop-sequence bounds', () => {
  const fields = describeModelOptions(schema, ['stop_sequences']),
    stop = '😀'.repeat(200);
  expect(parseModelOptions(fields, { stop_sequences: [stop] })).toEqual({
    value: { stop_sequences: [stop] },
    errors: {},
  });
});
