from __future__ import annotations
import typing as t
from collections import deque

T = t.TypeVar('T')

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


def walk_dfs(node: T, iterator:t.Callable[[T], t.Iterator[T]]) -> t.Iterator[T]:
    """
    Returns a generator object which visits all nodes in this tree in
    the DFS (Depth-first) order.
    """
    yield node
    for child in iterator(node):
        yield from walk_dfs(child, iterator)

def walk_bfs(node: T, iterator:t.Callable[[T], t.Iterator[T]]) -> t.Iterator[T]:
    """
    Returns a generator object which visits all nodes in this tree in
    the BFS (Breadth-first) order.
    """
    queue = deque([node])
    while queue:
        item = queue.popleft()
        yield item
        for v in iterator(item):
            queue.append(v)