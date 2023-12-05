from __future__ import annotations
from typing import Optional, Literal, Union
import kye.parser.kye_ast as AST
import kye.types as Types

def compile_expression(ast: AST.Expression, typ: Types.Type, env: ExpressionsTable) -> Types.Expression:
    assert isinstance(ast, AST.Expression)
    if isinstance(ast, AST.Identifier):
        # TODO: Maybe somehow push this location onto a call stack?
        if ast.kind == 'type':
            return env[ast.name] # Maybe this could also be a call where the type is `Object` and it is bound to the type
        if ast.kind == 'edge':
            assert typ is not None
            key = typ.ref + '.' + ast.name
            assert key in env
            return env[key] # Should accessing an edge should return a `Function` type?
    elif isinstance(ast, AST.LiteralExpression):
        if type(ast.value) is str:
            typ = env['String']
        elif type(ast.value) is bool:
            typ = env['Boolean']
        elif isinstance(ast.value, (int, float)):
            typ = env['Number']
        else:
            raise Exception()
        return Types.LiteralExpression(returns=typ.returns, value=ast.value, loc=ast.meta)
    elif isinstance(ast, AST.Operation):
        assert len(ast.children) >= 1
        expr = compile_expression(ast.children[0], typ, env)
        if ast.name == 'filter':
            assert len(ast.children) <= 2
            if len(ast.children) == 2:
                filter = compile_expression(ast.children[1], expr.returns, env)
                expr = Types.CallExpression(
                    bound=expr,
                    args=[filter],
                    returns=expr.returns,
                    edge_ref='Object.filter',
                    loc=ast.meta,
                )
        elif ast.name == 'dot':
            assert len(ast.children) >= 2
            for child in ast.children[1:]:
                expr = compile_expression(child, expr.returns, env)
        else:
            for child in ast.children[1:]:
                expr = Types.CallExpression(
                    bound=expr,
                    args=[
                        compile_expression(child, typ, env)
                    ],
                    returns=expr.returns,
                    edge_ref=f'{expr.returns.ref}.${ast.name}',
                    loc=ast.meta,
                )
        return expr
    else:
        raise Exception('Unknown Expression')

def compile_edge_definition(ast: AST.EdgeDefinition, model: Types.Type) -> tuple[Types.Edge, Types.Expression]:
    assert isinstance(ast, AST.EdgeDefinition)
    return Types.Edge(
        name=ast.name,
        model=model,
        nullable=ast.cardinality in ('?','*'),
        multiple=ast.cardinality in ('+','*'),
        loc=ast.meta,
    ), (ast.type, model)

def compile_type_definition(ast: AST.TypeDefinition) -> tuple[Types.Type, Types.Expression]:
    assert isinstance(ast, AST.TypeDefinition)
    if isinstance(ast, AST.AliasDefinition):
        model = Types.Type(ref=ast.name, loc=ast.meta)
        return model, (ast.type, model)
    elif isinstance(ast, AST.ModelDefinition):
        model = Types.Type(ref=ast.name, indexes=ast.indexes, loc=ast.meta)
        return model, Types.Expression(returns=model, loc=ast.meta)
    else:
        raise Exception('Unknown TypeDefinition')


def compile_definitions(ast: AST.ModuleDefinitions):
    assert isinstance(ast, AST.ModuleDefinitions)
    definitions = {}
    expressions = ExpressionsTable()

    expressions['Object'] = Types.Expression(returns=Types.Type('Object'))
    expressions['Object.filter'] = Types.Expression(returns=expressions['Object'].returns) # I feel like these returns should return an edge?
    expressions['Number'] = Types.Expression(returns=Types.Type('Number'))
    expressions['String'] = Types.Expression(returns=Types.Type('String'))
    expressions['String.length'] = Types.Expression(returns=expressions['Number'].returns)
    expressions['Boolean'] = Types.Expression(returns=Types.Type('Boolean'))

    for type_def in ast.children:
        typ, exp = compile_type_definition(type_def)
        definitions[typ.ref] = typ
        expressions[typ.ref] = exp

        if isinstance(type_def, AST.ModelDefinition):
            for edge_def in type_def.edges:
                edge, exp = compile_edge_definition(edge_def, typ)
                definitions[edge.ref] = edge
                expressions[edge.ref] = exp
    
    for exp in expressions:
        print(exp, expressions[exp])

    return expressions


class ExpressionsTable:
    symbols: dict[str, Union[tuple, Types.Expression, None]]

    def __init__(self):
        self.symbols = {}
    
    # TODO: have a define_type & define_edge functions that create an expression that returns a `Object`
    # def define_type(self, type: Types.Type):
    #     self.symbols[type.ref] = Types.Expression(bound=type, returns='Type')

    def __setitem__(self, ref: str, val: Union[tuple, Types.Expression]):
        assert ref not in self.symbols
        assert type(val) is tuple or isinstance(val, Types.Expression)
        self.symbols[ref] = val
    
    def __getitem__(self, ref: str):
        if ref not in self.symbols:
            raise KeyError(f'Unknown symbol `{ref}`')
        val = self.symbols[ref]
        if val is None:
            raise Exception(f'Possible circular reference for `{ref}`')
        elif isinstance(val, Types.Expression):
            return val
        elif type(val) is tuple:
            # Clear the table first, so that if the function calls itself
            # it will get a circular reference error
            self.symbols[ref] = None
            self.symbols[ref] = compile_expression(*val, env=self)
            return self.symbols[ref]
        else:
            raise Exception()
    
    def __iter__(self):
        return self.symbols.__iter__()

    def __contains__(self, ref: str):
        return ref in self.symbols