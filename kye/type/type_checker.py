from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
import kye.type.types as typ
import kye.type.expr as expr
from kye.errors import ErrorReporter, KyeRuntimeError

class TypeChecker(ast.Visitor):
    """
    Responsible for type checking expressions
    """
    reporter: ErrorReporter
    this: t.Optional[typ.Type]
    types: typ.Types
    
    def __init__(self, reporter: ErrorReporter, types: typ.Types):
        self.reporter = reporter
        self.types = types
        self.this = None
        
        for type in types.values():
            self.this = type
            for edge in type.edges.values():
                if edge.expr is not None:
                    self.visit(edge.expr)
            for filter in type.filters:
                self.visit(filter)
            for assertion in type.assertions:
                self.visit(assertion)
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        assert type_ast.name.lexeme in self.types, f'Type {type_ast.name.lexeme} not defined.'
        return self.types[type_ast.name.lexeme]

    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        assert self.this is not None
        edge_name = edge_ast.name.lexeme
        if edge_name not in self.this:
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_name} not defined.')
        edge = self.this[edge_name]
        if edge.returns is not None:
            return edge.returns
        if edge.expr is not None:
            return self.visit(edge.expr)
        raise NotImplementedError('Edge has no return type or expression')
    
    def visit_literal(self, literal_ast: ast.Literal):
        return expr.Const(literal_ast.value)
    
    def visit_binary(self, binary_ast: ast.Binary):
        left = self.visit(binary_ast.left)
        right = self.visit(binary_ast.right)
        if not isinstance(left, expr.Expr) or not isinstance(right, expr.Expr):
            raise NotImplementedError('Binary operations not yet implemented for types')
        op = expr.Operator(binary_ast.operator.lexeme).edge_name
        return expr.Expr(op, (left, right))

    def visit_unary(self, unary_ast: ast.Unary):
        right = self.visit(unary_ast.right)
        if not isinstance(expr.Expr, right):
            raise NotImplementedError('Unary operations not yet implemented for types')
        return expr.Expr(unary_ast.operator.lexeme, (right,))

    def visit_get(self, get_ast: ast.Get):
        obj = self.visit(get_ast.object)
        edge = get_ast.name.lexeme
        if isinstance(obj, typ.Type):
            raise NotImplementedError('Get operations not yet implemented for types')
        return expr.Expr(edge, (obj,))

    def visit_call(self, call_ast: ast.Call):
        arguments = call_ast.arguments
        if isinstance(call_ast.object, (ast.TypeIdentifier, ast.EdgeIdentifier)):
            edge = call_ast.object.name.lexeme
        elif isinstance(call_ast.object, ast.Get):
            edge = call_ast.object.name.lexeme
            arguments = (call_ast.object.object,) + arguments
        else:
            raise NotImplementedError('cannot call an expression')
        args = [self.visit(arg) for arg in arguments]
        if any(isinstance(arg, typ.Type) for arg in args):
            raise NotImplementedError('Call operations not yet implemented for types')
        return expr.Expr(edge, args)