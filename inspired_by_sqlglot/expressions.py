from __future__ import annotations
import typing as t
from typing_extensions import Self
from copy import deepcopy
import regex as re
import enum
from collections import OrderedDict

from iter_utils import list_values, walk_bfs, walk_dfs

TYPE_NAME_REGEX = re.compile(r'[A-Z][a-z][a-zA-Z]*')
EDGE_NAME_REGEX = re.compile(r'[a-z][a-z_]*')

@enum.unique
class Operator(enum.Enum):
    #        symbol, precedence
    DOT    = '.',    0
    FILTER = '[]',   0
    INVERT = '~',    1
    MUL    = '*',    2
    DIV    = '/',    2
    MOD    = '%',    2
    ADD    = '+',    3
    SUB    = '-',    3
    INTER  = '&',    4
    UNION  = '|',    4
    NOT    = '!',    5
    AND    = 'and',  6
    OR     = 'or',   6
    NE     = '!=',   6
    EQ     = '==',   6
    LT     = '<',    6
    GT     = '>',    6
    LE     = '<=',   6
    GE     = '>=',   6

    @property
    def symbol(self):
        return self.value[0]
    
    @property
    def precedence(self):
        return self.value[1]
    
    @property
    def python_name(self):
        return '__' + self.name.lower() + '__'
    
    def __repr__(self):
        return self.symbol

@enum.unique
class Cardinality(enum.Enum):
    ONE = '!'
    MAYBE = '?'
    MANY = '*'
    MORE = '+'

    def nullable(self) -> bool:
        return self in (self.MAYBE, self.MANY)

    def multiple(self) -> bool:
        return self in (self.MANY, self.MORE)
    
    def __repr__(self):
        return self.value


T = t.TypeVar('T')
E = t.TypeVar('E')

def abstract(abstract_cls):
    def __new__(cls, *args, **kwargs):
        if cls is abstract_cls:
            raise TypeError(f"Cannot instantiate abstract class '{cls.__name__}'")
        return super(abstract_cls, cls).__new__(cls)
    abstract_cls.__new__ = __new__
    return abstract_cls

