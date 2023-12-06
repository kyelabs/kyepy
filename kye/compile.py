from __future__ import annotations
from typing import Optional, Literal, Union
import kye.parser.kye_ast as AST
import kye.types as Types

def compile_expression(ast: AST.Expression, typ: Types.Type, env: SymbolsTable) -> Types.Expression:
    assert isinstance(ast, AST.Expression)
    if isinstance(ast, AST.Identifier):
        # TODO: Maybe somehow push this location onto a call stack?
        if ast.kind == 'type':
            # Maybe this could also be a call where the type is `Object` and it is bound to the type
            return Types.Expression(
                returns=env[ast.name].returns,
                loc=ast.meta,
            )
        if ast.kind == 'edge':
            assert typ is not None
            key = typ.ref + '.' + ast.name
            assert key in env
            return Types.CallExpression(
                bound=None,
                args=[],
                returns=env[key].returns,
                edge=env.get_edge(key),
                loc=ast.meta,
            )
    elif isinstance(ast, AST.LiteralExpression):
        if type(ast.value) is str:
            typ = env.get_type('String')
        elif type(ast.value) is bool:
            typ = env.get_type('Boolean')
        elif isinstance(ast.value, (int, float)):
            typ = env.get_type('Number')
        else:
            raise Exception()
        return Types.LiteralExpression(returns=typ, value=ast.value, loc=ast.meta)
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
                    edge=env.get_edge('Object.filter'),
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
                    edge=env.get_edge(f'{expr.returns.ref}.${ast.name}'),
                    loc=ast.meta,
                )
        return expr
    else:
        raise Exception('Unknown Expression')

def compile_edge_definition(ast: AST.EdgeDefinition, model: Types.Type, symbols: SymbolsTable) -> tuple[Types.Edge, Types.Expression]:
    assert isinstance(ast, AST.EdgeDefinition)
    return symbols.define_edge(
        name=ast.name,
        model=model,
        nullable=ast.cardinality in ('?','*'),
        multiple=ast.cardinality in ('+','*'),
        loc=ast.meta,
    ), (ast.type, model)


def compile_type_definition(ast: AST.TypeDefinition, symbols: SymbolsTable) -> tuple[Types.Type, Types.Expression]:
    assert isinstance(ast, AST.TypeDefinition)
    if isinstance(ast, AST.AliasDefinition):
        model = symbols.define_type(ref=ast.name, loc=ast.meta)
        return model, (ast.type, model)
    elif isinstance(ast, AST.ModelDefinition):
        model = symbols.define_type(ref=ast.name, indexes=ast.indexes, loc=ast.meta)
        return model, Types.Expression(returns=model, loc=ast.meta)
    else:
        raise Exception('Unknown TypeDefinition')


def compile_definitions(ast: AST.ModuleDefinitions):
    assert isinstance(ast, AST.ModuleDefinitions)

    symbols = SymbolsTable()
    Object = symbols.define_type(ref='Object')
    String = symbols.define_type(ref='String')
    Number = symbols.define_type(ref='Number')
    Boolean = symbols.define_type(ref='Boolean')
    symbols.define_edge(model=Object, name='filter', args=[Boolean])
    symbols.define_edge(model=String, name='length') # returns=Number
    symbols.define_edge(model=Number, name='$gt') # returns=Boolean

    symbols['Object'] = Types.Expression(returns=Object)
    symbols['String'] = Types.Expression(returns=String)
    symbols['Number'] = Types.Expression(returns=Number)
    symbols['Boolean'] = Types.Expression(returns=Boolean)
    symbols['Object.filter'] = Types.Expression(returns=Object)
    symbols['Number.$gt'] = Types.Expression(returns=Boolean)
    symbols['String.length'] = Types.Expression(returns=Number)

    for type_def in ast.children:
        typ, exp = compile_type_definition(type_def, symbols)
        symbols[typ.ref] = exp

        if isinstance(type_def, AST.ModelDefinition):
            for edge_def in type_def.edges:
                edge, exp = compile_edge_definition(edge_def, typ, symbols)
                symbols[edge.ref] = exp
    
    for exp in symbols:
        print(exp, symbols[exp])

    return symbols


class SymbolsTable:
    symbols: dict[str, Union[tuple, Types.Expression, None]]
    types: dict[Types.TYPE_REF, Types.Type]
    edges: dict[Types.EDGE_REF, Types.Edge]

    def __init__(self):
        self.symbols = {}
        self.types = {}
        self.edges = {}
    
    def define_type(self, **kwargs) -> Types.Type:
        typ = Types.Type(**kwargs)
        self.types[typ.ref] = typ
        return typ
    
    def define_edge(self, **kwargs) -> Types.Edge:
        edge = Types.Edge(**kwargs)
        self.edges[edge.ref] = edge
        return edge
    
    def get_type(self, ref: Types.TYPE_REF):
        return self.types[ref]
    
    def get_edge(self, ref: Types.EDGE_REF):
        return self.edges[ref]

    def __setitem__(self, ref: str, val: Union[tuple, Types.Expression]):
        assert ref not in self.symbols
        assert type(val) is tuple or isinstance(val, Types.Expression)
        self.symbols[ref] = val
    
    # TODO: rename to get_return_type or something and define/access 
    # the return type through the type/edge definitions
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