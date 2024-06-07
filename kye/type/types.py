from __future__ import annotations
import typing as t
from dataclasses import dataclass
from copy import deepcopy
from functools import cached_property

import kye.parse.expressions as ast

class Indexes:
    tokens: t.Dict[str, t.List[ast.Token]]
    sets: t.List[t.Tuple]
    edges: t.List[str]
    
    def __init__(self, indexes: t.List[ast.Index]):
        self.ast = {}
        self.sets = []
        edges = set()

        for index in indexes:
            items = tuple(token.lexeme for token in index.names)
            self.sets.append(items)
            for token in index.names:
                if not token.lexeme in self.ast:
                    self.ast[token.lexeme] = []
                self.ast[token.lexeme].append(token)
                edges.add(token.lexeme)
        
        self.edges = sorted(edges)
    
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
    order: int = -1

class Type:
    name: str
    source: t.Optional[str]
    parent: t.Optional[Type]
    edges: t.Dict[str, Edge]
    edge_order: t.List[str]
    filters: t.List[ast.Expr]
    assertions: t.List[ast.Expr]
    is_const: bool = False
    
    def __init__(self, name: str, source: t.Optional[str]):
        self.name = name
        self.source = source
        self.parent = None
        self.edges = {}
        self.edge_order = []
        self.filters = []
        self.assertions = []
        self.is_const = False
        
    def clone(self) -> t.Self:
        child = deepcopy(self)
        child.parent = self
        return child

    @cached_property
    def ancestors(self) -> t.List[Type]:
        ancestors = []
        current = self
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def __iter__(self):
        return iter(self.edges)
    
    def __contains__(self, edge_name):
        return edge_name in self.edges
    
    def __getitem__(self, edge_name):
        return self.edges[edge_name]
    
    def define(self, edge: Edge) -> t.Self:
        # TODO: Check if we are overriding an inherited edge
        # if we are, then check that this type is a subtype of the inherited type
        self.edge_order.append(edge.name)
        self.edges[edge.name] = edge
        return self
    
    def hide_all_edges(self) -> t.Self:
        self.edge_order = []
        return self

class Model(Type):
    source: str
    indexes: Indexes
    
    def __init__(self, name, source, indexes):
        assert source is not None, "Model source must not be None"
        super().__init__(name, source)
        self.indexes = indexes


def has_compatible_source(lhs: Type, rhs: Type) -> bool:
    return lhs.source is None\
        or rhs.source is None\
        or lhs.source == rhs.source

def common_ancestor(lhs: Type, rhs: Type) -> t.Optional[Type]:
    for ancestor in lhs.ancestors:
        if ancestor in rhs.ancestors:
            return ancestor
    return None

Types = t.Dict[str, Type]