@abstract
class Expression:
    _arg_types: OrderedDict[str, Arg] = {}
    _type: Type

    def __init__(self, *args, **kwargs):
        self.parent: t.Optional[Expression] = None
        self._args = {}
        self._arg_key: t.Optional[str] = None
        self._type = None
        self._meta: t.Optional[t.Dict[str, t.Any]] = None

        for k in self._arg_types.keys():
            if not self._arg_types[k].optional and k not in kwargs:
                raise Exception(f'Missing required property "{k}"')
            setattr(self, k, kwargs.get(k))
        self.validate()
    
    def __init_subclass__(cls, **kwargs):
        cls._arg_types = OrderedDict()
        mro = list(cls.mro())
        # Get attributes that are instances of Arg
        args = [
            getattr(cls, attr)
            for attr in dir(cls)
            if isinstance(getattr(cls, attr), Arg)
        ]
        # Key the args by their order
        args = {
            (mro.index(arg.owner), arg.order): arg
            for arg in args
        }
        # Set the args to the _arg_types attribute
        # in the correct order
        for order in sorted(args.keys()):
            cls._arg_types[args[order].name] = args[order]

    def __deepcopy__(self, memo):
        copy = self.__class__(**deepcopy(self._args))
        if self._type is not None:
            copy._type = self._type.copy()
        if self._meta is not None:
            copy._meta = deepcopy(self._meta)
        return copy

    @property
    def hashable_args(self) -> frozenset[tuple]:
        args = []
        for arg, values in self._args.items():
            values = list_values(values)
            if len(values) == 0:
                continue
            # I'm assuming that the order of the values doesn't matter
            # and that the values are hashable
            args.append((arg, frozenset(values)))
        return frozenset(args)

    def __eq__(self, other) -> bool:
        return type(self) is type(other) and hash(self) == hash(other)

    def __hash__(self) -> int:
        return hash((self.__class__, self.hashable_args))
    
    def validate(self, recurse=False) -> None:
        if self.parent:
            assert self._arg_key is not None
            assert self._arg_key in self.parent._args
            assert self in list_values(self.parent._args[self._arg_key])
        else:
            assert self._arg_key is None
        for arg, values in self._args.items():
            for val in list_values(values):
                if self._arg_types[arg].type is not None and not isinstance(val, self._arg_types[arg].type):
                    raise TypeError(f'Expected {arg} to be of type {self._arg_types[arg].type}, got {val}')
                if isinstance(val, Expression):
                    assert val.parent is self
                    assert val._arg_key == arg
                    if recurse:
                        val.validate(recurse=recurse)
    
    def copy(self, **kwargs) -> Self:
        """
        Returns a deep copy of the expression
        """
        new = deepcopy(self)
        new.parent = self.parent
        for k in self._arg_types.keys():
            if k in kwargs:
                setattr(new, k, kwargs[k])
        return new

    def depth(self) -> int:
        """ Returns the depth of this tree """
        if self.parent:
            return self.parent.depth + 1
        return 0
    
    def find_ancestor(self, *types: t.Type[E]) -> t.Optional[E]:
        ancestor = self.parent
        while ancestor and not isinstance(ancestor, types):
            ancestor = ancestor.parent
        return ancestor # type: ignore
    
    @property
    def root(self) -> Expression:
        """ Returns the root expression of this tree """
        expression = self
        while expression.parent:
            expression = expression.parent
        return expression

    @property
    def path(self) -> list[str]:
        if isinstance(self, Module):
            return []
        parent_path = self.parent.path if self.parent else []
        if isinstance(self, Definition):
            return [*parent_path, self.name]
        return parent_path
    
    def iter_expressions(self) -> t.Iterator[Expression]:
        """ Yields the key and expression for all arguments, exploding list args. """
        for values in self._args.values():
            for val in list_values(values):
                if isinstance(val, Expression):
                    yield val
    
    def walk(self, bfs: bool=True, within_scope: bool=False) -> t.Iterator[Expression]:
        """
        Returns a generator object which visits all nodes in this tree.

        Args:
            bfs (bool): if set to True the BFS traversal order will be applied,
                otherwise the DFS traversal will be used instead.
            within_scope (bool): if set to True, the walk will stop at scope boundaries
        """
        def iterator(node: Expression) -> t.Iterator[Expression]:
            # if within_scope is set and this node is a scope boundary,
            # only walk the root arg of the scope boundary
            if within_scope and isinstance(node, ScopeBoundary):
                if node._root_arg:
                    return list_values(getattr(node, node._root_arg))
                else:
                    return []
            return node.iter_expressions()
        return walk_bfs(self, iterator=iterator) if bfs else walk_dfs(self, iterator=iterator)

    def findall(self, *types: t.Type[E], bfs: bool = True, within_scope: bool=False) -> t.Iterator[E]:
        """
        Returns a generator object which visits all nodes in this tree and only
        yields those that match at least one of the specified expression types.
        """
        for expression in self.walk(bfs=bfs, within_scope=within_scope):
            if isinstance(expression, types):
                yield expression
    
    def find(self, *types: t.Type[E], bfs: bool = True, within_scope: bool=False) -> t.Optional[E]:
        """
        Returns the first node in this tree which matches at least one of
        the specified types.
        """
        return next(self.findall(*types, bfs=bfs, within_scope=within_scope), None)
    
    def scope(self) -> t.Optional[ScopeBoundary]:
        """ Returns the nearest scope boundary """
        return self.find_ancestor(ScopeBoundary)

    def replace_children(self, fun: t.Callable[[Expression], t.Any], *args, **kwargs) -> Self:
        """
        Replace children of an expression with the result of a lambda fun(child) -> exp.
        """
        for k, values in self._args.items():
            new_args = []
            for val in list_values(values):
                if isinstance(val, Expression):
                    new_args += list_values(fun(val, *args, **kwargs))
                else:
                    new_args.append(val)
            setattr(self, k, new_args)
        return self

    def transform(self, fun: t.Callable[[Expression], T], *args, inplace=True, **kwargs) -> T:
        """
        Recursively visit all tree nodes and apply the given transformation function to each node.
        """
        node = self if inplace else self.copy()
        node.replace_children(lambda child: child.transform(fun, *args, **kwargs))
        new_node = fun(self, *args, **kwargs)
        if inplace:
            return self.replace(new_node)
        return new_node

    def replace(self, expression: T) -> T:
        if not self.parent:
            return expression

        self.parent.replace_children(lambda child: expression if child is self else child)
        self.parent = None
        self._arg_key = None
        return expression

    def pop(self) -> Self:
        self.replace(None)
        return self
    
    def assert_is(self, *types: t.Type[E]) -> E:
        if not isinstance(self, types):
            raise AssertionError(f'{self} is not {types}')
        return self
    
    def to_xml(self, depth=0):
        indent = '  '*depth
        tag_name = self.__class__.__name__
        props = []
        for key, values in self._args.items():
            values = [
                val for val in list_values(values)
                if not isinstance(val, Expression)
            ]
            if len(values):
                if len(values) == 1 and not self._arg_types[key].many:
                    values = values[0]
                props.append(f'{key}={repr(values)}')
        props = ' ' + ' '.join(props) if len(props) else ''
        children = [
            expr.to_xml(depth=depth+1)
            for expr in self.iter_expressions()
        ]
        children = '\n' + '\n'.join(children) if len(children) else ''

        if len(children) == 0:
            return f'{indent}<{tag_name}{props}/>'
        else:
            return f'{indent}<{tag_name}{props}>{children}\n{indent}<{tag_name}/>'
    
    def compile(self):
        if isinstance(self, Module):
            return {
                'models': {
                    exp.ref: exp.compile()
                    for exp in self.models
                }
            }
        if isinstance(self, Model):
            compiled = {
                'indexes': [
                    idx.names if len(idx.names) > 1 else idx.names[0]
                    for idx in self.indexes
                ],
                'edges': {
                    edge.name + (edge.cardinality.value if edge.cardinality else ''): edge.compile()
                    for edge in self.edges
                },
                'assert': [
                    assertion.compile()
                    for assertion in self.assertions
                ]
            }
            if len(compiled['indexes']) == 1:
                compiled['index'] = compiled['indexes'][0]
                del compiled['indexes']
            if len(compiled['assert']) == 0:
                del compiled['assert']
            if len(compiled['edges']) == 0:
                del compiled['edges']
            return compiled
        if isinstance(self, Edge):
            compiled = {
                'query': self.value.compile(),
            }
            return compiled
        if isinstance(self, Literal):
            return self.value
        if isinstance(self, TypeIdentifier):
            return { 'select': self.name }
        if isinstance(self, EdgeIdentifier):
            return { 'get', self.name }
        if isinstance(self, Self):
            return { 'self': None }
        if isinstance(self, UnaryOp):
            return { self.op.name.lower(): self.value.compile() }
        if isinstance(self, Filter):
            node = self.value.compile()
            for cond in self.conditions:
                node = { 'filter': [node, cond.compile()] }
            return node
        if isinstance(self, Dot):
            return { 'with': [self.lhs.compile(), self.rhs.compile()] }
        if isinstance(self, BinaryOp):
            return { self.op.name.lower(): [self.lhs.compile(), self.rhs.compile()] }
        raise NotImplementedError(f'Unknown type {self}')
    
    def __repr__(self):
        return self.to_xml()
    
