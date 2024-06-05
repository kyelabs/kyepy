from __future__ import annotations
import typing as t
from copy import copy
from dataclasses import dataclass, field

import kye.expressions as ast

class Indexes:
    tokens: t.Dict[str, t.List[ast.Token]]
    sets: t.List[t.Tuple]
    edges: t.Set[str]
    
    def __init__(self, indexes: t.List[ast.Index]):
        self.ast = {}
        self.sets = []
        self.edges = set()

        for index in indexes:
            items = tuple(token.lexeme for token in index.names)
            self.sets.append(items)
            for token in index.names:
                if not token.lexeme in self.ast:
                    self.ast[token.lexeme] = []
                self.ast[token.lexeme].append(token)
                self.edges.add(token.lexeme)
    
    def __len__(self):
        return len(self.sets)


@dataclass(frozen=True)
class Edge:
    name: str
    indexes: Indexes
    allows_null: bool
    allows_many: bool
    input: Type
    output: Type
    expr: t.Optional[ast.Expr]

class Type:
    name: str
    edges: t.Dict[str, Edge]
    filters: t.List[ast.Expr]
    assertions: t.List[ast.Expr]
    
    def __init__(self, name, edges={}, filters=[], assertions=[]):
        self.name = name
        self.edges = edges
        self.filters = filters
        self.assertions = assertions
    
    def create_child(self, new_name=None, new_edges={}, new_filters=[], new_assertions=[]):
        child = Type(
            name=new_name or self.name,
            edges=copy(self.edges),
            filters=self.filters + new_filters,
            assertions=self.assertions + new_assertions,
        )
        for edge in new_edges:
            child.define(edge)
        return child
    
    def __iter__(self):
        return iter(self.edges)
    
    def __contains__(self, edge_name):
        return edge_name in self.edges
    
    def __getitem__(self, edge_name):
        return self.edges[edge_name]
    
    def define(self, edge: Edge):
        # TODO: Check if we are overriding an inherited edge
        # if we are, then check that this type is a subtype of the inherited type
        self.edges[edge.name] = edge


class Model(Type):
    indexes: Indexes
    
    def __init__(self, name, indexes, edges={}, filters=[], assertions=[]):
        super().__init__(name, edges, filters, assertions)
        self.indexes = indexes
    
    def create_child(self, new_name=None, new_edges={}, new_filters=[], new_assertions=[]):
        child = Model(
            name=new_name or self.name,
            indexes=self.indexes,
            edges=copy(self.edges),
            filters=self.filters + new_filters,
            assertions=self.assertions + new_assertions,
        )
        for edge in new_edges:
            child.define(edge)
        return child