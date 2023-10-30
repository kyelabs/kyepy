from __future__ import annotations
from typing import Iterable, Union, Callable
from kyepy.dataset import Type

Key = Union[str, int, Callable]

class Accessor:
    @property
    def value(self):
        pass

class ValueFormatter:
    def __init__(self, model: Type, data: Accessor):
        self.model = model
        self.data = data

    def validate(self) -> bool:
        pass

    def consume(self) -> object:
        return self.data.value

    def edges(self) -> dict[str, Accessor]:
        return {}

class Format:
    def __init__(self):
        pass

    def collect_errors(self, typ: Type, data: Accessor):
        # If no class defined then skip
        if not hasattr(self, typ.name):
            return []
        
        # Get the formatter class
        formatter = getattr(self, typ.name)(typ, data)
        if not formatter.validate():
            return [ data ]
        
        # Recursively collect errors from edges
        edge_errors = []
        for edge_name, child_data in formatter.edges().items():
            edge_errors += self.collect_errors(typ.edges[edge_name].type, child_data)
        return edge_errors
        

    def load(self, typ: Type, data: Iterable):
        data = self.Accessor(data)
        for parent_type in typ.inheritance_chain:
            errors = self.collect_errors(parent_type, data)
            if len(errors) > 0:
                invalid_data = errors[0]
                raise ValueError(f'{"(" + str(invalid_data) + "): " if str(invalid_data) else ""}"{data.value}" is not a {typ.name}')
            # for edge in formatter.edges():
            #     self.load(typ.edges[edge].type, edge.value)


class JsonFormat(Format):

    class Accessor(Accessor):
        def __init__(self, root: Iterable, path: tuple[str] = (), query: tuple[Key] = ()):
            self.root = root
            self.path = path
            self.query = query
        
        def get(self, edge: str, query: Key) -> JsonFormat.Accessor:
            return JsonFormat.Accessor(self.root, self.path + (edge,), self.query + (query,))

        @property
        def value(self):
            val = self.root
            for key in self.path:
                if callable(key):
                    val = key(val)
                else:
                    val = val[key]
            return val
        
        def __str__(self):
            s = ''
            for key in self.path:
                if callable(key):
                    s = key.__name__ + '(' + s + ')'
                elif type(key) is int:
                    s += '[' + str(key) + ']'
                else:
                    s += '.' + key
            return s
    
    class String(ValueFormatter):
        def validate(self) -> bool:
            return isinstance(self.data.value, str)
        
        def edges(self):
            return {
                'length': self.data.get('length', len)
            }
    
    class Number(ValueFormatter):
        def validate(self) -> bool:
            return isinstance(self.data.value, (int, float))
    
    class Boolean(ValueFormatter):
        def validate(self) -> bool:
            return isinstance(self.data.value, bool)
    
    class Struct(ValueFormatter):
        def validate(self) -> bool:
            return isinstance(self.data.value, dict)
        
        def edges(self) -> Iterable[JsonFormat.Accessor]:
            edges = {}
            for key in self.data.value.keys():
                child = self.data.get(key, key)
                if child.value is not None:
                    edges[key] = child
            return edges