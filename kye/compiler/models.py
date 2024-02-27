from __future__ import annotations
from typing import Optional, Iterator
from kye.compiler.from_ast import models_from_ast
from kye.compiler.from_compiled import models_from_compiled
from kye.compiler.assertion import Assertion, assertion_factory
import kye.parser.kye_ast as AST
from kye.parser.parser import parse_definitions
import re
from collections import OrderedDict

TYPE_REF = str
EDGE = str

class Type:
    """ Base Class for Types """
    ref: TYPE_REF
    extends: Optional[Type]
    assertions: list[Assertion]
    format: Optional[str]
    _indexes: tuple[tuple[EDGE]]
    _edges: OrderedDict[EDGE, Edge]
    _operations: dict[str, list[Type]]

    def __init__(self, name: TYPE_REF):
        assert re.match(r'\b[A-Z]+[a-z]\w+\b', name)
        self.ref = name
        self._indexes = tuple()
        self.assertions = []
        self.extends = None
        self.format = None
        self._edges = OrderedDict()
        self._operations = {}

    def define_edge(self,
                    name: EDGE,
                    type: Type,
                    nullable=False,
                    multiple=False
                    ):
        edge = Edge(name=name, origin=self, type=type, nullable=nullable, multiple=multiple)
        self._edges[edge.name] = edge
        return self
    
    def define_index(self, index: tuple[EDGE]):
        # Convert to tuple if passed in a single string
        if type(index) is str:
            index = (index,)
        else:
            index = tuple(index)

        # Skip if it is already part of our indexes
        if index in self.indexes:
            return

        # Validate edges within index
        for edge in index:
            assert edge in self, f'Cannot use undefined edge in index: "{edge}"'
            assert not self[edge].nullable, f'Cannot use a nullable edge in index: "{edge}"'
    
        # Remove any existing indexes that are a superset of the new index
        self._indexes = tuple(
            existing_idx for existing_idx in self.indexes
            if not set(index).issubset(set(existing_idx))
        ) + (index,)
        return self

    @property
    def indexes(self) -> tuple[tuple[EDGE]]:
        if self.extends is None:
            return self._indexes

        indexes = self.extends.indexes
        
        for index in self._indexes:
            indexes = tuple(
                existing_idx for existing_idx in indexes
                if not set(index).issubset(set(existing_idx))
            )
    
        return indexes + self._indexes
    
    def define_parent(self, parent: Type):
        assert isinstance(parent, Type)
        if self.extends is not None:
            assert self.extends == parent, 'Already assigned a parent'
            return
        self.extends = parent
        return self
    
    def define_format(self, format: str):
        assert self.format is None, 'format already set'
        self.format = format
        return self
    
    def define_assertion(self, op: str, arg):
        assertion = assertion_factory(op, arg)
        self.assertions.append(assertion)
        return self

    def define_operations(self, operations: list[str], types: list[Type] = []):
        if len(types) == 0:
            types = [self]
        for op in operations:
            for typ in types:
                self._operations.setdefault(op, []).append(typ)
        return self

    @property
    def index(self) -> set[EDGE]:
        """ Flatten the 2d list of indexes """
        return {idx for idxs in self.indexes for idx in idxs}

    @property
    def has_index(self) -> bool:
        return len(self.indexes) > 0

    @property
    def own_edges(self) -> list[Edge]:
        return list(self._edges.values())

    @property
    def edges(self) -> list[Edge]:
        if self.extends is None:
            return self.own_edges
        return self.extends.edges + self.own_edges
    
    def has_operation(self, operation, type):
        if type in self._operations.get(operation, []):
            return True

        if self.extends and self.extends.has_operation(operation, type):
            return True
        return False
    
    def keys(self) -> list[EDGE]:
        return list(self._edges.keys())
    
    def __contains__(self, edge: EDGE) -> bool:
        if self.extends is not None and edge in self.extends:
            return True
        return edge in self._edges

    def __getitem__(self, edge: EDGE) -> Edge:
        assert edge in self
        if edge not in self._edges:
            return self.extends[edge]
        return self._edges[edge]
    
    def __str__(self):
        return "{}{}".format(
            self.ref or '',
            '<' + self.format + '>' if self.format is not None else '',
        )

    def __repr__(self):
        non_index_edges = [
            str(edge)            
            for edge in self._edges
            if edge not in self.index
        ]

        return "{}{}{}{}".format(
            self.ref or '',
            '<' + self.format + '>' if self.format is not None else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

class Edge:
    def __init__(self, name: str, origin: Type, type: Type, nullable=False, multiple=False):
        assert isinstance(name, str)
        assert re.fullmatch(r'[a-z_][a-z0-9_]*', name)
        assert isinstance(origin, Type)
        assert isinstance(type, Type)
        assert isinstance(nullable, bool)
        assert isinstance(multiple, bool)
        self.name = name
        self.origin = origin
        self.type = type
        self.nullable = nullable
        self.multiple = multiple
    
    @property
    def ref(self):
        return f'{self.origin.ref}.{self.name}'
    
    @property
    def cardinality_symbol(self):
        nullable = int(self.nullable)
        multiple = int(self.multiple)
        return ([['' ,'+'],
                 ['?','*']])[nullable][multiple]

    def __str__(self):
        return f'{self.name}{self.cardinality_symbol}'

    def __repr__(self):
        return f'{self.origin}.{self.name}{self.cardinality_symbol}:{self.type}'

Number = (
    Type('Number')
        .define_assertion('type', 'number')
        .define_operations(['>','+','-','*','/','%'])
)
String = (
    Type('String')
        .define_edge('length', Number)
        .define_assertion('type','string')
        .define_operations(['>','+'])
)
Boolean = (
    Type('Boolean')
        .define_assertion('type','boolean')
)

GLOBALS = {
    'Number': Number,
    'String': String,
    'Boolean': Boolean
}

class Models:
    _models: dict[TYPE_REF, Type]

    def __init__(self):
        self._models = {**GLOBALS}
    
    @staticmethod
    def from_script(script: str) -> Models:
        ast = parse_definitions(script)
        return models_from_ast(Models(), ast)
    
    @staticmethod
    def from_ast(ast: AST.ModuleDefinitions) -> Models:
        assert isinstance(ast, AST.ModuleDefinitions)
        return models_from_ast(Models(), ast)
    
    @staticmethod
    def from_compiled(compiled) -> Models:
        return models_from_compiled(Models(), compiled)
    
    def define(self, ref: Optional[TYPE_REF] = None):
        if ref is None:
            ref = f'LambdaType{len(self._models)}'
        assert ref not in self._models
        typ = Type(ref)
        self._models[ref] = typ
        return typ
    
    def __contains__(self, ref: TYPE_REF):
        return ref in self._models
    
    def __getitem__(self, ref: TYPE_REF):
        assert ref in self._models, f'Undefined type: "{ref}"'
        return self._models[ref]
    
    def __iter__(self) -> Iterator[Type]:
        return iter(
            model for model in self._models.values()
            if model.ref not in GLOBALS
        )