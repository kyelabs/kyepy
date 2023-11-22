from __future__ import annotations
from typing import Optional, Literal, Any
import kye.parser.kye_ast as AST

class Type:
    ref: Optional[str] = None
    name: Optional[str] = None
    extends: Optional[str] = None
    indexes: list[list[str]] = []
    filters: dict[str, tuple[Any]] = {}

    def __init__(self,
                 ref: str = None,
                 name: str = None,
                 extends: str = None,
                 indexes: list[list[str]] = [],
                 filters: dict[str, tuple[Any]] = {}):
        self.ref = ref
        self.name = name
        self.extends = extends
        self.indexes = indexes
        self.filters = filters
    
    @property
    def index(self) -> list[str]:
        """ Flatten the 2d list of indexes """
        return list({idx for idxs in self.indexes for idx in idxs})

    def __repr__(self):
        return "Type<{}{}{}{}>".format(
            self.ref or self.name or '',
            ':' + self.extends if self.extends else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
        )

class Edge:
    name: str
    model: Type
    returns: Type
    parameters: list[Type]
    nullable: bool
    multiple: bool
    expression: Optional[str]

    def __init__(self,
                 name: str,
                 model: Type,
                 returns: Type,
                 parameters: list = [],
                 nullable: bool = False,
                 multiple: bool = False,
                 expression: Optional[str] = None,
                 ):
        self.name = name
        self.model = model
        self.returns = returns
        self.parameters = parameters
        self.nullable = nullable
        self.multiple = multiple
        self.expression = expression

    def __repr__(self):
        return "Edge<{}{}>".format(
            self.name or '',
            ([['' ,'+'],
                ['?','*']])[int(self.nullable)][int(self.multiple)],
        )

class Registry:
    definitions: dict[str, Type]

    def define(ref: str, ast: Optional[AST.Definition] = None):
        pass