class Arg:
    def __init__(self, type=None, optional=False, many=False):
        self.name = None
        self.type = type
        self.optional = optional
        self.many = many
        self.order = None
        self.owner = None
    
    def __set_name__(self, owner: t.Type[Expression], name):
        assert issubclass(owner, Expression)
        self.name = name
        # The _arg_types property will be overwritten by the __init_subclass__ method
        # we are just using it temporarily to calculate the order of the args
        owner._arg_types = {**owner._arg_types, name: self}
        self.order = len(owner._arg_types)
        self.owner = owner
        
   
    def __set__(self, instance: Expression, value):
        # remove parent of old args
        for old_value in list_values(instance._args.get(self.name)):
            if isinstance(old_value, Expression):
                old_value.parent = None
                old_value._arg_key = None

        # set parent of new args
        for new_value in list_values(value):
            if isinstance(new_value, Expression):
                new_value.parent = instance
                new_value._arg_key = self.name
            
        instance._args[self.name] = self.coerce_cardinality(value)
    
    def __get__(self, instance: t.Optional[Expression], owner=None):
        if instance is None:
            return self
        return self.coerce_cardinality(instance._args.get(self.name))

    def coerce_cardinality(self, value):
        values = list_values(value)

        if not self.optional and len(values) == 0:
            raise TypeError(f'Expected {self.name} to not be null: {value}')

        if not self.many:
            if len(values) > 1:
                raise TypeError(f'Expected {self.name} to only have one value: {value}')
            values = None if len(values) == 0 else values[0]
        
        return values

