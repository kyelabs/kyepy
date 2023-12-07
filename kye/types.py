from __future__ import annotations
from typing import Optional, Literal, Union
from kye.parser.kye_ast import TokenPosition

TYPE_REF = str
EDGE_REF = str
EDGE = str

class Definition:
    """ Abstract Class for Type and Edge Definitions """
    ref: str
    expr: Optional[Expression]
    returns: Type
    loc: Optional[TokenPosition]

class Type(Definition):
    ref: TYPE_REF
    indexes: list[list[EDGE]]
    edges: dict[EDGE, Edge]
    extends: Optional[Type]

    def __init__(self,
                 ref: TYPE_REF,
                 indexes: list[list[EDGE]] = [],
                 loc: Optional[TokenPosition] = None,
                 extends: Type = None,
                 ):
        self.ref = ref
        self.indexes = indexes
        self.edges = {}
        self.loc = loc
        self.expr = None
        self.extends = extends
        assert isinstance(extends, Type) or extends is None

    def _inheritance_chain(self):
        base = self
        yield base
        while base.extends is not None:
            base = base.extends
            yield base

    @property
    def kind(self) -> Literal['String','Number','Boolean','Object']:
        for typ in self._inheritance_chain():
            if typ.ref in ('String','Number','Boolean','Object'):
                return typ.ref
        raise Exception('Everything is supposed to at least inherit from `Object`')
    
    @property
    def has_index(self) -> bool:
        return len(self.indexes) > 0

    @property
    def index(self) -> list[EDGE]:
        """ Flatten the 2d list of indexes """
        return [idx for idxs in self.indexes for idx in idxs]
    
    def __getitem__(self, name: EDGE) -> Edge:
        return self.edges[name]

    def __contains__(self, name: EDGE) -> bool:
        return name in self.edges
    
    def __repr__(self):
        return "Type<{}>".format(self.ref)

class Edge(Definition):
    name: EDGE
    model: Type
    args: list[Type]
    nullable: bool = False
    multiple: bool = False
    
    def __init__(self,
                 name: EDGE,
                 model: Type,
                 nullable: bool = False,
                 multiple: bool = False,
                 args: list[Type] = [],
                 loc: Optional[TokenPosition] = None,
                 expr: Optional[Expression] = None,
                 returns: Type = None
                ):
        self.name = name
        self.model = model
        self.nullable = nullable
        self.multiple = multiple
        self.args = args
        self.loc = loc
        self.expr = expr
        self.returns = returns
        if self.returns is None:
            assert self.expr is not None
            self.returns = self.expr.returns
        assert isinstance(self.returns, Type)
    
    @property
    def ref(self) -> EDGE_REF:
        return self.model.ref + '.' + self.name
    
    @property
    def is_in_index(self) -> bool:
        return self.name in self.model.index
    
    def __repr__(self):
        return 'Edge<{}{}>'.format(
            self.ref,
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)]
        )

class Expression:
    returns: Type
    loc: Optional[TokenPosition]

    def __init__(self,
                 returns: Type,
                 loc: Optional[TokenPosition] = None
                 ):
        assert isinstance(returns, Type)
        self.returns = returns
        self.loc = loc
    
    def __repr__(self):
        import re
        return 'Expr<{}>'.format(
            re.sub(r'\s+', ' ', self.loc.text) if self.loc else ''
        )

class LiteralExpression(Expression):
    value: Union[str, int, float, bool]

    def __init__(self,
                 returns: Type,
                 value: Union[str, int, float, bool],
                 loc: Optional[TokenPosition] = None
                 ):
        super().__init__(returns=returns, loc=loc)
        self.value = value

class CallExpression(Expression):
    bound: Expression
    edge: Edge
    args: list[Expression]

    def __init__(self,
                 bound: Expression,
                 args: list[Expression],
                 returns: Type,
                 edge: Edge,
                 loc: Optional[TokenPosition] = None
                 ):
        super().__init__(returns=returns, loc=loc)
        self.bound = bound
        self.args = args
        self.edge = edge

Models = dict[str, Type]