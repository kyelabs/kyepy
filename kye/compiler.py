from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import kye.type.types as typ
from kye.errors import ErrorReporter
from kye.vm.op import OP

__all__ = ['Compiled', 'write_compiled', 'read_compiled', 'compile']

class Compiled(t.TypedDict):
    models: t.Dict[str, Model]

class Model(t.TypedDict):
    indexes: t.List[t.List[str]]
    edges: t.Dict[str, Edge]
    assertions: t.List[Assertion]
    loc: t.NotRequired[str]

class Edge(t.TypedDict):
    type: str
    expr: t.NotRequired[t.List[Expr]]
    many: t.NotRequired[bool]
    null: t.NotRequired[bool]
    loc: t.NotRequired[str]

class Assertion(t.TypedDict):
    msg: str
    expr: t.List[Expr]
    loc: t.NotRequired[str]

Expr = dict[str, t.Optional[t.Union[t.Any, t.List[t.Any]]]]

def read_compiled(filepath: str) -> Compiled:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text()
    if path.suffix in ('.yaml', '.yml'):
        import yaml
        return yaml.safe_load(text)
    elif path.suffix == '.json':
        import json
        return json.loads(text)
    else:
        raise ValueError(f'Unsupported file extension: {path.suffix}')

def write_compiled(compiled: Compiled, filepath: str):
    path = Path(filepath)
    text = None
    if path.suffix in ('.yaml', '.yml'):
        import yaml
        text = yaml.dump(compiled, sort_keys=False)
    elif path.suffix == '.json':
        import json
        text = json.dumps(compiled, sort_keys=False, indent=2)
    else:
        raise ValueError(f'Unsupported file extension: {path.suffix}')
    path.write_text(text)

def compile(types: typ.Types) -> Compiled:
    compiled: Compiled = {
        'models': {}
    }
    
    for type in types.values():
        if type.source is not None:
            assert type.source not in compiled
            if isinstance(type, typ.Model):
                compiled['models'][type.source] = compile_model(type)
            else:
                compile_type(type)
    return compiled
    

def compile_model(type: typ.Model) -> Model:
    compiled: Model = {
        'indexes': [
            list(idx)
            for idx in type.indexes.sets
        ],
        'edges': {
            edge.name: compile_edge(edge)
            for edge in type.edges.values()
        },
        'assertions': [
            compile_assertion(assertion)
            for assertion in type.assertions
        ],
    }
    if type.loc:
        compiled['loc'] = str(type.loc)
    return compiled

def compile_type( type: typ.Type):
    pass

def compile_edge( edge: typ.Edge) -> Edge:
    assert edge.returns is not None
    compiled: Edge = {
        'type': edge.returns.name,
    }
    if edge.expr:
        compiled['expr'] = list(compile_expr(edge.expr))
    if edge.allows_many:
        compiled['many'] = True
    if edge.allows_null:
        compiled['null'] = True
    if edge.loc:
        compiled['loc'] = str(edge.loc)
    return compiled

def compile_assertion( assertion: typ.Assertion) -> Assertion:
    compiled: Assertion = {
        'msg': '',
        'expr': list(compile_expr(assertion.expr))
    }
    if assertion.loc:
        compiled['loc'] = str(assertion.loc)
    return compiled

def compile_expr( expr: typ.Expr) -> t.Iterator[Expr]:
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
            yield from compile_expr(arg)
    args = const_args
    if len(args) == 0:
        args = None
    elif len(args) == 1:
        args = args[0]
    yield { op.name.lower(): args }