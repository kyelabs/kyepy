from __future__ import annotations
import typing as t
from dataclasses import dataclass
from copy import deepcopy
from functools import cached_property

import kye.parse.expressions as ast
from kye.parse.expressions import Location
from kye.vm.op import OP

Literal = t.Union[str, int, float, bool]

class Cmd:
    op: OP
    args: t.Tuple[t.Union[Cmd,Literal], ...]

    def __init__(self, op: OP, args: t.Iterable[t.Union[Cmd,Literal]]):
        self.op = op
        self.args = tuple(args)
    
    def __repr__(self):
        return f"{self.op}({', '.join(repr(arg) for arg in self.args)})"

class Indexes:
    sets: t.List[t.Tuple[str, ...]]
    edges: t.List[str]
    
    def __init__(self, indexes: t.Iterable[t.Iterable[str]]):
        self.sets = []
        edges = set()

        for index in indexes:
            self.sets.append(tuple(index))
            edges.update(index)
        
        self.edges = sorted(edges)
    
    def __contains__(self, key: str):
        return key in self.edges
    
    def __len__(self):
        return len(self.sets)


@dataclass(frozen=True)
class Edge:
    name: str
    indexes: Indexes
    allows_null: bool
    allows_many: bool
    model: Type
    title: t.Optional[str]
    returns: t.Optional[Type]
    expr: t.Optional[Cmd]
    loc: t.Optional[Location]

@dataclass(frozen=True)
class Assertion:
    expr: Cmd
    loc: t.Optional[Location]

class Type:
    name: str
    source: t.Optional[str]
    parent: t.Optional[Type]
    edges: t.Dict[str, Edge]
    edge_order: t.List[str]
    filters: t.List[Cmd]
    assertions: t.List[Assertion]
    
    def __init__(self,
                 name: str,
                 source: t.Optional[str],
                 loc: t.Optional[Location] = None
                 ):
        self.name = name
        self.source = source
        self.loc = loc
        self.parent = None
        self.edges = {}
        self.edge_order = []
        self.filters = []
        self.assertions = []
        
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
    
    def __contains__(self, edge_name: str):
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

    def __repr__(self):
        return f"Type({self.name!r})"

class Model(Type):
    source: str
    indexes: Indexes
    
    def __init__(self,
                 name: str,
                 source: str,
                 indexes: Indexes,
                 loc: t.Optional[Location]=None
                 ):
        assert source is not None, "Model source must not be None"
        super().__init__(name, source, loc)
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