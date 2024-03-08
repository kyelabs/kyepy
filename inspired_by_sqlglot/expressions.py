from __future__ import annotations
import typing as t
from typing_extensions import Self
from copy import deepcopy
import regex as re
import enum

from iter_utils import list_values, walk_bfs, walk_dfs

TYPE_NAME_REGEX = re.compile(r'[A-Z][a-z][a-zA-Z]*')
EDGE_NAME_REGEX = re.compile(r'[a-z][a-z_]*')

@enum.unique
class Operator(enum.Enum):
    #      symbol, precedence
    DOT    = '.',  0
    INVERT = '~',  1
    MUL    = '*',  2
    DIV    = '/',  2
    MOD    = '%',  2
    ADD    = '+',  3
    SUB    = '-',  3
    AND    = '&',  4
    OR     = '|',  4
    NOT    = '!',  4
    NE     = '!=', 5
    EQ     = '==', 5
    LT     = '<',  5
    GT     = '>',  5
    LE     = '<=', 5
    GE     = '>=', 5

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
    
    def __repr__(self):
        return self.value

T = t.TypeVar('T')
E = t.TypeVar('E')

class Expression:
    _arg_types: dict[str, Arg] = {}

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
        cls._arg_types = {}
        for attr in dir(cls):
            arg = getattr(cls, attr)
            if isinstance(arg, Arg):
                cls._arg_types[attr] = arg

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
    
    def copy(self) -> Self:
        """
        Returns a deep copy of the expression
        """
        new = deepcopy(self)
        new.parent = self.parent
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
    
    def root(self) -> Expression:
        """ Returns the root expression of this tree """
        expression = self
        while expression.parent:
            expression = expression.parent
        return expression
    
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
            if within_scope and isinstance(node, ScopeBoundary) and not node == self:
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
    
    def scope(self) -> t.Optional[Expression]:
        """ Returns the nearest scope boundary """
        scope = self.find_ancestor(ScopeBoundary).root
        if scope == self:
            return self.parent.scope()
        return scope

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
    
    def __repr__(self):
        return self.to_xml()
    
class Arg:
    def __init__(self, type=None, optional=False, many=False):
        self.name = None
        self.type = type
        self.optional = optional
        self.many = many
    
    def __set_name__(self, owner: t.Type[Expression], name):
        assert hasattr(owner, '_arg_types')
        self.name = name
   
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

class ScopeBoundary(Expression):
    """ Tells walk function to stop at this node when set to only walk within scope """
    _root_arg = None

    @property
    def root(self):
        if self._root_arg is None:
            return self
        return getattr(self, self._root_arg)

class Query(Expression):
    """ Abstract class for all AST nodes who wrap an expression  """
    value: Expression = Arg(type=Expression)

class Definition(Expression):
    """ Abstract class for all AST nodes that define a name """
    name: str = Arg(type=str)

class TypeDefinition(Definition):
    """ Abstract class for all AST nodes that define a type """
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

class Model(TypeDefinition, TypesContainer, EdgesContainer, ScopeBoundary):
    indexes: list[Index] = Arg(type=Index, many=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        edge_names = {edge.name for edge in self.edges}
        for idx in self.indexes:
            for name in idx.names:
                if name not in edge_names:
                    raise ValueError(f'edge referenced in index not defined in model: {name}')

class Literal(Expression):
    value: t.Union[int, float, str] = Arg(type=(int, float, str))

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

class Call(Expression):
    fn: Expression = Arg(type=Expression)
    args: list[Expression] = Arg(type=Expression, many=True, optional=True)

class Operation(Expression):
    """ Abstract class for all AST nodes that represent an operation"""
    op: Operator

class UnaryOp(Operation):
    """ Abstract class for all AST nodes that represent a unary operation"""
    value = Arg(type=Expression)

class BinaryOp(Operation):
    """ Abstract class for all AST nodes that represent a binary operation"""
    lhs = Arg(type=Expression)
    rhs = Arg(type=Expression)

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

class Composite(BinaryOp):
    pass

class Intersection(Composite):
    op = Operator.AND

class Union(Composite):
    op = Operator.OR

class Not(UnaryOp):
    op = Operator.NOT

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
    type: Expression = Arg(type=Expression)
    condition: Expression = Arg(type=Expression, many=True)
    _root_arg = 'type'

def convert() -> Expression:
    """ Convert python value to Expression """
    pass

def evaluate(exp: Expression) -> t.Any:
    if isinstance(exp, Literal):
        return exp.value
    if isinstance(exp, BinaryOp):
        return getattr(exp.lhs, exp.op.python_name)(exp.rhs)

if __name__ == '__main__':
    a = Module(
        models=[
            Model(
                name='Person',
                indexes=[
                    Index(names=['id', 'name']),
                ],
                edges=[
                    Edge(name='id', value=Literal(value=1)),
                    Edge(name='name', value=Literal(value='John')),
                    Edge(name='age', value=Literal(value=30), cardinality=Cardinality.ONE),
                ],
            ),
            Model(
                name='Company',
                indexes=[
                    Index(names=['name']),
                ],
                edges=[
                    Edge(name='name', value=Dot(
                        lhs=Identifier(name='location'),
                        rhs=Identifier(name='name')
                    )),
                    Edge(name='location', value=Literal(value='Cupertino')),
                ]
            ),
        ]
    )
    for exp in a.models[1].findall(Identifier):
        print(exp, exp.scope())
    print('hi')