@abstract
class ScopeBoundary(Expression):
    """ Tells walk function to stop at this node when set to only walk within scope """
    _root_arg = None

    def resolve_type(self, name: str) -> t.Optional[TypeDefinition]:
        if isinstance(self, TypesContainer):
            for model in self.models:
                if model.name == name:
                    return model
        parent_container = self.find_ancestor(ScopeBoundary)
        if parent_container:
            return parent_container.resolve_type(name)
        return None

    def resolve_edge(self, name: str) -> t.Optional[Edge]:
        if isinstance(self, Filter):
            if name == 'this':
                return self.scope()
            return self.type.resolve().resolve_edge(name)
        if isinstance(self, EdgesContainer):
            for edge in self.edges:
                if edge.name == name:
                    return edge
        parent_container = self.find_ancestor(ScopeBoundary)
        if parent_container:
            return parent_container.resolve_edge(name)
        return None

class QueryType(enum.Enum):
    CONSTANT = 'constant'
    RELATIVE = 'relative'
    ABSOLUTE = 'absolute'
    DYNAMIC = 'dynamic'

@abstract
class Query(Expression):
    """ Abstract class for all AST nodes who wrap an expression  """
    value: Expression = Arg(type=Expression)

    def query_type(self) -> QueryType:
        contains_type_ref = self.value.find(TypeIdentifier, within_scope=True) is not None
        contains_edge_ref = self.value.find(EdgeIdentifier, within_scope=True) is not None or self.value.find(Self) is not None
        if contains_type_ref and contains_edge_ref:
            return QueryType.DYNAMIC
        if contains_type_ref and not contains_edge_ref:
            return QueryType.ABSOLUTE
        if not contains_type_ref and contains_edge_ref:
            return QueryType.RELATIVE
        return QueryType.CONSTANT

@abstract
class Definition(Expression):
    """ Abstract class for all AST nodes that define a name """
    name: str = Arg(type=str)

    @property
    def ref(self):
        return '.'.join(self.path)

class Assert(Expression):
    condition: Expression = Arg(type=Expression)

