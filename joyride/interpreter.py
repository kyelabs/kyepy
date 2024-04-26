from __future__ import annotations
import typing as t
import joyride.expressions as ast
import joyride.types as types
import pandas as pd

class Interpreter(ast.Visitor):
    types: t.Dict[str, types.Type]
    this: t.Optional[types.Type]
    tables: t.Dict[str, pd.DataFrame]
    
    def __init__(self, tables: t.Dict[str, pd.DataFrame]):
        self.types = {
            'Number': types.Number(),
            'String': types.String(),
            'Boolean': types.Boolean()
        }
        self.this = None
        self.tables = tables
    
    def visit_model(self, model_ast: ast.Model):
        if len(model_ast.indexes) == 0:
            raise ValueError('Model must have at least one index.')
        if len(model_ast.indexes) > 1:
            raise NotImplementedError('Models with multiple indexes are not supported.')

        model_name = model_ast.name.lexeme
        indexes = [index.lexeme for index in model_ast.indexes[0].names]
        assert model_name in self.tables, f'Undefined Table {model_name}'
        data = self.tables[model_name]
        model = types.Model(model_name, indexes, data)
        self.types[model_name] = model
        self.this = model
        self.visit(model_ast.body)
        self.this = None
    
    def visit_edge(self, edge_ast: ast.Edge):
        if len(edge_ast.indexes) >= 1:
            raise NotImplementedError('Edges with indexes are not supported.')
        
        edge_name = edge_ast.name.lexeme
        # indexes = [index.lexeme for index in edge_ast.indexes[0].names]
        indexes = []
        assert isinstance(self.this, types.Model), 'No type to define edge on.'

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
            params=indexes,
            cardinality=ast.Cardinality(edge_ast.cardinality.lexeme),
            type=type
        )
        self.this.edges[edge_name] = edge

        val = edge.call([self.this])
        edge.type.test(val)
        edge.bind(val)
    
    def visit_type_identifier(self, type: ast.TypeIdentifier):
        assert type.name.lexeme in self.types, f'Type {type.name.lexeme} not found.'
        return self.types[type.name.lexeme]
    
    def visit_edge_identifier(self, edge: ast.EdgeIdentifier):
        if self.this is None:
            raise ValueError('No type to resolve edge from.')
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