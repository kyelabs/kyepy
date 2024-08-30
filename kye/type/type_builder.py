from __future__ import annotations
import typing as t

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.errors.compilation_errors import CompilationErrorReporter
from kye.type.native_types import NATIVE_TYPES
from kye.vm.op import OP

TOKEN_TO_OP = {
    ast.TokenType.PLUS: OP.ADD,
    ast.TokenType.MINUS: OP.SUB,
    ast.TokenType.STAR: OP.MUL,
    ast.TokenType.SLASH: OP.DIV,
    ast.TokenType.AND: OP.AND,
    ast.TokenType.OR: OP.OR,
    ast.TokenType.EQ: OP.EQ,
    ast.TokenType.NE: OP.NE,
    ast.TokenType.GT: OP.GT,
    ast.TokenType.GE: OP.GE,
    ast.TokenType.LT: OP.LT,
    ast.TokenType.LE: OP.LE,
    ast.TokenType.NOT: OP.NOT,
}

class TypeBuilder(ast.Visitor):
    """
    Responsible for interpreting the AST and building the types
    - Does not figure out the type of expressions
    - Converts expressions into it's own simplified representation
    """
    reporter: CompilationErrorReporter
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
            indexes=typ.Indexes([
                [index.lexeme for index in index_ast.names]
                for index_ast in model_ast.indexes
            ]),
            loc=model_ast.name.loc,
        )
        self.define(model)
        self.visit_with_this(model_ast.body, model)
        for index in model.indexes.edges:
            assert index in model, f'Index {index} not defined in model {model.name}'
    
    def visit_edge(self, edge_ast: ast.Edge):
        assert self.this is not None
        
        expr = self.visit(edge_ast.expr)
        returns = None
        if isinstance(expr, typ.Type):
            returns = expr
            expr = None
        
        edge = typ.Edge(
            name=edge_ast.name.lexeme,
            title=edge_ast.title,
            indexes=typ.Indexes([
                [index.lexeme for index in index_ast.names]
                for index_ast in edge_ast.params
            ]),
            allows_null=edge_ast.cardinality.allows_null,
            allows_many=edge_ast.cardinality.allows_many,
            model=self.this,
            returns=returns,
            expr=expr,
            loc=edge_ast.name.loc,
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
        assert self.this is not None
        # assert typ.has_compatible_source(obj, self.this)
        expr = self.visit(assert_ast.expr)
        assert isinstance(expr, typ.Cmd)
        assertion = typ.Assertion(
            expr=expr,
            loc=assert_ast.keyword.loc,
        )
        self.this.assertions.append(assertion)

    def visit_filter(self, filter_ast: ast.Filter):
        obj: typ.Type = self.visit(filter_ast.object)
        obj = obj.clone()
        obj.filters += [
            self.visit_with_this(cond, obj)
            for cond in filter_ast.conditions
        ]
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
        edge_name = edge_ast.name.lexeme
        
        if self.this is not None and \
                edge_name in self.this and \
                self.this[edge_name].expr is not None:
            return self.this[edge_name].expr

        return typ.Cmd(OP.COL, [edge_name])
    
    def visit_literal(self, literal_ast: ast.Literal):
        return typ.Cmd(OP.VAL, [literal_ast.value])
    
    def visit_binary(self, binary_ast: ast.Binary):
        left = self.visit(binary_ast.left)
        right = self.visit(binary_ast.right)
        if not isinstance(left, typ.Cmd) or not isinstance(right, typ.Cmd):
            raise NotImplementedError('Binary operations not yet implemented for types')
        
        op = TOKEN_TO_OP[binary_ast.operator.type]
        return typ.Cmd(op, (left, right))

    def visit_unary(self, unary_ast: ast.Unary):
        right = self.visit(unary_ast.right)
        if not isinstance(right, typ.Cmd):
            raise NotImplementedError('Unary operations not yet implemented for types')
        op = TOKEN_TO_OP[unary_ast.operator.type]
        return typ.Cmd(op, (right,))

    def visit_get(self, get_ast: ast.Get):
        # obj = self.visit(get_ast.object)
        # edge = get_ast.name.lexeme
        # if edge == 'matches':
        #     return type.Cmd(OP.MATCHES, (obj, get_ast.))
        # if isinstance(obj, typ.Type):
        raise NotImplementedError('Get operations not yet implemented')

    def visit_call(self, call_ast: ast.Call):
        arguments = call_ast.arguments
        if isinstance(call_ast.object, (ast.TypeIdentifier, ast.EdgeIdentifier)):
            edge = call_ast.object.name.lexeme
        # elif isinstance(call_ast.object, ast.Get):
        #     edge = call_ast.object.name.lexeme
        #     arguments = (call_ast.object.object,) + arguments
        else:
            raise NotImplementedError('cannot call an expression')

        # Visit the arguments
        args = [self.visit(arg) for arg in arguments]
        if any(isinstance(arg, typ.Type) for arg in args):
            raise NotImplementedError('Call operations not yet implemented for types')

        if edge == 'matches':
            assert len(arguments) == 2
            return typ.Cmd(OP.MATCHES, args)
        
        raise NotImplementedError('Call operations not yet implemented')