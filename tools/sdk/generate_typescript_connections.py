# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Render standalone TypeScript contracts from the shared Python SDK wire schemas."""
import argparse
import importlib
import inspect
import json
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sdk/python/src'))


def kind(schema):
    if '$ref' in schema:
        name=schema['$ref'].split('/')[-1]
        return 'Json' if name=='JsonValue' else name
    if 'const' in schema:return json.dumps(schema['const'])
    if 'enum' in schema:return ' | '.join(json.dumps(value) for value in schema['enum'])
    variants=schema.get('anyOf',schema.get('oneOf'))
    if variants:return ' | '.join(kind(value) for value in variants)
    selected=schema.get('type')
    if selected=='null':return 'null'
    if selected=='string':return 'string'
    if selected in ('integer','number'):return 'number'
    if selected=='boolean':return 'boolean'
    if selected=='array':return 'Array<'+kind(schema.get('items',{}))+'>'
    if selected=='object':
        additional=schema.get('additionalProperties')
        return 'Record<string,'+(kind(additional) if isinstance(additional,dict) else 'Json')+'>'
    return 'Json'


def render():
    classes=[]
    for name in ('mcp','external_reviews','external_file_reviews','organization_branding','organization_knowledge','organization_chat','authorized_applications','indexes','identity','attachments','evidence','exports','sharing','proposals','glossary','answer_audit','provenance','coordinates','curated','dataset_files'):
        module=importlib.import_module('koinon_sdk.'+name)
        classes.extend(value for value in vars(module).values() if inspect.isclass(value) and issubclass(value,BaseModel) and value.__module__==module.__name__)
    from koinon_sdk.models import AttachmentHistorySummary
    classes.append(AttachmentHistorySummary)
    _,schemas=models_json_schema([(value,'validation') for value in classes],ref_template='#/$defs/{model}')
    lines=['// Copyright 2026 Firefly Software Foundation','// SPDX-License-Identifier: Apache-2.0','// Generated from source-backed standalone SDK wire schemas.',"import type {Json} from './types.js';",'']
    for name,schema in sorted(schemas['$defs'].items()):
        properties=schema.get('properties')
        if properties is None:
            lines.append('export type '+name+' = '+kind(schema)+';')
            continue
        required=set(schema.get('required',[]))
        lines.append('export interface '+name+' {')
        for field,value in properties.items():
            lines.append(' '+json.dumps(field)+('' if field in required else '?')+': '+kind(value)+';')
        lines.append('}')
    lines.extend(['export type AttachmentStatus = AttachmentView["status"];','export type AttachmentKind = AttachmentView["kind"];',''])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    target=ROOT/'sdk/typescript/src/generated.ts'
    content=render()
    if args.check:
        assert target.exists() and target.read_text()==content,'Generated TypeScript contracts are stale'
    else:target.write_text(content)


if __name__=='__main__':main()
