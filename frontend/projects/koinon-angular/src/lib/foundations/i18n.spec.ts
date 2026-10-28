// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonI18n } from './i18n';
describe('presentation preferences', () => {
  let presentation: KoinonI18n;
  beforeEach(() => {
    TestBed.configureTestingModule({});
    presentation = TestBed.inject(KoinonI18n);
  });
  it('switches interface language independently from response language', () => {
    expect(presentation.text('Library')).toBe('Library');
    presentation.apply({ locale: 'es-ES', time_zone: 'Europe/Madrid', response_language: 'en' });
    expect(presentation.text('Library')).toBe('Biblioteca');
    presentation.apply({ locale: 'en-US', time_zone: 'UTC', response_language: 'es' });
    expect(presentation.text('Library')).toBe('Library');
  });
  it('formats decimal strings without losing precision or trailing zeroes', () => {
    presentation.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
    const raw = '12345678901234567890.123400';
    expect(presentation.value(raw, 'DECIMAL(30,6)')).toBe('12.345.678.901.234.567.890,123400');
    expect(raw).toBe('12345678901234567890.123400');
  });
  it('does not turn identifiers or text into numeric values', () => {
    presentation.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
    expect(presentation.value('000123')).toBe('000123');
    expect(presentation.value('1000.00', 'NUMERIC')).toBe('1000,00');
    expect(presentation.value('USD 1000.00', 'TEXT')).toBe('USD 1000.00');
  });
  it('preserves signed zero and scientific decimal precision', () => {
    presentation.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
    expect(presentation.value('-0.0000', 'DECIMAL')).toBe('-0,0000');
    expect(presentation.value('1.230000e-24', 'NUMERIC')).toBe('1,230000e-24');
  });
  it('applies time zones to timestamps while retaining calendar dates', () => {
    presentation.apply({
      locale: 'en-US',
      time_zone: 'America/Los_Angeles',
      response_language: 'en',
    });
    expect(presentation.date('2026-10-26T01:30:00Z')).toContain('Oct 25, 2026');
    expect(presentation.date('2026-10-26')).toContain('Oct 26, 2026');
  });
});
it('does not normalize an invalid calendar date into a different day', () => {
  TestBed.configureTestingModule({});
  expect(TestBed.inject(KoinonI18n).date('2026-02-30')).toBe('2026-02-30');
});
it('translates knowledge configuration decisions and native query outcomes', () => {
  TestBed.configureTestingModule({});
  const i18n = TestBed.inject(KoinonI18n);
  i18n.apply({ locale: 'es-ES', time_zone: 'Europe/Madrid', response_language: 'en' });
  expect(i18n.text('Knowledge models')).toBe('Modelos de conocimiento');
  expect(i18n.text('Save assignment')).toBe('Guardar asignación');
  expect(i18n.text('Workspace override')).toBe('Excepción del espacio');
  expect(i18n.text('Query complete')).toBe('Consulta completada');
  expect(i18n.text('Query failed')).toBe('La consulta ha fallado');
  expect(i18n.text('Blocked by query policy')).toBe('Bloqueada por la política de consultas');
  expect(i18n.text('Status unavailable')).toBe('Estado no disponible');
});

it('translates access choices and private invitation security guidance', () => {
  const i18n = TestBed.inject(KoinonI18n);
  i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
  expect(i18n.text('Add existing person')).toBe('Añadir persona existente');
  expect(i18n.text('Invite a person')).toBe('Invitar a una persona');
  expect(
    i18n.text('This link is shown once. Closing this view removes it from this session.'),
  ).toContain('una sola vez');
  expect(i18n.text('Keep at least one administrator for this organization.')).toContain(
    'al menos un administrador',
  );
});

it('translates invitation dismissal, reconnect feedback and role removal', () => {
  const i18n = TestBed.inject(KoinonI18n);
  i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
  expect(i18n.text('Close invitation')).toBe('Cerrar invitación');
  expect(i18n.text('Not now')).toBe('Ahora no');
  expect(i18n.text('Reconnecting to your answer…')).toBe('Reconectando con tu respuesta…');
  expect(i18n.text('Remove')).toBe('Eliminar');
});

it('distinguishes stored result truncation, preview controls and absent SQL in Spanish', () => {
  const i18n = TestBed.inject(KoinonI18n);
  i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'en' });
  expect(i18n.text('Recorded source lineage')).toBe('Linaje registrado de las fuentes');
  expect(i18n.text('Recorded with this query result.')).toBe(
    'Registrado con este resultado de consulta.',
  );
  expect(i18n.text('Original database')).toBe('Base de datos original');
  expect(i18n.text('Imported snapshot execution')).toBe(
    'Ejecución sobre una instantánea importada',
  );
  expect(i18n.text('Indexed document content')).toBe('Contenido de documentos indexados');
  expect(i18n.text('Copy SQL')).toBe('Copiar SQL');
  expect(i18n.text('Copy unavailable. Select the SQL and copy it manually.')).toBe(
    'No se puede copiar. Selecciona el SQL y cópialo manualmente.',
  );
  expect(i18n.text('Result truncated')).toBe('Resultado truncado');
  expect(i18n.text('Returned data preview')).toBe('Vista previa de los datos devueltos');
  expect(i18n.text('No SQL is available in this result.')).toBe('Este resultado no incluye SQL.');
});
