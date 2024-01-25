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
    indexes: tuple[tuple[EDGE]]
    assertions: list[Assertion]
    _edges: OrderedDict[EDGE, Type]
    _multiple: dict[EDGE, bool]
    _nullable: dict[EDGE, bool]

    def __init__(self, name: TYPE_REF):
        assert re.match(r'\b[A-Z]+[a-z]\w+\b', name)
        self.ref = name
        self.indexes = tuple()
        self.assertions = []
        self.extends = None
        self._edges = OrderedDict()
        self._multiple = {}
        self._nullable = {}

    def define_edge(self,
                    name: EDGE,
                    type: Type,
                    nullable=False,
                    multiple=False
                    ):
        assert re.fullmatch(r'[a-z_][a-z0-9_]+', name)
        assert isinstance(type, Type)
        self._edges[name] = type
        self._nullable[name] = nullable
        self._multiple[name] = multiple
    
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
            assert self.has_edge(edge), f'Cannot use undefined edge in index: "{edge}"'
            assert not self.allows_null(edge), f'Cannot use a nullable edge in index: "{edge}"'

        # Remove any existing indexes that are a superset of the new index
        self.indexes = tuple(
            existing_idx for existing_idx in self.indexes
            if not set(index).issubset(set(existing_idx))
        ) + (index,)
    
    def define_parent(self, parent: Type):
        assert isinstance(parent, Type)
        if self.extends is not None:
            assert self.extends == parent, 'Already assigned a parent'
            return
        self.extends = parent
        for edge in parent._edges:
            if not self.has_edge(edge):
                self.define_edge(
                    name=edge,
                    type=parent._edges[edge],
                    multiple=parent.allows_multiple(edge),
                    nullable=parent.allows_null(edge),
                )
        self.assertions = parent.assertions + self.assertions
    
    def define_assertion(self, op: str, arg):
        assertion = assertion_factory(op, arg)
        self.assertions.append(assertion)

    @property
    def index(self) -> set[EDGE]:
        """ Flatten the 2d list of indexes """
        return {idx for idxs in self.indexes for idx in idxs}

    @property
    def has_index(self) -> bool:
        return len(self.indexes) > 0

    @property
    def edges(self) -> list[EDGE]:
        return list(self._edges.keys())
    
    def has_edge(self, edge: EDGE) -> bool:
        return edge in self._edges

    def get_edge(self, edge: EDGE) -> Type:
        assert self.has_edge(edge)
        return self._edges[edge]
    
    def edge_origin(self, edge: EDGE) -> Optional[Type]:
        assert self.has_edge(edge)
        if self.extends and self.extends.has_edge(edge):
            return self.extends.edge_origin(edge)
        return self

    def allows_multiple(self, edge: EDGE) -> bool:
        assert self.has_edge(edge)
        return self._multiple[edge]

    def allows_null(self, edge: EDGE) -> bool:
        assert self.has_edge(edge)
        return self._nullable[edge]

    def __repr__(self):
        def get_cardinality_symbol(edge):
            nullable = int(self.allows_null(edge))
            multiple = int(self.allows_multiple(edge))
            return ([['' ,'+'],
                     ['?','*']])[nullable][multiple]

        non_index_edges = [
            edge + get_cardinality_symbol(edge)            
            for edge in self._edges
            if edge not in self.index
        ]

        return "{}{}{}".format(
            self.ref or '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

Number = Type('Number')
String = Type('String')
Boolean = Type('Boolean')
String.define_edge('length', Number)
Number.define_assertion('type', 'number')
String.define_assertion('type','string')
Boolean.define_assertion('type','boolean')

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
    
    def define(self, ref: TYPE_REF):
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