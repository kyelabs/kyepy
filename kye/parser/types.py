from __future__ import annotations
from typing import Optional, Literal, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from kye.parser.environment import Environment

class Expression:
    """ Abstract interface for Types, Edges & Values """
    name: Optional[str]
    env: Environment

    def extends(self, other: Expression) -> bool:
        raise NotImplementedError()

    def __getitem__(self, key: str) -> Edge:
        raise NotImplementedError()
    
    def __contains__(self, key: str) -> bool:
        raise NotImplementedError()

class Value(Expression):
    value: str | int | float | bool
    type: Type

    def __init__(self, type: Type, value: str | int | float | bool):
        super().__init__()
        self.name = None
        self.type = type
        self.value = value
    
    def extends(self, other: Expression) -> bool:
        if not self.type.extends(other):
            return False
        if isinstance(other, Value):
            return self.value == other.value
        return True
    
    def __getitem__(self, key: str) -> Edge:
        return self.type[key].bind(self)
    
    def __contains__(self, key: str) -> bool:
        return key in self.type
    
    def __repr__(self):
        return "{}({})".format(
            self.type.name,
            repr(self.value),
        )


class Type(Expression):
    name: str
    edges: dict[str, Edge]
    filter: Optional[Edge]

    def __init__(self,
                 name: str,
                 edges: Optional[dict[str, Edge]] = None,
                 filter: Optional[Edge] = None,
                 env: Optional[Environment] = None,
                 ):
        self.name = name
        self.edges = edges or {}
        self.filter = filter
        self.env = env
        assert self.env is None or self.env.name == name
    
    def _extend_filter(self, filter: Optional[Edge]):
        if self.filter:
            if filter is not None:
                filter = filter['__and__'].apply(self.filter)
            else:
                filter = self.filter
        return filter

    def _extend_edges(self, edges: dict[str, Edge]):
        edges = {**edges}
        for key, edge in self.edges.items():
            # If over writing the edge, ensure
            # that it can extend the parent's edge
            if key in edges:
                assert edges[key].extends(edge)
            else:
                edges[key] = edge
        return edges
    
    def extend(self,
               name: Optional[str] = None,
               edges: dict[str, Edge] = {},
               filter: Optional[Edge] = None,
               env: Optional[Environment] = None,
               ):
        return Type(
            name=name or self.name,
            edges=self._extend_edges(edges),
            filter=self._extend_filter(filter),
            env=env or self.env,
        )
    
    def extends(self, other: Expression) -> bool:
        if isinstance(other, Edge):
            return self.extends(other.returns)
        if isinstance(other, Value):
            return self.extends(other.type)
        if isinstance(other, Type):
            for other_key, other_edge in other.edges.items():
                if other_key not in self:
                    return False
                if not self[other_key].extends(other_edge):
                    return False
            # TODO: Also check if our filter is a subset of the other's filter?
            return True
        raise Exception('How did you get here?')

    def select(self, value: str | float | int | bool):
        return Value(type=self, value=value)
    
    def __getitem__(self, key: str) -> Edge:
        return self.edges[key]

    def __contains__(self, key: str):
        return key in self.edges
    
    def __repr__(self):
        return '{}{}'.format(
            self.name,
            '{' + ','.join(repr(edge) for edge in self.edges.values()) + '}' if len(self.edges) else '',
        )

class Model(Type):
    indexes: list[list[str]]

    def __init__(self,
                 name: str,
                 indexes: list[list[str]],
                 edges: dict[str, Edge] = {},
                 filter: Optional[Edge] = None,
                 env: Optional[Environment] = None,
                 ):
        super().__init__(name, edges, filter, env)
        assert len(indexes) > 0
        self.indexes = indexes
    
    def extend(self,
               name: Optional[str] = None,
               indexes: Optional[list[list[str]]] = None,
               edges: dict[str, Edge] = {},
               filter: Optional[Edge] = None,
               env: Optional[Environment] = None,
               ):
        return Model(
            name=name or self.name,
            indexes=indexes or self.indexes,
            edges=self._extend_edges(edges),
            filter=self._extend_filter(filter),
            env=env or self.env,
        )

    def extends(self, other: Expression) -> bool:
        if not super().extends(other):
            return False
        if isinstance(other, Model):
            indexes = {tuple(idx) for idx in self.indexes}
            for other_idx in other.indexes:
                if tuple(other_idx) not in indexes:
                    return False
        return True

    @property
    def index(self) -> set[str]:
        """ Flatten the 2d list of indexes into a set """
        return {idx for idxs in self.indexes for idx in idxs}

    def __repr__(self):
        non_index_edges = [
            repr(self.edges[edge])
            for edge in self.edges.keys()
            if edge not in self.index
        ]
        return '{}{}{}'.format(
            self.name,
            ''.join('(' + ','.join(repr(self.edges[edge]) for edge in idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

class Edge(Expression):
    owner: Type
    name: Optional[str]
    returns: Type
    parameters: list[Type]
    bound: Optional[Expression]
    values: list[Optional[Edge]]
    nullable: bool
    multiple: bool

    def __init__(self,
                 owner: Type,
                 name: Optional[str],
                 returns: Type,
                 parameters: list[Type] = [],
                 values: list[Optional[Edge]] = [],
                 bound: Optional[Expression] = None,
                 nullable: bool = False,
                 multiple: bool = False,
                 ):
        self.owner = owner
        self.name = name
        self.returns = returns
        self.parameters = parameters
        assert bound is None or bound.extends(self.owner)
        self.bound = bound
        self.values = self._normalize_values(values)
        self.nullable = nullable
        self.multiple = multiple
    
    def _copy(self, **kwargs):
        return Edge(**{**self.__dict__, **kwargs})

    def _normalize_values(self, values: list[Edge]):
        assert len(values) <= len(self.parameters)
        for i, val in enumerate(values):
            assert val is None or val.extends(self.parameters[i])
        # fill the undefined values with null
        values = values + [None] * (len(self.parameters) - len(values))
        return values

    def bind(self, exp: Optional[Expression]) -> Edge:
        return self._copy(bound=exp)
    
    def apply(self, values: list[Optional[Edge]]):
        return self._copy(values=values)
    
    def extends(self, other: Expression) -> bool:
        if not self.returns.extends(other):
            return False
        if isinstance(other, Edge):
            if not self.nullable and other.nullable:
                return False
            if not self.multiple and other.multiple:
                return False
            # TODO: Might also want to check parameters and values?
        return True
    
    def __getitem__(self, key: str) -> Edge:
        return self.returns[key].bind(self)
    
    def __contains__(self, key: str) -> bool:
        return key in self.returns

    def __repr__(self):
        return "{}{}".format(
            self.name,
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)]
        )

if __name__ == '__main__':
    boolean = Type('Boolean')
    number = Type('Number')
    number.edges['__gt__'] = Edge(owner=number, name='__gt__', parameters=[number], returns=boolean)
    number.edges['__lt__'] = Edge(owner=number, name='__lt__', parameters=[number], returns=boolean)
    string = Type('String')
    string.edges['length'] = Edge(owner=string, name='length', returns=number)
    big_string = string.extend(name='BigString')
    big_string.filter = big_string['length']['__gt__'].apply([number.select(5)])
    print('hi')