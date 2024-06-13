from __future__ import annotations
import typing as t
from copy import copy
from dataclasses import dataclass
import ibis

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.parse.expressions as ast
import kye.type.types as typ
from kye.load.loader import Loader

@dataclass
class Table:
    type: typ.Model
    table: ibis.Table
    
    def __repr__(self):
        return self.table.select(*(self.type.indexes.edges + [
            col for col in self.type.edge_order
            if col in self.table.columns and col not in self.type.indexes
        ]))._interactive_repr()

class Interpreter(ast.Visitor):
    loader: Loader
    reporter: ErrorReporter
    this: t.Optional[Table]
    types: typ.Types
    env: t.Dict[str, Table]
    
    def __init__(self, types: typ.Types, loader: Loader):
        self.loader = loader
        self.types = types
        self.env = {}
        self.this = None
    
    def visit_with_this(self, node_ast: ast.Node, this: Table):
        previous = self.this
        self.this = this
        result = self.visit(node_ast)
        self.this = previous
        return result
        
    def load_model(self, model_name: str) -> Table:
        if model_name in self.env:
            return self.env[model_name]
        assert model_name in self.types, f'Model {model_name} not found.'
        type = self.types[model_name]
        assert isinstance(type, typ.Model)
        if len(type.indexes) == 0:
            raise Exception('Models without indexes are not yet supported.')
        if len(type.indexes) > 1:
            raise Exception('Models with multiple indexes are not yet supported.')
        
        table = self.loader.load(type.source)
        model = Table(type, table)
        self.env[model_name] = model
        
        # TODO: report errors for failed assertions
        conditions = [
            self.visit_with_this(condition, model)
            for condition in type.filters + type.assertions
        ]
        if len(conditions):
            model = Table(type, table.filter(conditions))
            self.env[model_name] = model
        return model

    def visit_edge(self, edge_ast: ast.Edge):
        assert self.this is not None
        assert isinstance(self.this, Table), 'Edge used outside of table.'
        val = self.visit(edge_ast.expr)
        edge_name = edge_ast.name.lexeme
        self.this.type.edge_order.append(edge_name)
        self.this.table = self.this.table.mutate(**{edge_name: val})
            
    
    # def load_edge(self, edge: typ.Edge, table: ibis.Table) -> t.Optional[ibis.Value]:
    #     assert self.this is not None
        
    #     if len(edge.indexes) > 0:
    #         raise Exception('Edges with parameters are not yet supported.')
        
    #     if edge.name in table.columns:
    #         return table[edge.name] # type: ignore
        
    #     if edge.expr is not None:
    #         return self.visit_with_this(edge.expr, self.this)

    #     return None
    
    # def visit_type(self, type_ast: ast.Type):
    #     value = self.visit(type_ast.expr)
    #     assert isinstance(value, Model), 'Can only set alias to models.'
    #     type = copy(value)
    #     type.name = type_ast.name.lexeme
    #     self.types[type.name] = type
    #     return type
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        type = self.types[type_ast]
        if isinstance(type, typ.Model):
            return self.load_model(type.name)
        raise KyeRuntimeError(type_ast.name, f'Type {type_ast.name.lexeme} not defined.')
    
    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        edge_name = edge_ast.name.lexeme
        if self.this is None:
            raise KyeRuntimeError(edge_ast.name, 'Edge used outside of model.')
        if edge_name not in self.this.type:
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_ast.name.lexeme} not defined.')
        
        edge = self.this.type[edge_name]
        if isinstance(self.this.table, ibis.Table) and edge_name in self.this.table.columns:
            return self.this.table[edge_name]
        if edge.expr is not None:
            return self.visit_with_this(edge.expr, self.this)
        raise Exception(f'Edge {edge_name} not defined.')

    def visit_literal(self, literal_ast: ast.Literal):
        return literal_ast.value
    
    def visit_binary(self, binary_ast: ast.Binary):
        left = self.visit(binary_ast.left)
        right = self.visit(binary_ast.right)
        if left is None or right is None:
            return None
        if binary_ast.operator.type == ast.TokenType.PLUS:
            return left + right
        if binary_ast.operator.type == ast.TokenType.MINUS:
            return left - right
        if binary_ast.operator.type == ast.TokenType.STAR:
            return left * right
        if binary_ast.operator.type == ast.TokenType.SLASH:
            return left / right
        if binary_ast.operator.type == ast.TokenType.EQ:
            return left == right
        if binary_ast.operator.type == ast.TokenType.NE:
            return left != right
        if binary_ast.operator.type == ast.TokenType.GT:
            return left > right
        if binary_ast.operator.type == ast.TokenType.GE:
            return left >= right
        if binary_ast.operator.type == ast.TokenType.LT:
            return left < right
        if binary_ast.operator.type == ast.TokenType.LE:
            return left <= right
        if binary_ast.operator.type == ast.TokenType.AND:
            return left and right
        if binary_ast.operator.type == ast.TokenType.OR:
            return left or right
        raise ValueError(f'Unknown operator {binary_ast.operator.type}')
    
    
    def visit_call(self, call_ast: ast.Call):
        obj = self.visit(call_ast.object)
        assert isinstance(obj, Table), 'Can only call tables.'
        arguments = [self.visit(argument) for argument in call_ast.arguments]
        if obj is None and len(arguments) == 0:
            return arguments[0]
        assert len(obj.type.indexes) == len(arguments), 'Incorrect number of arguments.'
        assert isinstance(obj, ibis.Table)
        return Table(
            obj.type,
            obj.table.filter([
                obj[key] == val
                for key,val in
                zip(obj.type.indexes.edges, arguments)
            ])
        )

    def visit_get(self, get_ast: ast.Get):
        obj: Table = self.visit(get_ast.object)
        return self.visit_with_this(ast.EdgeIdentifier(name=get_ast.name), obj)
    
    def visit_filter(self, filter_ast: ast.Filter):
        obj = self.visit(filter_ast.object)
        assert isinstance(obj, Table), 'Can only filter on tables.'
        conditions = [
            self.visit_with_this(argument, obj)
            for argument in filter_ast.conditions
        ]
        return Table(
            obj.type,
            obj.table.filter(conditions)
        )
    
    def visit_select(self, select_ast: ast.Select):
        obj = self.visit(select_ast.object)
        assert isinstance(obj, Table), 'Can only select on tables.'
        selection = Table(
            obj.type.clone().hide_all_edges(),
            obj.table
        )
        self.visit_with_this(select_ast.body, selection)
        return selection
    
    def visit_assert(self, assert_ast: ast.Assert):
        assert self.this is not None, 'Assertion used outside of model.'
        assert isinstance(self.this, Table), 'Assertion used outside of model.'
        value = self.visit(assert_ast.expr)
        invalid_count = self.this.table.filter(~value).count().execute()
        if invalid_count > 0:
            raise KyeRuntimeError(assert_ast.keyword, 'Assertion failed.')