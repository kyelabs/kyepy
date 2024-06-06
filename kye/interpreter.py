from __future__ import annotations
import typing as t
from copy import copy
from dataclasses import dataclass
import ibis

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.parse.expressions as ast

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

@dataclass
class Edge:
    name: str
    indexes: Indexes
    allows_null: bool
    allows_many: bool
    expr: t.Optional[ast.Expr]
    order: int = -1

Edges = t.Dict[str, Edge]

class Model(Type):
    name: str
    indexes: Indexes
    table: ibis.Table
    edges: Edges

    def __init__(self, interpreter: Interpreter, name: str, indexes: Indexes, edges: Edges, table: ibis.Table):
        self.interpreter = interpreter
        self.name = name
        self.indexes = indexes
        self.edges = edges
        self.table = table
    
    def __copy__(self) -> Model:
        return Model(self.interpreter, self.name, self.indexes, {
            edge.name: copy(edge)
            for edge in self.edges.values()
        }, self.table)
    
    def _filter(self, table) -> Model:
        copied = copy(self)
        copied.table = table
        return copied
    
    def set(self, edge: Edge):
        edge.order = len(self.edges)
        self.edges[edge.name] = edge
    
    def has(self, name: str):
        return name in self.edges
    
    def get(self, name: str):
        edge = self.edges[name]
        if name in self.table.columns:
            return self.table[name]
        elif edge.expr is not None:
            col = self.interpreter.visit_with_this(edge.expr, self)
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
    
    def hide_all_edges(self) -> t.Self:
        for edge in self.edges.values():
            edge.order = -1
        return self
    
    def __str__(self):
        return self.table.select(*[
            t.cast(ibis.Value, self.get(edge.name))
            for edge in sorted(self.edges.values(), key=lambda edge: edge.order)
            if edge.order >= 0
        ]).__str__()

class Interpreter(ast.Visitor):
    engine: Engine
    reporter: ErrorReporter
    this: t.Optional[Type]
    types: t.Dict[str, Type]
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.types = {}
        self.this = None
    
    def visit_with_this(self, node_ast: ast.Node, this: Type):
        previous = self.this
        self.this = this
        result = self.visit(node_ast)
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
        
        edge = Edge(
            name=edge_name,
            indexes=params,
            allows_null=edge_ast.cardinality.allows_null,
            allows_many=edge_ast.cardinality.allows_many,
            expr=edge_ast.expr
        )

        assert self.this is not None
        assert isinstance(self.this, Model)

        self.this.set(edge)
    
    def visit_type(self, type_ast: ast.Type):
        value = self.visit(type_ast.expr)
        assert isinstance(value, Model), 'Can only set alias to models.'
        type = copy(value)
        type.name = type_ast.name.lexeme
        self.types[type.name] = type
        return type
    
    def visit_type_identifier(self, type_ast: ast.TypeIdentifier):
        return self.types.get(type_ast.name.lexeme)
    
    def visit_edge_identifier(self, edge_ast: ast.EdgeIdentifier):
        if self.this is None:
            raise KyeRuntimeError(edge_ast.name, 'Edge used outside of model.')
        if not self.this.has(edge_ast.name.lexeme):
            raise KyeRuntimeError(edge_ast.name, f'Edge {edge_ast.name.lexeme} not defined.')
        return self.this.get(edge_ast.name.lexeme)
    
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
        type = self.visit(call_ast.object)
        assert isinstance(type, Type), 'Can only call types.'
        arguments = [self.visit(argument) for argument in call_ast.arguments]
        if type is None and len(arguments) == 0:
            return arguments[0]
        return type.call(arguments)

    def visit_get(self, get_ast: ast.Get):
        type = self.visit(get_ast.object)
        edge_name = get_ast.name.lexeme
        assert isinstance(type, Type), 'Can only access edges on tables.'
        if not type.has(get_ast.name.lexeme):
            raise KyeRuntimeError(get_ast.name, f'Edge {get_ast.name.lexeme} not defined.')
        return type.get(edge_name)
    
    def visit_filter(self, filter_ast: ast.Filter):
        type = self.visit(filter_ast.object)
        assert isinstance(type, Type), 'Can only filter on tables.'
        conditions = [self.visit_with_this(argument, type) for argument in filter_ast.conditions]
        condition = conditions.pop(0)
        for cond in conditions:
            condition = condition & cond
        return type.filter(condition)
    
    def visit_select(self, select_ast: ast.Select):
        type = self.visit(select_ast.object)
        assert isinstance(type, Model), 'Can only select on models.'
        model = copy(type).hide_all_edges()
        
        self.visit_with_this(select_ast.body, model)

        return model
    
    def visit_assert(self, assert_ast: ast.Assert):
        assert self.this is not None, 'Assertion used outside of model.'
        assert isinstance(self.this, Model), 'Assertion used outside of model.'
        value = self.visit(assert_ast.expr)
        invalid_count = self.this.filter(~value).table.count().execute()
        if invalid_count > 0:
            raise KyeRuntimeError(assert_ast.keyword, 'Assertion failed.')