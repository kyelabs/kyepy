from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import kye.type.types as typ
from kye.errors import ErrorReporter
from kye.vm.op import OP

Compiled = dict
Model = dict
Edge = dict
Assertion = dict
Expr = dict

class Compiler:
    reporter: ErrorReporter
    types: typ.Types
    compiled: Compiled
    
    def __init__(self, types: typ.Types):
        self.types = types
        self.compiled = {
            'models': {}
        }
        
        for type in types.values():
            if type.source is not None:
                if isinstance(type, typ.Model):
                    self.compiled['models'][type.source] = self.compile_model(type)
                else:
                    self.compile_type(type)
    
    def write(self, path_: str):
        path = Path(path_)
        text = None
        if path.suffix in ('.yaml', '.yml'):
            import yaml
            text = yaml.dump(self.compiled, sort_keys=False)
        elif path.suffix == '.json':
            import json
            text = json.dumps(self.compiled, sort_keys=False, indent=2)
        else:
            raise ValueError(f'Unsupported file extension: {path.suffix}')
        path.write_text(text)

    def compile_model(self, type: typ.Model) -> Model:
        assert type.source not in self.compiled
        return {
            'indexes': [
                list(idx)
                for idx in type.indexes.sets
            ],
            'edges': {
                edge.name: self.compile_edge(edge)
                for edge in type.edges.values()
            },
            'assertions': [
                self.compile_assertion(assertion)
                for assertion in type.assertions
            ]
        }

    def compile_type(self, type: typ.Type):
        pass
    
    def compile_edge(self, edge: typ.Edge) -> Edge:
        assert edge.returns is not None
        compiled = {
            'type': edge.returns.name,
            'expr': list(self.compile_expr(edge.expr))
        }
        if len(compiled['expr']) == 1 and 'col' in compiled['expr'][0]:
            del compiled['expr']
        if edge.allows_many:
            compiled['many'] = True
        if edge.allows_null:
            compiled['null'] = True
        return compiled
    
    def compile_assertion(self, assertion: typ.Expr) -> Assertion:
        return {
            'msg': '',
            'expr': list(self.compile_expr(assertion))
        }

    def compile_expr(self, expr: typ.Expr) -> t.Iterator[Expr]:
        if isinstance(expr, typ.Var):
            yield { 'col': expr.name }
            return
        assert expr.name.startswith('$')
        op = OP[expr.name[1:].upper()]
        const_args = []
        for arg in expr.args:
            if isinstance(arg, typ.Const):
                const_args.append(arg.value)
            else:
                yield from self.compile_expr(arg)
        args = const_args
        if len(args) == 0:
            args = None
        elif len(args) == 1:
            args = args[0]
        yield { op.name.lower(): args }