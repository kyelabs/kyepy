from __future__ import annotations
import typing as t
from dataclasses import dataclass
from copy import deepcopy
from functools import cached_property
import enum

import kye.parse.expressions as ast
from kye.parse.expressions import Location

class Operator(enum.Enum):
    SUB = '-'
    ADD = '+'
    MUL = '*'
    DIV = '/'
    MOD = '%'
    INV = "~"

    NOT = "!"
    NE = "!="
    EQ = "=="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    
    AND = "&"
    OR = "|"
    XOR = "^"
    
    IN = "in"
    IS = "is"
    
    @property
    def edge_name(self):
        return '$' + self.name.lower()
    
    @property
    def is_unary(self):
        return self in (Operator.INV, Operator.NOT)
    
    @property
    def is_mathematical(self):
        return self in (Operator.SUB, Operator.ADD, Operator.MUL, Operator.DIV, Operator.MOD)
    
    @property
    def is_comparison(self):
        return self in (Operator.EQ, Operator.NE, Operator.GT, Operator.GE, Operator.LT, Operator.LE)

class Expr:
    name: str
    args: t.Tuple[Expr, ...]

    def __init__(self, name: str, args: t.Iterable[Expr]):
        self.name = name
        self.args = tuple(args)
    
    def __repr__(self):
        return f"{self.name}({', '.join(repr(arg) for arg in self.args)})"

class Const(Expr):
    value: t.Any

    def __init__(self, value: t.Any):
        super().__init__('const', [])
        self.value = value

    def __repr__(self):
        return repr(self.value)

class Var(Expr):
    name: str

    def __init__(self, name: str):
        super().__init__('var', [])
        self.name = name

    def __repr__(self):
        return f"Var({self.name!r})"


class Indexes:
    tokens: t.Dict[str, t.List[ast.Token]]
    sets: t.List[t.Tuple]
    edges: t.List[str]
    
    def __init__(self, indexes: t.Iterable[ast.Index]):
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
    expr: t.Optional[Expr]
    loc: t.Optional[Location]

@dataclass(frozen=True)
class Assertion:
    expr: Expr
    loc: t.Optional[Location]

class Type:
    name: str
    source: t.Optional[str]
    parent: t.Optional[Type]
    edges: t.Dict[str, Edge]
    edge_order: t.List[str]
    filters: t.List[Expr]
    assertions: t.List[Assertion]
    is_const: bool = False
    
    def __init__(self, name: str, source: t.Optional[str], loc: t.Optional[Location] = None):
        self.name = name
        self.source = source
        self.loc = loc
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
    
    def __init__(self, name, source, indexes, loc=None):
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