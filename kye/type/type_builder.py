from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.type.native_types import NATIVE_TYPES


class TypeBuilder(ast.Visitor):
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
        
        value: typ.Type = self.visit(edge_ast.expr)
        value = value.clone()
        value.source = self.this.source
        
        edge = typ.Edge(
            name=edge_ast.name.lexeme,
            indexes=typ.Indexes(edge_ast.params),
            allows_null=edge_ast.cardinality.allows_null,
            allows_many=edge_ast.cardinality.allows_many,
            input=self.this,
            output=value,
            # TODO: only set expr if the type is not calculated
            expr=edge_ast.expr,
        )
        
        self.this.define(edge)
    
    def visit_type(self, type_ast: ast.Type):
        value = self.visit(type_ast.expr)
        assert isinstance(value, typ.Type)
        type = value.clone()
        type.name = type_ast.name.lexeme
        self.define(type)
        return type

    def after_expr(self, expr_ast: ast.Expr, type: typ.Type):
        if type is not None:
            assert isinstance(type, typ.Type)
            self.types[expr_ast] = type
        return type
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        return self.types.get(type_ast.name.lexeme)

    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        assert self.this is not None
        edge_name = edge_ast.name.lexeme
        if edge_name not in self.this:
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_name} not defined.')
        return self.this[edge_name].output
    
    def visit_literal(self, literal_ast: ast.Literal):
        if type(literal_ast.value) is bool:
            t = self.types['Boolean'].clone()
        elif type(literal_ast.value) is float:
            t = self.types['Number'].clone()
        elif type(literal_ast.value) is str:
            t = self.types['String'].clone()
        else:
            raise NotImplementedError(f'Literal type {type(literal_ast.value)} not implemented.')
        t.is_const = True
        return t
    
    def visit_binary(self, binary_ast: ast.Binary):
        left: typ.Type = self.visit(binary_ast.left)
        right: typ.Type = self.visit(binary_ast.right)
        assert typ.has_compatible_source(left, right)
        
        op = binary_ast.operator.type
        if op.is_mathematical:
            # TODO: Instead of just returning a single ancestor, 
            # return a list of common ancestors, and the find the
            # first one that implements the operator
            common_ancestor = typ.common_ancestor(left, right)
            if common_ancestor is None:
                raise KyeRuntimeError(binary_ast.operator, 'Type mismatch')
            out = common_ancestor
        elif op.is_comparison:
            out = self.types['Boolean']
        elif op is ast.TokenType.AND:
            raise NotImplementedError('Type intersection not implemented')
        elif op is ast.TokenType.OR:
            raise NotImplementedError('Type union not implemented')
        else:
            raise NotImplementedError(f'Unknown operator {op}')
        
        out = out.clone()
        out.is_const = left.is_const and right.is_const
        out.source = left.source or right.source
        return out

    def visit_assert(self, assert_ast: ast.Assert):
        type: typ.Type = self.visit(assert_ast.expr)
        assert self.this is not None
        assert typ.has_compatible_source(type, self.this)
        self.this.assertions.append(assert_ast.expr)

    def visit_filter(self, filter_ast: ast.Filter):
        type: typ.Type = self.visit(filter_ast.object)
        type = type.clone()
        for condition in filter_ast.conditions:
            condition_type = self.visit_with_this(condition, type)
            # TODO: Check that condition_type is a boolean?
            type.filters.append(condition)
        return type

    def visit_select(self, select_ast: ast.Select):
        type: typ.Type = self.visit(select_ast.object)
        type = type.clone().hide_all_edges()
        self.visit_with_this(select_ast.body, type)
        return type