from __future__ import annotations
import typing as t

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