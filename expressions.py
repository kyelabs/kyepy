from __future__ import annotations
import typing as t
from collections.abc import Iterable
from collections import deque
from copy import deepcopy

T = t.TypeVar('T')
E = t.TypeVar('E')

class Expression:
    arg_types: dict[str, dict]

    def __init__(self, **kwargs):
        self.args = {}
        self.parent: t.Optional[Expression] = None
        self.arg_key: t.Optional[str] = None
        self._type = None
        self._meta: t.Optional[t.Dict[str, t.Any]] = None

        for k in kwargs.keys():
            if k not in self.arg_types:
                raise Exception(f'Unexpected property {k}')
        for k in self.arg_types.keys():
            if not self.arg_types[k]['nullable'] and k not in kwargs:
                raise Exception(f'Missing required property "{k}"')
            setattr(self, k, kwargs.get(k))
        
    def __deepcopy__(self, memo):
        copy = self.__class__(**deepcopy(self.args))
        if self._type is not None:
            copy._type = self._type.copy()
        if self._meta is not None:
            copy._meta = deepcopy(self._meta)
    
    def copy(self):
        """
        Returns a deep copy of the expression
        """
        new = deepcopy(self)
        new.parent = self.parent
        return new

    def depth(self):
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
    
    def iter_props(self) -> t.Iterator[t.Any]:
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
    
    def dfs(self, prune:t.Callable[[Expression], bool]=None):
        """
        Returns a generator object which visits all nodes in this tree in
        the DFS (Depth-first) order.
        """
        yield self
        if prune and prune(self):
            return
        for v in self.iter_expressions():
            yield from v.dfs(prune)

    def bfs(self, prune:t.Callable[[Expression], bool]=None):
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
    
    def walk(self, bfs: bool=True, prune:t.Callable[[Expression], bool]=None):
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

    def replace_children(self, fun: t.Callable[[Expression], t.Any], *args, **kwargs) -> None:
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
    
    def transform_children(self, fun: t.Callable[[Expression], t.Any], *args, **kwargs) -> dict:
        """
        Recursively visits all tree nodes (excluding already transformed ones)
        and applies the given transformation function to each node.
        """
        transformed_args = {}
        for k, values in self.args.items():
            new_args = []
            use_list = is_list(values)
            for val in list_values(values):
                if isinstance(val, Expression):
                    out = fun(val, *args, **kwargs)
                    use_list |= is_list(out)
                    new_args += list_values(out)
                else:
                    new_args.append(val)
            # Convert to single value if original was a
            # single value _and_ the result is a single value
            if not use_list:
                new_args = new_args[0] if len(new_args) else None
            transformed_args[k] = new_args
        return transformed_args

    def transform(self, fun: t.Callable[[Expression, dict], t.Any], *args, **kwargs):
        """
        Recursively visits all tree nodes
        and applies the given transformation function to each node.
        """
        transformed_args = self.transform_children(lambda child: child.transform(fun, *args, **kwargs))
        new_node = fun(self, transformed_args, *args, **kwargs)
        if new_node is None or not isinstance(new_node, Expression):
            return new_node
        if new_node is not self:
            new_node.parent = self.parent
            return new_node
        
        new_node.replace_children(lambda child: child.transform(fun, *args, copy=False, **kwargs))
        return new_node

    def replace(self, expression):
        if isinstance(expression, Expression) and not self.parent:
            return expression

        self.parent.replace_children(lambda child: expression if child is self else child)
        self.parent = None
        return expression

    def pop(self):
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
    def __init__(self, type=None, nullable=False, multiple=False):
        self.name = None
        self.type = type
        self.nullable = nullable
        self.multiple = multiple
    
    def __set_name__(self, owner, name):
        self.name = name
        if not hasattr(owner, 'arg_types'):
            setattr(owner, 'arg_types', {})
        owner.arg_types[name] = {
            'type': self.type,
            'nullable': self.nullable,
            'multiple': self.multiple,
        }
   
    def __set__(self, instance, value):
        values = list_values(value)

        if not self.nullable and len(values) == 0:
            raise TypeError(f'Expected {self.name} to not be null: {value}')

        for val in values:
            if self.type is not None and not isinstance(val, self.type):
                raise TypeError(f'Expected {self.name} to be an instance of {self.type.__name__}: {value}')
            if isinstance(val, Expression):
                val.parent = instance
                val.arg_key = self.name

        if not self.multiple:
            if len(values) > 1:
                raise TypeError(f'Expected {self.name} to only have one value: {value}')
            values = None if len(values) == 0 else values[0]
            
        instance.args[self.name] = values
    
    def __get__(self, instance, owner=None):
        return instance.args.get(self.name)

class Model(Expression):
    indexes = Arg(type=str)

class Func(Expression):
    kwargs = Arg(type=str, nullable=True)

class Binary(Func):
    lhs = Arg(type=Expression)
    rhs = Arg(type=Expression)

class Add(Binary):
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

if __name__ == '__main__':
    m = Add(
        lhs=Literal(value=1),
        rhs=Literal(value=2)
    )
    print(m.to_xml())
    print('hi')