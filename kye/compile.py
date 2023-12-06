from __future__ import annotations
from typing import Optional, Literal, Union
import kye.parser.kye_ast as AST
import kye.types as Types

def compile_expression(ast: AST.Expression, typ: Optional[Types.Type], symbols: Models) -> Types.Expression:
    assert isinstance(ast, AST.Expression)
    if isinstance(ast, AST.Identifier):
        # TODO: Maybe somehow push this location onto a call stack?
        if ast.kind == 'type':
            # Maybe this could also be a call where the type is `Object` and it is bound to the type
            return Types.Expression(
                returns=symbols.get_return_type(ast.name),
                loc=ast.meta,
            )
        if ast.kind == 'edge':
            edge = symbols.get_edge(typ, ast.name)
            return Types.CallExpression(
                bound=None,
                args=[],
                returns=symbols.get_return_type(edge.ref),
                edge=edge,
                loc=ast.meta,
            )
    elif isinstance(ast, AST.LiteralExpression):
        if type(ast.value) is str:
            typ = symbols.get_type('String')
        elif type(ast.value) is bool:
            typ = symbols.get_type('Boolean')
        elif isinstance(ast.value, (int, float)):
            typ = symbols.get_type('Number')
        else:
            raise Exception()
        return Types.LiteralExpression(returns=typ, value=ast.value, loc=ast.meta)
    elif isinstance(ast, AST.Operation):
        assert len(ast.children) >= 1
        expr = compile_expression(ast.children[0], typ, symbols)
        if ast.name == 'filter':
            assert len(ast.children) <= 2
            if len(ast.children) == 2:
                filter = compile_expression(ast.children[1], expr.returns, symbols)
                expr = Types.CallExpression(
                    bound=expr,
                    args=[filter],
                    returns=expr.returns,
                    edge=symbols.get_edge(expr.returns, '$filter'),
                    loc=ast.meta,
                )
        elif ast.name == 'dot':
            assert len(ast.children) >= 2
            for child in ast.children[1:]:
                expr = compile_expression(child, expr.returns, symbols)
        else:
            for child in ast.children[1:]:
                expr = Types.CallExpression(
                    bound=expr,
                    args=[
                        compile_expression(child, typ, symbols)
                    ],
                    returns=expr.returns,
                    edge=symbols.get_edge(expr.returns, '$' + ast.name),
                    loc=ast.meta,
                )
        return expr
    else:
        raise Exception('Unknown Expression')

def compile_edge_definition(ast: AST.EdgeDefinition, model: Types.Type, symbols: Models) -> tuple[Types.Edge, Types.Expression]:
    assert isinstance(ast, AST.EdgeDefinition)
    return symbols.define_edge(
        name=ast.name,
        model=model,
        nullable=ast.cardinality in ('?','*'),
        multiple=ast.cardinality in ('+','*'),
        loc=ast.meta,
        expr=ast.type,
    )


def compile_type_definition(ast: AST.TypeDefinition, symbols: Models) -> tuple[Types.Type, Types.Expression]:
    assert isinstance(ast, AST.TypeDefinition)
    if isinstance(ast, AST.AliasDefinition):
        return symbols.define_type(ref=ast.name, loc=ast.meta, expr=ast.type)
    elif isinstance(ast, AST.ModelDefinition):
        return symbols.define_type(
            ref=ast.name,
            indexes=ast.indexes,
            loc=ast.meta,
            extends=symbols.get_type('Object')
        )
    else:
        raise Exception('Unknown TypeDefinition')


def compile_definitions(ast: AST.ModuleDefinitions):
    assert isinstance(ast, AST.ModuleDefinitions)

    symbols = Models()
    Object = symbols.define_type(ref='Object')
    String = symbols.define_type(ref='String', extends=Object)
    Number = symbols.define_type(ref='Number', extends=Object)
    Boolean = symbols.define_type(ref='Boolean', extends=Object)
    symbols.define_edge(model=Object, name='$filter', args=[Boolean], returns=Object)
    symbols.define_edge(model=String, name='length', returns=Number)
    symbols.define_edge(model=Number, name='$gt', args=[Number], returns=Boolean)

    for type_def in ast.children:
        typ = compile_type_definition(type_def, symbols)

        if isinstance(type_def, AST.ModelDefinition):
            for edge_def in type_def.edges:
                compile_edge_definition(edge_def, typ, symbols)
    
    for exp in symbols.definitions:
        print(exp, symbols.get_return_type(exp))

    return symbols


class Models:
    definitions: dict[str, Types.Definition]
    expressions: dict[str, AST.Expression]

    def __init__(self):
        self.definitions = {}
        self.expressions = {}
    
    def _define(self, definition: Types.Definition, expr: Optional[AST.Expression] = None):
        assert definition.ref not in self.definitions
        self.definitions[definition.ref] = definition
        assert definition.returns is not None or expr is not None, 'Must either have returns defined or expression defined'
        if expr is not None:
            self.expressions[definition.ref] = expr
    
    def define_type(self, expr: Optional[AST.Expression] = None, **kwargs) -> Types.Type:
        typ = Types.Type(**kwargs)
        # If the type does not define an expression, then return itself
        if expr is None:
            typ.returns = typ
        self._define(typ, expr)
        return typ
    
    def define_edge(self, expr: Optional[AST.Expression] = None, **kwargs) -> Types.Edge:
        edge = Types.Edge(**kwargs)
        self._define(edge, expr)
        if edge.name not in edge.model.edges:
            edge.model.edges[edge.name] = edge
        assert edge.model.edges[edge.name] == edge
        return edge
    
    def get_type(self, ref: Types.TYPE_REF):
        typ = self.definitions[ref]
        assert isinstance(typ, Types.Type)
        return typ
    
    def get_edge(self, typ: Types.Type, edge_ref: Types.EDGE_REF):
        extended_type = typ
        edge = self.definitions.get(extended_type.ref + '.' + edge_ref)
        while edge is None and extended_type.extends is not None:
            extended_type = extended_type.extends
            edge = self.definitions.get(extended_type.ref + '.' + edge_ref)

        if edge is None:
            raise KeyError(f"Unknown edge `{typ.ref}.{edge_ref}`")
        assert isinstance(edge, Types.Edge)
        return edge
    
    def get_return_type(self, ref: str) -> Types.Type:
        if ref not in self.definitions:
            raise KeyError(f'Unknown symbol `{ref}`')
        definition = self.definitions[ref]
        if definition is None:
            raise Exception(f'Possible circular reference for `{ref}`')
        if getattr(definition, 'returns') is None:
            # Clear the table first, so that if the function calls itself
            # it will get a circular reference error
            self.definitions[ref] = None
            definition.expr = compile_expression(
                ast=self.expressions[ref],
                typ=definition.model if isinstance(definition, Types.Edge) else None,
                symbols=self
            )
            assert isinstance(definition.expr, Types.Expression)
            definition.returns = definition.expr.returns
            self.definitions[ref] = definition
        return definition.returns

    def __contains__(self, ref: str):
        return ref in self.definitions