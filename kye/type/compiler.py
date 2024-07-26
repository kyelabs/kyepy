from __future__ import annotations
import typing as t

import kye.type.types as typ
from kye.vm.op import OP
from kye.compiled import Compiled, Model, Edge, Assertion, Cmd

def compile(types: typ.Types) -> Compiled:
    models = {}
    
    for type in types.values():
        if type.source is not None:
            assert type.source not in models
            if isinstance(type, typ.Model):
                models[type.source] = compile_model(type)
            else:
                compile_type(type)

    return Compiled(models=models)

def compile_model(type: typ.Model) -> Model:
    return Model(
        name=type.name,
        indexes=[
            list(idx) for idx in type.indexes.sets
        ],
        edges={
            edge.name: compile_edge(type.name, edge)
            for edge in type.edges.values()
        },
        assertions=[
            compile_assertion(type.name, assertion)
            for assertion in type.assertions
        ],
        loc=str(type.loc) if type.loc else None
    )

def compile_type( type: typ.Type):
    pass

def compile_edge(model_name: str, edge: typ.Edge) -> Edge:
    assert edge.returns is not None
    return Edge(
        model=model_name,
        name=edge.name,
        title=edge.title,
        type=edge.returns.name,
        expr=list(compile_expr(edge.expr)) if edge.expr else None,
        many=edge.allows_many,
        null=edge.allows_null,
        loc=str(edge.loc) if edge.loc else None
    )

def compile_assertion(model_name: str, assertion: typ.Assertion) -> Assertion:
    return Assertion(
        model=model_name,
        msg='',
        expr=list(compile_expr(assertion.expr)),
        loc=str(assertion.loc) if assertion.loc else None
    )

def compile_expr( expr: typ.Expr) -> t.Iterator[Cmd]:
    if isinstance(expr, typ.Var):
        yield Cmd(op=OP.COL, args=[ expr.name ])
        return
    assert expr.name.startswith('$')
    op = OP[expr.name[1:].upper()]
    args = []
    for arg in expr.args:
        if isinstance(arg, typ.Const):
            args.append(arg.value)
        else:
            yield from compile_expr(arg)
    yield Cmd(op=op, args=args)