from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
from kye.errors.compilation_errors import CompilationErrorReporter
from kye.type.native_types import NATIVE_TYPES

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
    refs: t.Set[str]
    aliases: t.Dict[str, ast.Expr]
    
    def __init__(self):
        self.model = None
        self.refs = set()
        self.aliases = {}
    
    def visit_model(self, model_ast: ast.Model):
        self.model = model_ast
        self.visit_children(model_ast)
        self.model = None
        return model_ast
    
    def collect_refs(self, expr: ast.Expr):
        previous = self.refs
        self.refs = set()
        out = self.visit(expr)
        collected = self.refs
        self.refs = previous | collected
        return out, self.refs

    def visit_script(self, script_ast: ast.Script):
        statements = []
        for stmt in script_ast.statements:
            keep = self.visit(stmt)
            if keep is not None:
                statements.append(keep)
        script_ast.statements = tuple(statements)
        return script_ast

    # def visit_block(self, block_ast: ast.Block):
    #     statements = []
    #     for stmt in block_ast.statements:
    #         keep = self.visit(stmt)
    #         if keep is not None:
    #             statements.append(keep)
    #     block_ast.statements = tuple(statements)
    #     return block_ast
    
    def visit_type(self, type_ast: ast.Type):
        expr, refs = self.collect_refs(type_ast.expr)
        if isinstance(expr, ast.Expr) and len(refs) == 0:
            self.aliases[type_ast.name.lexeme] = expr
            return None
        return type_ast

    def visit_edge(self, edge_ast: ast.Edge):
        assert self.model is not None
        edge_ast.expr = self.visit(edge_ast.expr)
        assert isinstance(edge_ast.expr, ast.Expr)
        if not isinstance(edge_ast.expr, ast.TypeIdentifier):
            if isinstance(edge_ast.expr, ast.Literal):
                add_assertion(self.model, ast.Binary(
                    left=edge_identifier(edge_ast.name.lexeme),
                    operator=token(ast.TokenType.EQ),
                    right=edge_ast.expr,
                ))
                edge_ast.expr = type_identifier(edge_ast.expr.type)
        return edge_ast

    def visit_assert(self, assert_ast: ast.Assert):
        assert_ast.expr = self.visit(assert_ast.expr)
        return assert_ast
    
    def visit_binary(self, binary_ast: ast.Binary):
        left = self.visit(binary_ast.left)
        right = self.visit(binary_ast.right)
        assert isinstance(left, ast.Expr)
        assert isinstance(right, ast.Expr)
        self.left = left
        self.right = right
        if isinstance(left, ast.Literal) and isinstance(right, ast.Literal):
            if binary_ast.operator.type == ast.TokenType.PLUS:
                return literal(left.value + right.value)
            if binary_ast.operator.type == ast.TokenType.MINUS:
                return literal(left.value - right.value)
            if binary_ast.operator.type == ast.TokenType.STAR:
                return literal(left.value * right.value)
            if binary_ast.operator.type == ast.TokenType.SLASH:
                return literal(left.value / right.value)
            if binary_ast.operator.type == ast.TokenType.EQ:
                return literal(left.value == right.value)
            if binary_ast.operator.type == ast.TokenType.NE:
                return literal(left.value != right.value)
        return binary_ast
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        type_name = type_ast.name.lexeme
        if type_name in self.aliases:
            return self.aliases[type_name]
        if type_name not in NATIVE_TYPES:
            self.refs.add(type_name)
        return type_ast
    
    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        self.refs.add(edge_ast.name.lexeme)
        return edge_ast
    
    def visit_literal(self, literal_ast: ast.Literal):
        return literal_ast