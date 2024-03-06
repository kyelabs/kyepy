from __future__ import annotations
import typing as t
from typing_extensions import Self
from collections.abc import Iterable
from collections import deque
from copy import deepcopy

T = t.TypeVar('T')
E = t.TypeVar('E')

class Expression:
    arg_types: dict[str, Arg]

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
        self.check_arg_types()
        
    def __deepcopy__(self, memo):
        copy = self.__class__(**deepcopy(self.args))
        if self._type is not None:
            copy._type = self._type.copy()
        if self._meta is not None:
            copy._meta = deepcopy(self._meta)
        return copy

    @property
    def hashable_args(self) -> frozenset[tuple]:
        args = (
            (arg, *list_values(values))
            for arg, values in self.args.items()
        )
        return frozenset(
            arg for arg in args
            if len(arg) > 1
        )

    def __eq__(self, other) -> bool:
        return type(self) is type(other) and hash(self) == hash(other)

    def __hash__(self) -> int:
        return hash((self.__class__, self.hashable_args))
    
    def check_arg_types(self, recurse=False) -> None:
        for arg, values in self.args.items():
            for val in list_values(values):
                if self.arg_types[arg].type is not None and not isinstance(val, self.arg_types[arg].type):
                    raise TypeError(f'Expected {arg} to be of type {self.arg_types[arg].type}, got {val}')
                if isinstance(val, Expression):
                    assert val.parent is self
                    assert val.arg_key == arg
                    if recurse:
                        val.check_arg_types(recurse=recurse)
    
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
        self.name = name
        if not hasattr(owner, 'arg_types'):
            owner.arg_types = {}
        owner.arg_types = { **owner.arg_types, self.name: self }
   
    def __set__(self, instance, value):
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
    
    def __get__(self, instance, owner=None):
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

class Model(Expression):
    indexes = Arg(type=str)

class Func(Expression):
    kwargs = Arg(type=str, optional=True)

class Binary(Func):
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

def is_list(values):
    return isinstance(values, (list, tuple))
    # return isinstance(values, Iterable) and not isinstance(values, (str, bytes))

@t.overload
def list_values(values: t.Iterable[t.Optional[T]]) -> list[T]: ...

@t.overload
def list_values(values: t.Optional[T]) -> list[T]: ...

def list_values(values):
    if values is None:
        return []
    if is_list(values):
        return [v for v in values if v is not None]
    else:
        return [ values ]

def evaluate(exp: Expression) -> t.Any:
    if isinstance(exp, Literal):
        return exp.value
    if isinstance(exp, Add):
        return exp.lhs + exp.rhs
    if isinstance(exp, Subtract):
        return exp.lhs - exp.rhs

if __name__ == '__main__':
    a1 = Add(
            lhs=Literal(value=1),
            rhs=Literal(value=2),
        )
    a2 = Add(
            lhs=Literal(value=1),
            rhs=Literal(value=3),
        )
    print(a1 == a2)
    print('hi')