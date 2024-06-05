from __future__ import annotations
import typing as t

import kye.expressions as ast
import kye.types as typ
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.engine import Engine
from kye.native_types import NATIVE_TYPES


class TypeBuilder(ast.Visitor):
    reporter: ErrorReporter
    this: t.Optional[typ.Type]
    types: t.Dict[str, typ.Type]
    
    def __init__(self, reporter: ErrorReporter):
        self.reporter = reporter
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
    
    def visit_script(self, script_ast: ast.Script):
        for statement in script_ast.statements:
            self.visit(statement)

    def visit_block(self, block_ast: ast.Script):
        for statement in block_ast.statements:
            self.visit(statement)

    def visit_model(self, model_ast: ast.Model):
        model = typ.Model(
            name=model_ast.name.lexeme,
            indexes=typ.Indexes(model_ast.indexes)
        )
        self.define(model)
        self.visit_with_this(model_ast.body, model)
    
    def visit_edge(self, edge_ast: ast.Edge):
        assert self.this is not None
        
        value=self.visit(edge_ast.body)
        
        edge = typ.Edge(
            name=edge_ast.name.lexeme,
            indexes=typ.Indexes(edge_ast.params),
            allows_null=edge_ast.cardinality.allows_null,
            allows_many=edge_ast.cardinality.allows_many,
            input=self.this,
            output=value,
            # TODO: only set expr if the type is not calculated
            expr=edge_ast.body,
        )
        
        self.this.define(edge)
    
    def visit_type(self, type_ast: ast.Type):
        value = self.visit(type_ast.value)
        assert isinstance(value, typ.Type)
        type = value.create_child(new_name=type_ast.name.lexeme)
        self.define(type)
        return type
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        return self.types.get(type_ast.name.lexeme)

    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        assert self.this is not None
        edge_name = edge_ast.name.lexeme
        if edge_name not in self.this:
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_name} not defined.')
        return self.this[edge_name]
    
    def visit_literal(self, literal_ast: ast.Literal):
        if type(literal_ast.value) is bool:
            return self.types['Boolean']
        if type(literal_ast.value) is float:
            return self.types['Number']
        if type(literal_ast.value) is str:
            return self.types['String']
        raise NotImplementedError(f'Literal type {type(literal_ast.value)} not implemented.')