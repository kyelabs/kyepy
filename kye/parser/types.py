from __future__ import annotations
from typing import Optional, Literal, Any
import kye.parser.kye_ast as AST

class Type:
    name: Optional[str] = None
    extends: Optional[Type] = None
    indexes: list[list[str]] = []
    filters: dict[str, tuple[Any]] = {}
    edges: dict[str, Edge] = {}

    def __init__(self,
                 name: Optional[str] = None,
                 extends: Type = None,
                 indexes: list[list[str]] = [],
                 filters: dict[str, tuple[Any]] = {},
                 edges: dict[str, Edge] = {},
                ):
        self.name = name
        self.extends = extends
        self.indexes = indexes
        self.filters = filters
        self.edges = edges
        for name, edge in self.edges.items():
            edge.model = self

    @property
    def has_edges(self) -> bool:
        return len(self.edges) > 0
    
    @property
    def has_index(self) -> bool:
        return len(self.indexes) > 0

    @property
    def base(self) -> Type:
        return self.extends if self.extends else self
    
    @property
    def index(self) -> list[str]:
        """ Flatten the 2d list of indexes """
        return list({idx for idxs in self.indexes for idx in idxs})

    def __repr__(self):
        non_index_edges = [
            repr(edge) for edge in self.edges.values()
            if edge.name not in self.index
        ]
        return "Type<{}{}{}>".format(
            self.name or '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            "{" + ','.join(non_index_edges) + "}" if len(non_index_edges) > 0 else '',
        )

class Edge:
    name: str
    model: Optional[Type]
    returns: Type
    parameters: list[Type]
    nullable: bool
    multiple: bool
    expression: Optional[str]

    def __init__(self,
                 name: str,
                 returns: Type,
                 parameters: list = [],
                 nullable: bool = False,
                 multiple: bool = False,
                 expression: Optional[str] = None,
                 ):
        self.name = name
        self.returns = returns
        self.parameters = parameters
        self.nullable = nullable
        self.multiple = multiple
        self.expression = expression
        self.model = None

    def __repr__(self):
        return "{}{}".format(
            self.name,
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)]
        )