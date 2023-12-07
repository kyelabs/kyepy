from __future__ import annotations
from functools import cached_property
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
                 expr: Optional[Expression] = None,
                 extends: Optional[Type] = None,
                 ):
        self.ref = ref
        self.indexes = indexes
        self.edges = {}
        self.loc = loc
        self.expr = expr
        self.extends = extends
        if expr is not None:
            assert isinstance(expr, Expression)
            assert extends is None
            self.extends = expr.returns
        assert isinstance(self.extends, Type) or ref == 'Object', 'Everything is supposed to at least inherit from `Object`'

    def _inheritance_chain(self):
        base = self
        yield base
        while base.extends is not None:
            base = base.extends
            yield base

    @cached_property
    def kind(self) -> Literal['String','Number','Boolean','Object']:
        for typ in self._inheritance_chain():
            if typ.ref in ('String','Number','Boolean','Object'):
                return typ.ref
        raise Exception('Everything is supposed to at least inherit from `Object`')
    
    @cached_property
    def has_index(self) -> bool:
        return len(self.indexes) > 0

    @cached_property
    def index(self) -> set[EDGE]:
        """ Flatten the 2d list of indexes """
        return {idx for idxs in self.indexes for idx in idxs}
    
    def __getitem__(self, name: EDGE) -> Edge:
        return self.edges[name]

    def __contains__(self, name: EDGE) -> bool:
        return name in self.edges
    
    def __repr__(self):
        non_index_edges = [edge for edge in self.edges.keys() if edge not in self.index]
        return "Type<{}{}{}{}>".format(
            self.ref or '',
            ':' + self.extends.ref if self.extends is not None and self.extends.ref is not 'Object' else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

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
        return '{}<{}>'.format(
            self.__class__.__name__,
            re.sub(r'\s+', ' ', self.loc.text) if self.loc else '',
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
    bound: Optional[Expression]
    edge: Edge
    args: list[Expression]

    def __init__(self,
                 edge: Edge,
                 bound: Optional[Expression] = None,
                 args: list[Expression] = [],
                 loc: Optional[TokenPosition] = None
                 ):
        returns = edge.returns

        # Have not figured out template functions yet,
        # so here is my hack for $filter
        if edge.name == '$filter':
            assert bound is not None
            returns = bound.returns

        super().__init__(returns=returns, loc=loc)
        self.bound = bound
        self.args = args
        self.edge = edge

Models = dict[str, Type]