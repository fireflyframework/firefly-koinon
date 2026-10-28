# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Inventory only explicitly admitted retained operations, separately from canonical APIs."""
import ast
import hashlib


def qualified_glossary(root):
    guard = 'backend/src/koinon/knowledge/glossary_writes.py'
    tree = ast.parse((root / guard).read_text())
    registered = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'GLOSSARY_WRITES' for target in node.targets))
    admitted = set(ast.literal_eval(registered.value))
    read_guard = 'backend/src/koinon/knowledge/legacy_read.py'
    read_tree = ast.parse((root / read_guard).read_text())
    read_registered = next(node for node in read_tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'READ_OPERATIONS' for target in node.targets))
    reads = {(method, path) for domain, path, permission in ast.literal_eval(read_registered.value) if domain == 'structured' for method in ['GET']}
    result = []
    for agent in (False, True):
        source = 'packages/structured/src/flyquery/web/controllers/' + ('agent/' if agent else '') + 'glossary_controller.py'
        methods = ast.parse((root / source).read_text())
        cls = next(node for node in methods.body if isinstance(node, ast.ClassDef) and node.name == ('AgentGlossaryController' if agent else 'GlossaryController'))
        prefix = ('/agent' if agent else '') + '/glossary'
        for verb, suffix, method, helper, schema in (
            ('GET', '', 'list_terms', 'list', None),
            ('GET', '/{term_id}', 'get_term', 'get', None),
            ('POST', '', 'create', 'create', 'GlossaryTermCreate'),
            ('PUT', '/{term_id}', 'update', 'update', 'GlossaryTermUpdate'),
            ('DELETE', '/{term_id}', 'delete', 'remove', None),
        ):
            active_guard = read_guard if verb == 'GET' else guard
            assert (verb, prefix + suffix) in (reads if verb == 'GET' else admitted)
            endpoint = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == method)
            decorator = next(node for node in endpoint.decorator_list if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == verb.lower() + '_mapping')
            assert (ast.literal_eval(decorator.args[0]) if decorator.args else '') == suffix
            result.append({
                'operation': cls.name + '.' + method, 'method': verb,
                'path': '/api/v1/structured' + prefix + suffix,
                'source': active_guard,
                'source_sha256': hashlib.sha256((root / active_guard).read_bytes()).hexdigest(),
                'native_controller': cls.name, 'native_method': method,
                'native_source_sha256': hashlib.sha256((root / source).read_bytes()).hexdigest(),
                'guard': active_guard, 'guard_sha256': hashlib.sha256((root / active_guard).read_bytes()).hexdigest(),
                'request_schema': schema, 'response_schema': 'void' if verb == 'DELETE' else 'GlossaryPage' if method == 'list_terms' else 'GlossaryTermRead',
                'sdk_python': {'list':'glossary_terms', 'get':'glossary_term', 'create': 'create_glossary_term', 'update': 'update_glossary_term', 'remove': 'delete_glossary_term'}[helper],
                'sdk_python_agent': agent,
                'sdk_typescript': 'structured.' + ('agentGlossary' if agent else 'glossary') + '.' + helper,
                'sdk_java': 'client.' + ('structuredAgentGlossary' if agent else 'structuredGlossary') + '(tenant,workspace).' + helper,
                'headers': ['X-Tenant-ID', 'X-Workspace-ID'] + (['If-Match (exact unparsed updated_at string)'] if verb in {'PUT', 'DELETE'} else []),
            })
    return result
