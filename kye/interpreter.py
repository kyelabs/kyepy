from __future__ import annotations
import typing as t
import kye.expressions as ast
import kye.types as types
import pandas as pd
from kye.errors import ErrorReporter, KyeRuntimeError

class Interpreter(ast.Visitor):
    types: t.Dict[str, types.Type]
    this: t.Optional[types.Type]
    tables: t.Dict[str, pd.DataFrame]
    reporter: ErrorReporter
    
    def __init__(self, tables: t.Dict[str, pd.DataFrame], reporter: ErrorReporter):
        self.types = {
            'Number': types.Number(),
            'String': types.String(),
            'Boolean': types.Boolean()
        }
        self.this = None
        self.tables = tables
        self.reporter = reporter
    
    def visit_model(self, model_ast: ast.Model):
        if len(model_ast.indexes) == 0:
            raise KyeRuntimeError(model_ast.name, 'Models without indexes are not yet supported.')
        if len(model_ast.indexes) > 1:
            raise KyeRuntimeError(model_ast.name, 'Models with multiple indexes are not yet supported.')

        model_name = model_ast.name.lexeme
        indexes = [index.lexeme for index in model_ast.indexes[0].names]
        if len(indexes) == 0:
            raise KyeRuntimeError(model_ast.name, 'Model must have at least one index.')

        if model_name not in self.tables:
            raise KyeRuntimeError(model_ast.name, 'Table not found for model.')

        data = self.tables[model_name]
        model = types.Model(model_name, indexes, data)
        self.types[model_name] = model
        self.this = model
        self.visit(model_ast.body)
        self.this = None

        for idx_ast in model_ast.indexes[0].names:
            if idx_ast.lexeme not in model.edges:
                raise KyeRuntimeError(idx_ast, 'Index edge not defined in model.')
    
    def visit_edge(self, edge_ast: ast.Edge):
        
        edge_name = edge_ast.name.lexeme

        if len(edge_ast.params) > 0:
            raise KyeRuntimeError(edge_ast.name, 'Edges with parameters are not yet supported.')
        params = []

        assert isinstance(self.this, types.Model), 'No type to define edge on.'

        if edge_name in self.this.edges:
            raise KyeRuntimeError(edge_ast.name, 'Edge already defined in model.')

        type = self.visit(edge_ast.body)
        if not isinstance(type, types.Type):
            const_type = None
            if isinstance(type, (int, float)):
                const_type = self.types['Number']
            elif isinstance(type, str):
                const_type = self.types['String']
            elif isinstance(type, bool):
                const_type = self.types['Boolean']
            else:
                raise ValueError(f'Unknown type {type}')
            type = types.Const(type, const_type)

        edge = types.Edge(
            name=edge_name,
            model=self.this,
            params=params,
            cardinality=ast.Cardinality(edge_ast.cardinality.lexeme),
            type=type
        )
        self.this.edges[edge_name] = edge

        val = edge.call([self.this])
        edge.type.test(val)
        edge.bind(val)
    
    def visit_type_identifier(self, type: ast.TypeIdentifier):
        if type.name.lexeme not in self.types:
            raise KyeRuntimeError(type.name, 'Type not defined.')
        return self.types[type.name.lexeme]
    
    def visit_edge_identifier(self, edge: ast.EdgeIdentifier):
        if self.this is None:
            raise KyeRuntimeError(edge.name, 'Edge used outside of model.')
        return self.this.edges[edge.name.lexeme]
    
    def visit_literal(self, literal: ast.Literal):
        return literal.value
    
    def visit_binary(self, binary: ast.Binary):
        left = self.visit(binary.left)
        right = self.visit(binary.right)
        if binary.operator.type == ast.TokenType.PLUS:
            return left + right
        if binary.operator.type == ast.TokenType.MINUS:
            return left - right
        if binary.operator.type == ast.TokenType.STAR:
            return left * right
        if binary.operator.type == ast.TokenType.SLASH:
            return left / right
        if binary.operator.type == ast.TokenType.EQ:
            return left == right
        if binary.operator.type == ast.TokenType.NE:
            return left != right
        if binary.operator.type == ast.TokenType.GT:
            return left > right
        if binary.operator.type == ast.TokenType.GE:
            return left >= right
        if binary.operator.type == ast.TokenType.LT:
            return left < right
        if binary.operator.type == ast.TokenType.LE:
            return left <= right
        if binary.operator.type == ast.TokenType.AND:
            return left and right
        if binary.operator.type == ast.TokenType.OR:
            return left or right
        raise ValueError(f'Unknown operator {binary.operator.type}')
    
    def visit_call(self, call: ast.Call):
        callee = self.visit(call.callee)
        assert isinstance(callee, types.Callable), 'Can only call functions and methods.'
        arguments = [self.visit(argument) for argument in call.arguments]
        if len(arguments) != callee.arity():
            raise ValueError(f'Expected {callee.arity()} arguments, got {len(arguments)}.')
        return callee.call(arguments)

    def visit_get(self, get: ast.Get):
        object = self.visit(get.object)
        edge_name = get.name.lexeme
        assert isinstance(object, types.Model), 'Can only access edges on models.'
        assert edge_name in object.edges, f'Edge {edge_name} not found on {object.name}.'
        return object.edges[edge_name]