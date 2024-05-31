from __future__ import annotations
import typing as t
import kye.expressions as ast
import ibis
from copy import copy

from kye.errors import ErrorReporter, KyeRuntimeError

if t.TYPE_CHECKING:
    from kye.engine import Engine

    Indexes = t.List[t.List[str]]


def flatten_indexes(indexes: Indexes) -> t.List[str]:
    return list({index for index_list in indexes for index in index_list})

class Type:
    """ Abstract class for types """
    name: str

    def call(self, arguments):
        raise NotImplementedError()

    def has(self, name: str):
        raise NotImplementedError()

    def get(self, name: str):
        raise NotImplementedError()
    
    def filter(self, condition):
        raise NotImplementedError()
    
    def __str__(self):
        return "<type>"

class Model(Type):
    name: str
    indexes: Indexes
    methods: t.Dict[str, ast.Expr]
    table: ibis.Table

    def __init__(self, interpreter: Interpreter, name: str, indexes: Indexes, methods: t.Dict[str, ast.Expr], table: ibis.Table):
        self.interpreter = interpreter
        self.name = name
        self.indexes = indexes
        self.methods = methods
        self.table = table
    
    def _filter(self, table) -> Model:
        return Model(self.interpreter, self.name, self.indexes, copy(self.methods), table)
    
    def has(self, name: str):
        return name in self.methods or name in self.table.columns
    
    def get(self, name: str):
        if name in self.table.columns:
            return self.table[name]
        if name in self.methods:
            col = self.interpreter.visit_with_this(self.methods[name], self)
            col = col.name(name)
            return col
        return None
    
    def call(self, arguments) -> Model:
        assert len(self.indexes) == 1, 'Only one index supported.'
        index = self.indexes[0]
        assert len(arguments) == len(index), 'Expected one argument for each index.'
        return self._filter(self.table.filter([
            self.table[key] == val
            for key, val in zip(index, arguments)
        ]))
    
    def filter(self, condition) -> Model:
        return self._filter(self.table.filter(condition))
    
    def __str__(self):
        return self.table.mutate(**{
            edge: t.cast(ibis.Value, self.get(edge))
            for edge in self.methods
        }).__str__()

class Interpreter(ast.Visitor):
    engine: Engine
    table_index_map: t.Dict[str, Indexes]
    reporter: ErrorReporter
    this: t.Optional[Type]
    types: t.Dict[str, Type]
    calculated_edges: t.Dict[str, ibis.Column]
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.types = {}
        self.this = None
    
    def visit_with_this(self, node: ast.Node, this: Type):
        previous = self.this
        self.this = this
        result = self.visit(node)
        self.this = previous
        return result
        
    def visit_model(self, model_ast: ast.Model):
        if len(model_ast.indexes) == 0:
            raise KyeRuntimeError(model_ast.name, 'Models without indexes are not yet supported.')
        if len(model_ast.indexes) > 1:
            raise KyeRuntimeError(model_ast.name, 'Models with multiple indexes are not yet supported.')
        # TODO: Type check all indexes have a corresponding edge defined

        model_name = model_ast.name.lexeme
        indexes: Indexes = []
        for index_ast in model_ast.indexes:
            indexes.append([index.lexeme for index in index_ast.names])
        if len(indexes) == 0:
            raise KyeRuntimeError(model_ast.name, 'Model must have at least one index.')

        if not self.engine.has_table(model_name):
            raise KyeRuntimeError(model_ast.name, 'Table not found for model.')

        table = self.engine.get_table(model_name)
        model = Model(self, model_name, indexes, {}, table)
        self.types[model_name] = model

        self.visit_with_this(model_ast.body, model)
    
    def visit_edge(self, edge_ast: ast.Edge):
        
        edge_name = edge_ast.name.lexeme

        if len(edge_ast.params) > 0:
            raise KyeRuntimeError(edge_ast.name, 'Edges with parameters are not yet supported.')
        params = []

        assert self.this is not None
        assert isinstance(self.this, Model)

        if edge_name in self.this.methods:
            raise KyeRuntimeError(edge_ast.name, 'Edge has already been defined.')

        # TODO: only add as a method if it is a calculated field
        self.this.methods[edge_name] = edge_ast.body
    
    def visit_type_identifier(self, type: ast.TypeIdentifier):
        return self.types.get(type.name.lexeme)
    
    def visit_edge_identifier(self, edge: ast.EdgeIdentifier):
        if self.this is None:
            raise KyeRuntimeError(edge.name, 'Edge used outside of model.')
        if not self.this.has(edge.name.lexeme):
            raise KyeRuntimeError(edge.name, f'Edge {edge.name.lexeme} not defined.')
        return self.this.get(edge.name.lexeme)
    
    def visit_literal(self, literal: ast.Literal):
        return literal.value
    
    def visit_binary(self, binary: ast.Binary):
        left = self.visit(binary.left)
        right = self.visit(binary.right)
        if left is None or right is None:
            return None
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
        type = self.visit(call.callee)
        assert isinstance(type, Type), 'Can only call types.'
        arguments = [self.visit(argument) for argument in call.arguments]
        if type is None and len(arguments) == 0:
            return arguments[0]
        return type.call(arguments)

    def visit_get(self, get: ast.Get):
        type = self.visit(get.object)
        edge_name = get.name.lexeme
        assert isinstance(type, Type), 'Can only access edges on tables.'
        if not type.has(get.name.lexeme):
            raise KyeRuntimeError(get.name, f'Edge {get.name.lexeme} not defined.')
        return type.get(edge_name)
    
    def visit_filter(self, filter: ast.Filter):
        type = self.visit(filter.object)
        assert isinstance(type, Type), 'Can only filter on tables.'
        conditions = [self.visit_with_this(argument, type) for argument in filter.conditions]
        condition = conditions.pop(0)
        for cond in conditions:
            condition = condition & cond
        return type.filter(condition)