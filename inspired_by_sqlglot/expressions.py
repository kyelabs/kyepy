from __future__ import annotations
import typing as t
from typing_extensions import Self
from collections.abc import Iterable
from collections import deque
from copy import deepcopy
import regex as re

TYPE_NAME_REGEX = re.compile(r'[A-Z][a-z][a-zA-Z]*')
EDGE_NAME_REGEX = re.compile(r'[a-z][a-z_]*')

from iter_utils import list_values

T = t.TypeVar('T')
E = t.TypeVar('E')

class Expression:
    arg_types: dict[str, Arg] = {}

    def __init__(self, **kwargs):
        self.args = {}
        self.parent: t.Optional[Expression] = None
        self.arg_key: t.Optional[str] = None
        self._type = None
        self._meta: t.Optional[t.Dict[str, t.Any]] = None

        for k in self.arg_types.keys():
            if not self.arg_types[k].optional and k not in kwargs:
                raise Exception(f'Missing required property "{k}"')
            setattr(self, k, kwargs.get(k))
        self.validate()
    
    def __init_subclass__(cls, **kwargs):
        cls.arg_types = {}
        for attr in dir(cls):
            if isinstance(getattr(cls, attr), Arg):
                cls.arg_types[attr] = getattr(cls, attr)
        
    def __deepcopy__(self, memo):
        copy = self.__class__(**deepcopy(self.args))
        if self._type is not None:
            copy._type = self._type.copy()
        if self._meta is not None:
            copy._meta = deepcopy(self._meta)
        return copy

    @property
    def hashable_args(self) -> frozenset[tuple]:
        args = []
        for arg, values in self.args.items():
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
            assert self.arg_key is not None
            assert self.arg_key in self.parent.args
            assert self in list_values(self.parent.args[self.arg_key])
        else:
            assert self.arg_key is None
        for arg, values in self.args.items():
            for val in list_values(values):
                if self.arg_types[arg].type is not None and not isinstance(val, self.arg_types[arg].type):
                    raise TypeError(f'Expected {arg} to be of type {self.arg_types[arg].type}, got {val}')
                if isinstance(val, Expression):
                    assert val.parent is self
                    assert val.arg_key == arg
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
    
    def iter_props(self) -> t.Iterator[tuple[str, t.Any]]:
        for key, values in self.args.items():
            for val in list_values(values):
                if not isinstance(val, Expression):
                    yield key, val

    def iter_expressions(self) -> t.Iterator[Expression]:
        """ Yields the key and expression for all arguments, exploding list args. """
        for values in self.args.values():
            for val in list_values(values):
                if isinstance(val, Expression):
                    yield val
    
    def dfs(self, prune:t.Callable[[Expression], bool]=None) -> t.Iterator[Expression]:
        """
        Returns a generator object which visits all nodes in this tree in
        the DFS (Depth-first) order.
        """
        yield self
        if prune and prune(self):
            return
        for v in self.iter_expressions():
            yield from v.dfs(prune)

    def bfs(self, prune:t.Callable[[Expression], bool]=None) -> t.Iterator[Expression]:
        """
        Returns a generator object which visits all nodes in this tree in
        the BFS (Breadth-first) order.
        """
        queue = deque([self])
        while queue:
            item = queue.popleft()
            yield item
            if prune and prune(item):
                continue
            for v in item.iter_expressions():
                queue.append(v)
    
    def walk(self, bfs: bool=True, prune:t.Callable[[Expression], bool]=None) -> t.Iterator[Expression]:
        """
        Returns a generator object which visits all nodes in this tree.

        Args:
            bfs (bool): if set to True the BFS traversal order will be applied,
                otherwise the DFS traversal will be used instead.
            prune ((node) -> bool): callable that returns True if
                the generator should stop traversing this branch of the tree.
        """
        return self.bfs(prune=prune) if bfs else self.dfs(prune=prune)

    def find_all(self, *types: t.Type[E], bfs: bool = True) -> t.Iterator[E]:
        """
        Returns a generator object which visits all nodes in this tree and only
        yields those that match at least one of the specified expression types.
        """
        for expression in self.walk(bfs=bfs):
            if isinstance(expression, types):
                yield expression
    
    def find(self, *types: t.Type[E], bfs: bool = True) -> t.Optional[E]:
        """
        Returns the first node in this tree which matches at least one of
        the specified types.
        """
        return next(self.find_all(*types, bfs=bfs), None)

    def replace_children(self, fun: t.Callable[[Expression], t.Any], *args, **kwargs) -> Self:
        """
        Replace children of an expression with the result of a lambda fun(child) -> exp.
        """
        for k, values in self.args.items():
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
        self.arg_key = None
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
        props = [
            f'{k}={repr(v)}'
            for k,v in self.iter_props()
        ]
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
        assert hasattr(owner, 'arg_types')
        self.name = name
   
    def __set__(self, instance: Expression, value):
        # remove parent of old args
        for old_value in list_values(instance.args.get(self.name)):
            if isinstance(old_value, Expression):
                old_value.parent = None
                old_value.arg_key = None

        # set parent of new args
        for new_value in list_values(value):
            if isinstance(new_value, Expression):
                new_value.parent = instance
                new_value.arg_key = self.name
            
        instance.args[self.name] = self.coerce_cardinality(value)
    
    def __get__(self, instance: t.Optional[Expression], owner=None):
        if instance is None:
            return self
        return self.coerce_cardinality(instance.args.get(self.name))

    def coerce_cardinality(self, value):
        values = list_values(value)

        if not self.optional and len(values) == 0:
            raise TypeError(f'Expected {self.name} to not be null: {value}')

        if not self.many:
            if len(values) > 1:
                raise TypeError(f'Expected {self.name} to only have one value: {value}')
            values = None if len(values) == 0 else values[0]
        
        return values

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

