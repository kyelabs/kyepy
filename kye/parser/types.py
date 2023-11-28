from __future__ import annotations
from typing import Optional, Literal, Any
import kye.parser.kye_ast as AST

class Type:
    name: str
    edges: dict[str, Edge]

    def __init__(self, name: str, edges: dict[str, Edge]):
        self.name = name
        self.edges = edges

class FilteredType(Type):
    extends: Type
    filter: Edge

    def __init__(self, extends: Type, filter: Edge):
        super().__init__(name=extends.name, edges=extends.edges)
        self.extends = extends
        self.filter = filter

class PrimitiveType(Type):
    name: Literal['String', 'Number', 'Boolean']

class FilteredPrimitiveType(PrimitiveType, FilteredType):
    extends: PrimitiveType

class ComposedType(Type):
    indexes: list[list[str]]

class FilteredComposedType(ComposedType, FilteredType):
    extends: ComposedType

class Edge:
    name: str
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