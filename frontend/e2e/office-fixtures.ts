// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Small genuine OOXML packages for transport tests; native parser coverage lives in backend tests.
import { crc32 } from 'node:zlib';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function archive(parts: Record<string, string>) {
  const entries: Buffer[] = [],
    directory: Buffer[] = [];
  let offset = 0;
  for (const [path, value] of Object.entries(parts)) {
    const name = Buffer.from(path),
      data = Buffer.from(value),
      header = Buffer.alloc(30),
      central = Buffer.alloc(46);
    header.writeUInt32LE(0x04034b50);
    header.writeUInt16LE(20, 4);
    header.writeUInt32LE(crc32(data), 14);
    header.writeUInt32LE(data.length, 18);
    header.writeUInt32LE(data.length, 22);
    header.writeUInt16LE(name.length, 26);
    central.writeUInt32LE(0x02014b50);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt32LE(crc32(data), 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    entries.push(header, name, data);
    directory.push(central, name);
    offset += header.length + name.length + data.length;
  }
  const table = Buffer.concat(directory),
    end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50);
  end.writeUInt16LE(Object.keys(parts).length, 8);
  end.writeUInt16LE(Object.keys(parts).length, 10);
  end.writeUInt32LE(table.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...entries, table, end]);
}
const rels = (body: string) =>
  `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${body}</Relationships>`;
const relation = (id: string, type: string, target: string) =>
  `<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/${type}" Target="${target}"/>`;
const types = (main: string, contentType: string, extra = '') =>
  `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/${main}" ContentType="application/vnd.openxmlformats-officedocument.${contentType}"/>${extra}</Types>`;
export function officeFile(kind: 'docx' | 'pptx' | 'xlsx' | 'csv') {
  const directory = process.env['KOINON_OFFICE_SAMPLES'];
  if (directory) return readFileSync(resolve(directory, 'review.' + kind));
  if (kind === 'csv') return Buffer.from('Region,Revenue\nNorth,125\nSouth,250\n');
  if (kind === 'docx')
    return archive({
      '[Content_Types].xml': types('word/document.xml', 'wordprocessingml.document.main+xml'),
      '_rels/.rels': rels(relation('main', 'officeDocument', 'word/document.xml')),
      'word/document.xml':
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>North region revenue is 125.</w:t></w:r></w:p></w:body></w:document>',
    });
  if (kind === 'pptx')
    return archive({
      '[Content_Types].xml': types(
        'ppt/presentation.xml',
        'presentationml.presentation.main+xml',
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>',
      ),
      '_rels/.rels': rels(relation('main', 'officeDocument', 'ppt/presentation.xml')),
      'ppt/presentation.xml':
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="slide1"/></p:sldIdLst></p:presentation>',
      'ppt/_rels/presentation.xml.rels': rels(relation('slide1', 'slide', 'slides/slide1.xml')),
      'ppt/slides/slide1.xml':
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>North region revenue is 125.</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>',
    });
  return archive({
    '[Content_Types].xml': types(
      'xl/workbook.xml',
      'spreadsheetml.sheet.main+xml',
      '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
    ),
    '_rels/.rels': rels(relation('main', 'officeDocument', 'xl/workbook.xml')),
    'xl/workbook.xml':
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Revenue" sheetId="1" r:id="sheet1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels': rels(relation('sheet1', 'worksheet', 'worksheets/sheet1.xml')),
    'xl/worksheets/sheet1.xml':
      '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Region</t></is></c><c r="B1" t="inlineStr"><is><t>Revenue</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>North</t></is></c><c r="B2"><v>125</v></c></row><row r="3"><c r="A3" t="inlineStr"><is><t>South</t></is></c><c r="B3"><v>250</v></c></row></sheetData></worksheet>',
  });
}