class EdgeDefinition(Definition, Query):
    cardinality: str = Arg(type=str, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        if self.cardinality and self.cardinality not in ('+', '?', '*', '!'):
            raise ValueError(f'Invalid cardinality {self.cardinality}')
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
    edges: list[EdgeDefinition] = Arg(type=EdgeDefinition, many=True, optional=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        type_names = set()
        for child in self.edges:
            if child.name in type_names:
                raise ValueError(f'multiple definitions with same name: {child.name}')
            type_names.add(child.name)

class Module(TypesContainer):
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

class Model(TypeDefinition, TypesContainer, EdgesContainer):
    indexes: list[Index] = Arg(type=Index, many=True)

    def validate(self, **kwargs):
        super().validate(**kwargs)
        edge_names = {edge.name for edge in self.edges}
        for idx in self.indexes:
            for name in idx.names:
                if name not in edge_names:
                    raise ValueError(f'edge referenced in index not defined in model: {name}')

class Call(Expression):
    """ Abstract class for all AST nodes that call a function """
    pass
    
class Binary(Call):
    lhs = Arg(type=Expression)
    rhs = Arg(type=Expression)

class Add(Binary):
    pass

class Subtract(Binary):
    pass

class Literal(Expression):
    value: t.Union[int, float, str] = Arg(type=(int, float, str))

def convert() -> Expression:
    """ Convert python value to Expression """
    pass

def evaluate(exp: Expression) -> t.Any:
    if isinstance(exp, Literal):
        return exp.value
    if isinstance(exp, Add):
        return exp.lhs + exp.rhs
    if isinstance(exp, Subtract):
        return exp.lhs - exp.rhs

if __name__ == '__main__':
    a = Module(
        models=[
            Model(
                name='Person',
                indexes=[
                    Index(names=['id']),
                ],
                edges=[
                    EdgeDefinition(name='id', value=Literal(value=1)),
                    EdgeDefinition(name='name', value=Literal(value='John')),
                    EdgeDefinition(name='age', value=Literal(value=30)),
                ],
            ),
            Model(
                name='Company',
                indexes=[
                    Index(names=['name']),
                ],
                edges=[
                    EdgeDefinition(name='name', value=Literal(value='Apple')),
                    EdgeDefinition(name='location', value=Literal(value='Cupertino')),
                ]
            ),
        ]
    )
    print('hi')