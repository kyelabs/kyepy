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
            self.extends = expr.get_context()
        assert isinstance(self.extends, Type) or ref in ('Object','Type'), 'Everything is supposed to at least inherit from `Object`'

    def _inheritance_chain(self):
        base = self
        yield base
        while base.extends is not None:
            base = base.extends
            yield base
    
    def get_edge(self, name: str):
        for typ in self._inheritance_chain():
            if name in typ.edges:
                return typ.edges[name]
        raise Exception(f'Unknown edge `{self.ref}.{name}`')

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
            ':' + self.extends.ref if self.extends is not None and self.extends.ref != 'Object' else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

class Edge(Definition):
    name: EDGE
    model: Type
    args: list[Type]
    nullable: bool = False
    multiple: bool = False
    returns: Type
    
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
            self.returns = self.expr.get_context()
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
    """ Abstract Class for all Expression Types """
    returns: Type
    type: Optional[Type]
    loc: Optional[TokenPosition]

    def __init__(self,
                 returns: Type,
                 type: Optional[Type] = None,
                 loc: Optional[TokenPosition] = None
                 ):
        assert isinstance(returns, Type)
        self.returns = returns
        self.type = type
        self.loc = loc
    
    def is_type(self):
        return self.returns.ref == 'Type'
    
    def get_context(self):
        return self.type if self.type is not None else self.returns
    
    def __repr__(self):
        import re
        return '{}<{}>'.format(
            self.__class__.__name__,
            re.sub(r'\s+', ' ', self.loc.text) if self.loc else '',
        )

class TypeRefExpression(Expression):
    type: Type

    def __init__(self,
                 type: Type,
                 returns: Type,
                 loc: Optional[TokenPosition] = None,
                ):
        super().__init__(returns=returns, type=type, loc=loc)
        assert self.is_type()

class EdgeRefExpression(Expression):
    edge: Edge

    def __init__(self,
                 edge: Edge,
                 loc: Optional[TokenPosition] = None):
        super().__init__(returns=edge.returns, loc=loc)
        self.edge = edge

class LiteralExpression(Expression):
    value: Union[str, int, float, bool]

    def __init__(self,
                 type: Type,
                 value: Union[str, int, float, bool],
                 loc: Optional[TokenPosition] = None
                 ):
        super().__init__(returns=type, loc=loc, type=type)
        self.value = value

class CallExpression(Expression):
    bound: Expression
    edge: Edge
    args: list[Expression]

    def __init__(self,
                 bound: Expression,
                 edge: Edge,
                 args: list[Expression] = [],
                 loc: Optional[TokenPosition] = None
                 ):
        returns = edge.returns
        type = None

        # Have not figured out template functions yet,
        # so here is my hack for $filter
        if edge.name == '$filter':
            returns = bound.returns
            type = bound.type

        super().__init__(returns=returns, type=type, loc=loc)
        self.bound = bound
        self.args = args
        self.edge = edge

Models = dict[str, Type]