@abstract
class TypeDefinition(Definition):
    """ Abstract class for all AST nodes that define a type """
    assertions: list[Assert] = Arg(type=Assert, many=True, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not TYPE_NAME_REGEX.match(self.name):
            raise ValueError(f'Invalid type name {self.name}')

class Edge(Definition, Query):
    cardinality: Cardinality = Arg(type=Cardinality, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not EDGE_NAME_REGEX.match(self.name):
            raise ValueError(f'Invalid edge name {self.name}')

@abstract
class TypesContainer(Expression):
    """ Abstract class for all AST nodes that have child type definitions """
    models: list[TypeDefinition] = Arg(type=TypeDefinition, many=True, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        type_names = set()
        for child in self.models:
            if child.name in type_names:
                raise ValueError(f'multiple definitions with same name: {child.name}')
            type_names.add(child.name)

@abstract
class EdgesContainer(Expression):
    """ Abstract class for all AST nodes that have child edge definitions """
    edges: list[Edge] = Arg(type=Edge, many=True, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        type_names = set()
        for child in self.edges:
            if child.name in type_names:
                raise ValueError(f'multiple definitions with same name: {child.name}')
            type_names.add(child.name)


class Module(TypesContainer, ScopeBoundary):
    pass

class TypeAlias(TypeDefinition, Query):
    pass

class Index(Expression):
    names: list[str] = Arg(type=str, many=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        names_set = set()
        for name in self.names:
            if not EDGE_NAME_REGEX.match(name):
                raise ValueError(f'Invalid edge name {name}')
            if name in names_set:
                raise ValueError(f'edge referenced multiple times in same index: {name}')
            names_set.add(name)

class Model(TypeDefinition, EdgesContainer, ScopeBoundary):
    indexes: list[Index] = Arg(type=Index, many=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        edge_names = {edge.name for edge in self.edges}
        for idx in self.indexes:
            for name in idx.names:
                if name not in edge_names:
                    raise ValueError(f'edge referenced in index not defined in model: {name}')

@abstract
class Literal(Expression):
    """ Abstract class for all AST nodes that represent a literal value """
    value = Arg(type=(int, float, str, bool))

class String(Literal):
    value: str = Arg(type=str)
    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not isinstance(self.value, str):
            raise ValueError(f'Expected string, got {self.value}')

class Number(Literal):
    value: t.Union[int, float] = Arg(type=(int, float))
    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not isinstance(self.value, (int, float)):
            raise ValueError(f'Expected number, got {self.value}')

class Boolean(Literal):
    value: bool = Arg(type=bool)
    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not isinstance(self.value, bool):
            raise ValueError(f'Expected boolean, got {self.value}')

@abstract
class Identifier(Expression):
    name: str = Arg(type=str)

class EdgeIdentifier(Identifier):
    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not EDGE_NAME_REGEX.match(self.name):
            raise ValueError(f'Invalid edge name {self.name}')

class TypeIdentifier(Identifier):
    def validate(self, **kwargs):
        super().validate(**kwargs)
        if not TYPE_NAME_REGEX.match(self.name):
            raise ValueError(f'Invalid type name {self.name}')

class Self(Identifier):
    name = 'self'

@abstract
class Operation(Expression):
    """ Abstract class for all AST nodes that represent an operation"""
    op: Operator

@abstract
class UnaryOp(Operation):
    """ Abstract class for all AST nodes that represent a unary operation"""
    value: Expression = Arg(type=Expression)

@abstract
class BinaryOp(Operation):
    """ Abstract class for all AST nodes that represent a binary operation"""
    lhs: Expression = Arg(type=Expression)
    rhs: Expression = Arg(type=Expression)

class Dot(BinaryOp, ScopeBoundary):
    op = Operator.DOT
    _root_arg = 'lhs'

class Invert(UnaryOp):
    op = Operator.INVERT

class Mul(BinaryOp):
    op = Operator.MUL

class Div(BinaryOp):
    op = Operator.DIV

class Mod(BinaryOp):
    op = Operator.MOD

class Add(BinaryOp):
    op = Operator.ADD

class Sub(BinaryOp):
    op = Operator.SUB

class And(BinaryOp):
    op = Operator.AND

class Or(BinaryOp):
    op = Operator.OR

class Not(UnaryOp):
    op = Operator.NOT

@abstract
class Composite(BinaryOp):
    pass

class Intersection(Composite):
    op = Operator.INTER

class Union(Composite):
    op = Operator.UNION

@abstract
class Comparison(BinaryOp):
    pass

class Equals(Comparison):
    op = Operator.EQ

class NotEquals(Comparison):
    op = Operator.NE

class LessThan(Comparison):
    op = Operator.LT

class GreaterThan(Comparison):
    op = Operator.GT

class LessThanOrEquals(Comparison):
    op = Operator.LE

class GreaterThanOrEquals(Comparison):
    op = Operator.GE

class Filter(ScopeBoundary):
    value: Expression = Arg(type=Expression)
    conditions: list[Expression] = Arg(type=Expression, many=True, optional=True)
    _root_arg = 'value'

def convert() -> Expression:
    """ Convert python value to Expression """
    pass

def evaluate(exp: Expression) -> t.Any:
    if isinstance(exp, Literal):
        return exp.value
    if isinstance(exp, BinaryOp):
        return getattr(exp.lhs, exp.op.python_name)(exp.rhs)

def test_query_type():
    assert Edge(
        name='count',
        value=GreaterThanOrEquals(
            lhs=TypeIdentifier(name='Number'),
            rhs=Number(value=1)
        ),
    ).query_type() == QueryType.ABSOLUTE
    assert Edge(
        name='name',
        value=Filter(
            value=TypeIdentifier(name='String'),
            conditions=[
                GreaterThan(lhs=EdgeIdentifier(name='length'), rhs=Number(value=0)),
            ]
        )
    ).query_type() == QueryType.ABSOLUTE
    assert Edge(
        name='posts',
        value=Filter(
            value=TypeIdentifier(name='Posts'),
            conditions=[
                Equals(lhs=EdgeIdentifier(name='id'), rhs=Self()),
            ]
        )
    ).query_type() == QueryType.DYNAMIC
    assert Edge(
        name='full_name',
        value=Add(
            lhs=String(value='Mr. '),
            rhs=EdgeIdentifier(name='name')
        )
    ).query_type() == QueryType.RELATIVE
    assert Edge(
        name='two_plus_four',
        value=Add(
            lhs=Number(value=2),
            rhs=Number(value=4)
        )
    ).query_type() == QueryType.CONSTANT

class Type:
    def __init__(self,
                 name: str,
                 extends: Type = None,
                 dynamic: bool = False,
                 foreign: bool = False,
                 range: bool = False):
        assert name is not None
        self.name = name
        self.extends = extends
        self.dynamic = dynamic
        self.foreign = foreign
        self.range = range
    
    @property
    def root(self) -> Type:
        return self.extends.root if self.extends else self
    
    def hierarchy(self) -> list[Type]:
        if self.extends:
            return [self] + self.extends.hierarchy()
        return [self]
    
    def copy(self,**kwargs) -> Type:
        return Type(
            name=self.name,
            extends=kwargs.get('extends', self.extends),
            dynamic=kwargs.get('dynamic', self.dynamic),
            foreign=kwargs.get('foreign', self.foreign),
            range=kwargs.get('range', self.range),
        )
    
    def equals(self, other: Type) -> Type:
        r, c = None, None
        if self.range and not other.range:
            r, c = self, other
        if not self.range and other.range:
            r, c = other, self
        if r and c:
            if self.name != other.name:
                raise ValueError("Cannot compare two different types")
            return Type(
                name=r.name,
                dynamic=r.dynamic or c.dynamic,
                foreign=r.foreign or c.foreign,
                range=False)
        return self.compare(other)

    def compare(self, other: Type) -> Type:
        if self.range and other.range:
            raise ValueError("Cannot compare two range types")
        if not self.range and not other.range:
            return Type('Boolean',
                        dynamic=self.dynamic or other.dynamic,
                        foreign=self.foreign or other.foreign,
                        range=False)
        if self.name != other.name:
            raise ValueError("Cannot compare two different types")
        return Type(
            name=self.name,
            dynamic=self.dynamic or other.dynamic,
            foreign=self.foreign or other.foreign,
            range=True)

from contextlib import contextmanager
class EnvDefinitionStatus(enum.Enum):
    INITIALIZED = 1
    PENDING = 2
    COMPLETE = 3

class EnvDefinition:
    ast: t.Optional[Definition]
    status: EnvDefinitionStatus
    _type: t.Optional[Type]

    def __init__(self, ast: t.Optional[Definition], status: EnvDefinitionStatus, type: t.Optional[Type] = None):
        self.ast = ast
        self.status = status
        self._type = type
    
    @staticmethod
    def from_ast(ast: Definition) -> EnvDefinition:
        return EnvDefinition(ast=ast, status=EnvDefinitionStatus.INITIALIZED)
    
    @staticmethod
    def from_native(type: Type) -> EnvDefinition:
        return EnvDefinition(ast=None, status=EnvDefinitionStatus.COMPLETE, type=type)
    
    @property
    def type(self) -> t.Optional[Type]:
        return self._type or self.ast._type

    @property
    def is_native(self) -> bool:
        return self._type is not None
    
    def __enter__(self) -> Definition:
        """
        Using the 'status' property makes sure that there are no circular references
        (i.e. trying to use a reference during its own compilation)
        """
        assert self.status == EnvDefinitionStatus.INITIALIZED
        assert self.ast is not None
        assert self.ast._type is None
        self.status = EnvDefinitionStatus.PENDING
        return self.ast

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is not None:
            assert self.ast._type is not None
            self.status = EnvDefinitionStatus.COMPLETE

class Env:
    _types: t.Dict[str, EnvDefinition]

    def __init__(self):
        self._types = {
            'String': EnvDefinition.from_native(Type('String', range=True)),
            'Number': EnvDefinition.from_native(Type('Number', range=True)),
            'Boolean': EnvDefinition.from_native(Type('Boolean', range=True)),
        }
    
    def read_ast(self, ast: Expression):
        for child in ast.findall(Definition):
            self._types[child.ref] = EnvDefinition.from_ast(child)
        return self
    
    def _get_def(self, ref: str):
        if ref not in self._types:
            raise KeyError(f'Unknown symbol `{ref}`')
        return self._types[ref]
    
    def compile_ref(self, ref: str) -> Type:
        typ_def = self._get_def(ref)
        
        # Check if already compiled
        if typ_def.type is None:

            # Checkout the definition, locking it out from recursion
            with typ_def as ast:
                if isinstance(ast, Model):
                    ast._type = Type(
                        name=ast.ref,
                    )
                elif isinstance(ast, TypeAlias):
                    ast._type = Type(
                        name=ast.ref,
                        extends=self.compile_ast(ast.value),
                    )
                elif isinstance(ast, Edge):
                    if isinstance(ast.value, TypeIdentifier):
                        ast._type = self.compile_ast(ast.value)
                    else:
                        model_type = self.compile_ref(ast.find_ancestor(TypeDefinition).ref)
                        ast._type = Type(
                            name=ast.ref,
                            extends=self.compile_ast(
                                ast.value,
                                model=model_type,
                                this=model_type,
                            ),
                        )
                else:
                    raise NotImplementedError(f'Unknown type {ast}')

        return typ_def.type
    
    def compile_ast(self, ast: Expression, model: Type = None, this: Type = None) -> Type:
        if isinstance(ast, String):
            return Type('String')
        if isinstance(ast, Number):
            return Type('Number')
        if isinstance(ast, Boolean):
            return Type('Boolean')
        if isinstance(ast, TypeIdentifier):
            return self.compile_ref(ast.name).copy(dynamic=False, foreign=True, range=True)
        if isinstance(ast, EdgeIdentifier):
            return self.compile_ref(this.name + '.' + ast.name).copy(
                foreign=False,
                dynamic=True,
                range=False
            )
        if isinstance(ast, Self):
            return model.copy(foreign=False, dynamic=True, range=False)
        if isinstance(ast, UnaryOp):
            return self.compile_ast(ast.value, model=model, this=this)
        if isinstance(ast, BinaryOp):
            lhs = self.compile_ast(ast.lhs, model=model, this=this)
            rhs = self.compile_ast(ast.rhs, model=model, this=this)
            return lhs.equals(rhs)
        if isinstance(ast, Filter):
            root = self.compile_ast(ast.root, model=model, this=this)
            foreign = root.foreign
            dynamic = root.dynamic
            for cond in ast.conditions:
                cond_type = self.compile_ast(cond, model=model, this=root)
                foreign |= cond_type.foreign
                dynamic |= cond_type.dynamic
            return root.copy(foreign=foreign, dynamic=dynamic)
        if isinstance(ast, Dot):
            root = self.compile_ast(ast.rhs, model=model, this=this)
            return self.compile_ast(
                ast.lhs,
                model=model,
                this=root
            ).copy(foreign=root.foreign, dynamic=root.dynamic)
        raise NotImplementedError(f'Unknown type {ast}')

if __name__ == '__main__':
    a = Module(
        models=[
            Model(
                name='Person',
                indexes=[
                    Index(names=['id']),
                ],
                edges=[
                    Edge(name='id', value=TypeIdentifier(name='Number')),
                    Edge(name='age', value=GreaterThan(lhs=TypeIdentifier(name='Number'), rhs=Number(value=0))),
                ],
            ),
            # Model(
            #     name='Rect',
            #     indexes=[
            #         Index(names=['width','height']),
            #     ],
            #     edges=[
            #         Edge(name='width', value=TypeIdentifier(name='Number')),
            #         Edge(name='height', value=GreaterThan(
            #             lhs=TypeIdentifier(name='Number'),
            #             rhs=EdgeIdentifier(name='width'))
            #         ),
            #     ],
            # ),
            Model(
                name='Square',
                indexes=[
                    Index(names=['width']),
                ],
                edges=[
                    Edge(name='width', value=TypeIdentifier(name='Number')),
                    Edge(name='height', value=EdgeIdentifier(name='width')),
                ],
            )
        ]
    )
    e = Env().read_ast(a)
    # e.compile_ref('Person')


    # for exp in a.models[1].findall(Identifier):
    #     print(exp, exp.scope())
    # flatten_models(a)
    # print(a)
    # edge = Edge(name='posts', value=Filter(
    #     value=TypeIdentifier(name='Post'),
    #     conditions=[
    #         Equals(lhs=EdgeIdentifier(name='author'), rhs=Dot(lhs=Self(), rhs=EdgeIdentifier(name='name'))),
    #         GreaterThan(lhs=EdgeIdentifier(name='age'), rhs=Number(value=0)),
    #     ]
    # ))
    
    # print(externalize_filter_cond(edge.value.conditions[0]))
    # a,b = split_out_external_assertions(edge.value)
    # a = Filter(
    #     value=TypeIdentifier(name='Post'),
    #     conditions=[
    #         Equals(lhs=EdgeIdentifier(name='author'), rhs=Dot(lhs=Self(), rhs=EdgeIdentifier(name='name'))),
    #         GreaterThan(lhs=EdgeIdentifier(name='age'), rhs=Number(value=0)),
    #     ]
    # )
    # import yaml
    # print(yaml.dump(a.compile(), sort_keys=False))
    for ref, typ_def in e._types.items():
        if ref.split('.')[-1].islower():
            typ = e.compile_ref(ref)
            print(ref, ''.join([
                'dynamic ' if typ.dynamic else '',
                'foreign ' if typ.foreign else '',
                '$' if typ_def.is_native else '',
                ' > '.join([p.name for p in typ.hierarchy()]),
                '[]' if typ.range else '',
            ]))
    print('hi')