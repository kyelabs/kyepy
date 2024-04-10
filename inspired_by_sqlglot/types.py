from __future__ import annotations
import typing as t
import re
import enum
from collections import OrderedDict

TYPE_REF = t.Union[int, str]
EDGE = str

class Operator(enum.Enum):
    GT = '>'
    GE = '>='
    LT = '<'
    LE = '<='
    EQ = '=='
    NE = '!='
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = '%'

class Assertion:
    def __init__(self, op: Operator, *args: t.Any):
        self.op = op
        self.args = args

class Type:
    name: t.Optional[str]
    extends: t.Optional[Type]
    assertions: list[Assertion]
    format: t.Optional[str]
    constant: t.Optional[t.Any]
    _indexes: tuple[tuple[EDGE]]
    _edges: OrderedDict[EDGE, Edge]
    _operations: dict[str, list[Type]]

    def __init__(self, name: str = None):
        self.name = name
        self.assertions = []
        self.extends = None
        self.format = None
        self._indexes = tuple()
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
    
    def define_parent(self, parent: Type):
        assert isinstance(parent, Type)
        if self.extends is not None:
            assert self.extends == parent, 'Already assigned a parent'
            return
        self.extends = parent
        return self
    
    def define_const_val(self, value: t.Any):
        assert self.constant is None, 'constant already set'
        self.constant = value
        return self

    def define_format(self, format: str):
        assert self.format is None, 'format already set'
        self.format = format
        return self

    def define_assertion(self, op: str, arg: t.Any):
        return self

    def define_operations(self, ops: list[str], types: list[Type] = []):
        if len(types) == 0:
            types = [self]
        for op in ops:
            for typ in types:
                self._operations.setdefault(op, []).append(typ)
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

    @property
    def is_constant(self) -> bool:
        return self.constant is not None
    
    @property
    def can_compute(self) -> bool:
        # TODO: check if 
    
    def can_compare(self, other: Type) -> bool:
        return True

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
            self.name or '',
            '<' + self.format + '>' if self.format is not None else '',
        )

    def __repr__(self):
        non_index_edges = [
            str(edge)            
            for edge in self._edges
            if edge not in self.index
        ]

        return "{}{}{}{}".format(
            self.name or '',
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
        return f'{self.origin.name}.{self.name}'
    
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
        .define_operations(['>','+','-','*','/','%'])
)
String = (
    Type('String')
        .define_edge('length', Number)
        .define_operations(['>','+'])
)
Boolean = (
    Type('Boolean')
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
    
    def define(self, name: str = None):
        if name is not None:
            assert name not in self._models
        ref = name or len(self._models)
        self._models[ref] = Type(ref, name)
        return ref

    def __contains__(self, ref: TYPE_REF) -> bool:
        return ref in self._models
    
    def __getitem__(self, ref: TYPE_REF) -> Type:
        assert ref in self._models, f'Undefined type: "{ref}"'
        return self._models[ref]
    
    def __iter__(self) -> t.Iterator[Type]:
        return iter(
            model for model in self._models.values()
            if model.name not in GLOBALS
        )
    
    def compute_maybe_type(self, obj: t.Any) -> Type:
        if type(obj) is dict:
            return self.compute_type(obj)
        return obj

    def compute_types(self, objs: list[t.Any]) -> list[Type]:
        return [self.compute_type(obj) for obj in objs]

    def compute_maybe_types(self, objs: list[t.Any]) -> list[Type]:
        return [self.compute_maybe_type(obj) for obj in objs]

    def compute_type(self, obj) -> Type:
        if type(obj) is str:
            return Type().define_parent(self['String']).define_const_val(obj)
        if isinstance(obj, (int, float)):
            return Type().define_parent(self['Number']).define_const_val(obj)
        if type(obj) is bool:
            return Type().define_parent(self['Boolean']).define_const_val(obj)
        if type(obj) is dict:
            assert len(obj) == 1
            op, args = next(iter(obj.items()))
            if type(args) is not list:
                args = [args]
            if op == 'select':
                assert len(args) == 1
                assert type(args[0]) is str
                assert args[0] in self
                return self[args[0]]
            if op == 'eq':
                assert len(args) == 2
                arg1, arg2 = self.compute_types(args)
                assert arg1.can_compare(arg2)
                if arg1.is_constant and arg2.is_constant:
                    return self.compute_type(arg1.constant == arg2.constant)
                elif arg1.is_constant:
                    return arg2.define_assertion(Operator.EQ, arg1.constant)
                elif arg2.is_constant:
                    return arg1.define_assertion(Operator.EQ, arg2.constant)