from __future__ import annotations
from typing import Optional
from kye.parser.parser import parse_expression
import kye.parser.kye_ast as AST
import re
from collections import OrderedDict

TYPE_REF = str
EDGE = str

class Type:
    """ Base Class for Types """
    ref: TYPE_REF
    extends: Optional[Type]
    indexes: tuple[tuple[EDGE]]
    assertions: list[AST.Expression]
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
    
    def define_assertion(self, assertion: str):
        assert type(assertion) is str
        ast = parse_expression(assertion)
        self.assertions.append(ast)

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

GLOBALS = {
    'Number': {},
    'String': {'edges':{'length':'Number'}},
    'Boolean': {},
}

def from_compiled(source, types: dict[TYPE_REF, Type]={}):
    source['models'] = {**GLOBALS, **source.get('models',{})}
    # 1. Do first iteration creating a stub type for each name
    for ref in source.get('models',{}):
        types[ref] = Type(ref)
    
    def get_type(type_ref):
        assert type_ref in types, f'Undefined type: "{type_ref}"'
        return types[type_ref]
    
    zipped_source_and_stub: dict[TYPE_REF, tuple[dict, Type]] = {
        ref: (src, types[ref])
        for ref, src in source.get('models',{}).items()
    }

    # 2. During second iteration define the edges, indexes & assertions
    for src, typ in zipped_source_and_stub.values():

        for edge_name, edge_type_ref in src.get('edges', {}).items():
            nullable = edge_name.endswith('?') or edge_name.endswith('*')
            multiple = edge_name.endswith('+') or edge_name.endswith('*')
            edge_name = edge_name.rstrip('?+*')
            typ.define_edge(
                name=edge_name,
                type=get_type(edge_type_ref),
                nullable=nullable,
                multiple=multiple,
            )

        if 'index' in src:
            typ.define_index(src['index'])
        if 'indexes' in src:
            for idx in src['indexes']:
                typ.define_index(idx)

        for assertion in src.get('assertions', []):
            typ.define_assertion(assertion)

    # 3. Wait till the third iteration to define the extends
    # so that parent edges & assertions will be known
    def recursively_define_parent(type_ref):
        src, typ = zipped_source_and_stub[type_ref]
        if 'extends' in src:
            parent = get_type(src['extends'])
            recursively_define_parent(parent.ref)
            typ.define_parent(parent)

    for type_ref in zipped_source_and_stub.keys():
        recursively_define_parent(type_ref)
    

    # # 4. Now that all edges have been defined, parse the expressions
    # for src, typ in zipped_source_and_stub:
    #     for assertion in src.get('assertions', []):
    #         # TODO: parse the assertion and add type information
    #         typ.define_assertion(assertion)

    return types