from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.type.native_types import NATIVE_TYPES


class TypeBuilder(ast.Visitor):
    """
    Responsible for interpreting the AST and building the types
    - Does not type check
    - Does not touch expressions, only organizes them 
      within the types (edges, conditions, assertions)
    """
    reporter: ErrorReporter
    this: t.Optional[typ.Type]
    types: typ.Types
    
    def __init__(self):
        self.types = {**NATIVE_TYPES}
        self.this = None
    
    def define(self, type: typ.Type):
        assert type.name not in self.types
        self.types[type.name] = type
    
    def visit_with_this(self, node_ast: ast.Node, this: typ.Type):
        previous = self.this
        self.this = this
        result = self.visit(node_ast)
        self.this = previous
        return result

    def visit_model(self, model_ast: ast.Model):
        model = typ.Model(
            name=model_ast.name.lexeme,
            source=model_ast.name.lexeme,
            indexes=typ.Indexes(model_ast.indexes)
        )
        self.define(model)
        self.visit_with_this(model_ast.body, model)
        for index in model.indexes.edges:
            assert index in model, f'Index {index} not defined in model {model.name}'
    
    def visit_edge(self, edge_ast: ast.Edge):
        assert self.this is not None
        
        returns = self.visit(edge_ast.expr)
        expr = None
        if returns is None:
            expr = edge_ast.expr
            returns = None
        
        edge = typ.Edge(
            name=edge_ast.name.lexeme,
            indexes=typ.Indexes(edge_ast.params),
            allows_null=edge_ast.cardinality.allows_null,
            allows_many=edge_ast.cardinality.allows_many,
            model=self.this,
            returns=returns,
            expr=expr,
        )
        
        self.this.define(edge)
    
    def visit_type(self, type_ast: ast.Type):
        value = self.visit(type_ast.expr)
        assert isinstance(value, typ.Type)
        type = value.clone()
        type.name = type_ast.name.lexeme
        self.define(type)
        return type

    def visit_assert(self, assert_ast: ast.Assert):
        obj: typ.Type = self.visit(assert_ast.expr)
        assert self.this is not None
        assert typ.has_compatible_source(obj, self.this)
        self.this.assertions.append(assert_ast.expr)

    def visit_filter(self, filter_ast: ast.Filter):
        obj: typ.Type = self.visit(filter_ast.object)
        obj = obj.clone()
        obj.filters += filter_ast.conditions
        return obj

    def visit_select(self, select_ast: ast.Select):
        type: typ.Type = self.visit(select_ast.object)
        type = type.clone().hide_all_edges()
        self.visit_with_this(select_ast.body, type)
        return type

    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        assert type_ast.name.lexeme in self.types, f'Type {type_ast.name.lexeme} not defined.'
        return self.types[type_ast.name.lexeme]
    
    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        return None
    
    def visit_literal(self, literal_ast: ast.Literal):
        return None
    
    def visit_binary(self, binary_ast: ast.Binary):
        return None
    
    def visit_unary(self, unary_ast: ast.Unary):
        return None
    
    def visit_get(self, get_ast: ast.Get):
        return None
    
    def visit_call(self, call_ast: ast.Call):
        return None