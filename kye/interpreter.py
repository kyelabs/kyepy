from __future__ import annotations
import typing as t
from copy import copy
from dataclasses import dataclass
import ibis

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.parse.expressions as ast
import kye.type.types as typ
from kye.load.loader import Loader

class Interpreter(ast.Visitor):
    loader: Loader
    reporter: ErrorReporter
    this: t.Optional[typ.Type]
    types: typ.Types
    tables: t.Dict[str, ibis.Table]
    
    def __init__(self, types: typ.Types, loader: Loader):
        self.loader = loader
        self.types = types
        self.tables = {}
        self.this = None
    
    def visit_with_this(self, node_ast: ast.Node, this: typ.Type):
        previous = self.this
        self.this = this
        result = self.visit(node_ast)
        self.this = previous
        return result
        
    def load_model(self, model_name: str):
        previous_this = self.this
        assert model_name in self.types, f'Model {model_name} not found.'
        self.this = self.types[model_name]
        assert isinstance(self.this, typ.Model)
        
        if len(self.this.indexes) == 0:
            raise Exception('Models without indexes are not yet supported.')
        if len(self.this.indexes) > 1:
            raise Exception('Models with multiple indexes are not yet supported.')
        # TODO: Type check all indexes have a corresponding edge defined
        
        table = self.loader.load(self.this.source)
        self.tables[model_name] = table
        
        for col in self.this.edge_order:
            edge = self.this[col]
            if edge.name not in table.columns and edge.expr is not None:
                val = self.visit_with_this(edge.expr, self.this)
                table = table.mutate(**{edge.name: val})
                self.tables[model_name] = table
        
        conditions = [
            self.visit_with_this(condition, self.this)
            for condition in self.this.filters + self.this.assertions
        ]
        # TODO: report errors for failed assertions
        before_count = table.count().as_scalar().execute()
        filtered_table = table.filter(conditions)
        after_count = filtered_table.count().as_scalar().execute()
        if before_count != after_count:
            print(f'Lost rows after filtering: {before_count} -> {after_count}')
        
        self.tables[model_name] = filtered_table.select(*(self.this.indexes.edges + [
            col for col in self.this.edge_order
            if col in filtered_table.columns and col not in self.this.indexes
        ]))
        
        self.this = previous_this
            
    
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
        type = self.types.get(type_ast.name.lexeme)
        if isinstance(type, typ.Model):
            if type.name not in self.tables:
                self.load_model(type.name)
            return self.tables[type.name]
    
    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        edge_name = edge_ast.name.lexeme
        if self.this is None:
            raise KyeRuntimeError(edge_ast.name, 'Edge used outside of model.')
        table = self.tables[self.this.name]

        if edge_name not in table.columns:
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_ast.name.lexeme} not defined.')
        
        return table[edge_name]
    
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
    
    
    # def visit_call(self, call_ast: ast.Call):
    #     type = self.visit(call_ast.object)
    #     assert isinstance(type, Type), 'Can only call types.'
    #     arguments = [self.visit(argument) for argument in call_ast.arguments]
    #     if type is None and len(arguments) == 0:
    #         return arguments[0]
    #     return type.call(arguments)

    # def visit_get(self, get_ast: ast.Get):
    #     type = self.visit(get_ast.object)
    #     edge_name = get_ast.name.lexeme
    #     assert isinstance(type, Type), 'Can only access edges on tables.'
    #     if not type.has(get_ast.name.lexeme):
    #         raise KyeRuntimeError(get_ast.name, f'Edge {get_ast.name.lexeme} not defined.')
    #     return type.get(edge_name)
    
    # def visit_filter(self, filter_ast: ast.Filter):
    #     type = self.visit(filter_ast.object)
    #     assert isinstance(type, Type), 'Can only filter on tables.'
    #     conditions = [self.visit_with_this(argument, type) for argument in filter_ast.conditions]
    #     condition = conditions.pop(0)
    #     for cond in conditions:
    #         condition = condition & cond
    #     return type.filter(condition)
    
    # def visit_select(self, select_ast: ast.Select):
    #     type = self.visit(select_ast.object)
    #     assert isinstance(type, Model), 'Can only select on models.'
    #     model = copy(type).hide_all_edges()
        
    #     self.visit_with_this(select_ast.body, model)

    #     return model
    
    # def visit_assert(self, assert_ast: ast.Assert):
    #     assert self.this is not None, 'Assertion used outside of model.'
    #     assert isinstance(self.this, Model), 'Assertion used outside of model.'
    #     value = self.visit(assert_ast.expr)
    #     invalid_count = self.this.filter(~value).table.count().execute()
    #     if invalid_count > 0:
    #         raise KyeRuntimeError(assert_ast.keyword, 'Assertion failed.')