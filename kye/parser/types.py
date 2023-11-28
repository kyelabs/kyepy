from __future__ import annotations
from typing import Optional, Literal, Union

class Type:
    name: str
    edges: dict[str, Edge]
    filter: Optional[Edge]

    def __init__(self,
                 name: str,
                 edges: Optional[dict[str, Edge]] = None,
                 filter: Optional[Edge] = None
                 ):
        self.name = name
        self.edges = edges or {}
        self.filter = filter
    
    def _extend_filter(self, filter: Optional[Edge]):
        if self.filter:
            filter = self.filter.extend_with(filter)
        return filter

    def _extend_edges(self, edges: dict[str, Edge]):
        edges = {**edges}
        for key, edge in self.edges.items():
            edges[key] = edge.extend_with(edges.get(key))
        return edges
    
    def extend(self,
               name: Optional[str] = None,
               edges: dict[str, Edge] = {},
               filter: Optional[Edge] = None):
        return Type(
            name=name or self.name,
            edges=self._extend_edges(edges),
            filter=self._extend_filter(filter),
        )
    
    def extend_with(self, other: Optional[Type]):
        return self.extend(other.name, other.edges, other.filter)

    def select(self, value: str | float | int | bool):
        return Value(type=self, value=value)
    
    def __getitem__(self, key: str):
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
                 edges: dict[str, Edge],
                 filter: Optional[Edge] = None,
                 ):
        super().__init__(name, edges, filter)
        assert len(indexes) > 0
        self.indexes = indexes
    
    def extend(self,
               name: Optional[str] = None,
               indexes: Optional[list[list[str]]] = None,
               edges: dict[str, Edge] = {},
               filter: Optional[Edge] = None,
               ):
        return Model(
            name=name or self.name,
            indexes=indexes or self.indexes,
            edges=self._extend_edges(edges),
            filter=self._extend_filter(filter),
        )

    def extend_with(self, other: Optional[Model]):
        assert isinstance(other, Model)
        return self.extend(other.name, other.indexes, other.edges, other.filter)

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
            '{' + ','.join(non_index_edges) + '}' if len(self.edges) else '',
        )

class Edge:
    name: Optional[str]
    returns: Type
    parameters: list[tuple[Type, Optional[Edge]]]
    nullable: bool
    multiple: bool

    def __init__(self,
                 name: Optional[str],
                 returns: Type,
                 parameters: list[tuple[Type, Optional[Edge]]] = [],
                 nullable: bool = False,
                 multiple: bool = False,
                 ):
        self.name = name
        self.returns = returns
        self.parameters = parameters
        self.nullable = nullable
        self.multiple = multiple
    
    def extend_with(self, other: Optional[Edge]):
        if other is None:
            return self
        assert isinstance(other, Edge)
        assert self.name == other.name or (self.name or other.name) is None
        return Edge(
            name=self.name or other.name,
            # TODO: Assert that return types are compatible
            returns=self.returns.extend_with(other.returns),
            # TODO: Assert that the other edge's parameters are compatible
            parameters=self.parameters, 
            nullable=self.nullable or other.nullable,
            multiple=self.multiple or other.multiple,
        )
    
    def apply(self, values: list[Optional[Edge]]):
        assert len(self.parameters) == len(values)
        return Edge(
            name=self.name,
            returns=self.returns,
            parameters=[(self.parameters[i][0], val) for i, val in enumerate(values)],
            nullable=self.nullable,
            multiple=self.multiple,
        )

    def __repr__(self):
        return "{}{}".format(
            self.name,
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)]
        )

class Value(Edge):
    def __init__(self, type: Type, value: str | int | float | bool):
        super().__init__(name=None, returns=type, parameters=[(type, value)], nullable=False, multiple=False)


if __name__ == '__main__':
    boolean = Type('Boolean')
    number = Type('Number')
    number.edges['__gt__'] = Edge(name='__gt__', parameters=[(number, None), (number, None)], returns=boolean)
    number.edges['__lt__'] = Edge(name='__lt__', parameters=[(number, None), (number, None)], returns=boolean)
    string = Type('String')
    string.edges['length'] = Edge(name='length', parameters=[(string, None)], returns=number)
    big_string = string.extend(name='BigString')
    big_string.filter = number.edges['__gt__'].apply(values=[big_string['length'], number.select(5)])
    print('hi')