from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
from kye.errors.compilation_errors import CompilationErrorReporter

def token(type: ast.TokenType, value: t.Optional[str] = None):
    if value is None:
        value = type.value
    return ast.Token(type=type, lexeme=value, loc=ast.NULL_LOCATION)

def literal(value: t.Union[int, float, str, bool]):
    type = None
    if isinstance(value, (int, float)):
        type = ast.TokenType.NUMBER
    elif isinstance(value, bool):
        type = ast.TokenType.BOOLEAN
    elif isinstance(value, str):
        type = ast.TokenType.STRING
    else:
        raise ValueError(f'Unsupported literal type: {type(value)}')
    return ast.Literal(token(type, str(value)), value)

def type_identifier(name: str):
    return ast.TypeIdentifier(name=token(ast.TokenType.TYPE, name), format=None)

def edge_identifier(name: str):
    return ast.EdgeIdentifier(name=token(ast.TokenType.EDGE, name))

def assert_(expr: ast.Expr):
    return ast.Assert(keyword=token(ast.TokenType.ASSERT), expr=expr)

def add_assertion(model: ast.Model, expr: ast.Expr):
    model.body.statements = model.body.statements + (assert_(expr),)

class Desugar(ast.Visitor):
    def __init__(self):
        self.model = None
    
    def visit_model(self, model_ast: ast.Model):
        self.model = model_ast
        self.visit_children(model_ast)
        self.model = None

    def visit_edge(self, edge_ast: ast.Edge):
        assert self.model is not None
        if not isinstance(edge_ast.expr, ast.TypeIdentifier):
            if isinstance(edge_ast.expr, ast.Literal):
                add_assertion(self.model, ast.Binary(
                    left=edge_identifier(edge_ast.name.lexeme),
                    operator=token(ast.TokenType.EQ),
                    right=edge_ast.expr,
                ))
                edge_ast.expr = type_identifier(edge_ast.expr.type)