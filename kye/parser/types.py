from __future__ import annotations
from typing import Optional

class Environment:
    local: dict[str, ChildEnvironment]

    def __init__(self):
        self.local = {}
    
    @property
    def path(self):
        return tuple()

    @property
    def global_name(self):
        return '.'.join(self.path)
    
    def get_path(self, key):
        return (*self.resolve(key).path, key)
    
    def resolve(self, key):
        if key in self.local:
            return self
        raise KeyError(f'Could not resolve "{key}"')

    def get(self, key, __default = None):
        return self.local.get(key, __default)

    def __getitem__(self, key):
        if key in self.local:
            return self.local[key]
        raise KeyError(f'"{key}" not defined')
    
    def __contains__(self, key):
        return key in self.local

    def __repr__(self):
        return self.global_name + '{' + ','.join(self.local.keys()) + '}'


class ChildEnvironment(Environment):
    name: str
    parent: Environment

    def __init__(self, name: str, parent: Environment):
        super().__init__()
        assert type(name) is str
        assert '.' not in name
        assert isinstance(parent, Environment)
        self.name = name
        self.parent = parent
        assert self.name not in self.parent.local
        self.parent.local[self.name] = self
    
    @property
    def path(self):
        return (*self.parent.path, self.name)
    
    def resolve(self, key):
        if key in self.local:
            return self
        return self.parent.resolve(key)

    def get(self, key, default = None):
        if key in self.local:
            return self.local[key]
        return self.parent.get(key, default)
    
    def __getitem__(self, key):
        if key in self.local:
            return self.local[key]
        return self.parent[key]
    
    def __contains__(self, key):
        return key in self.local or (key in self.parent)


class Type:
    ref: Optional[str] = None
    name: Optional[str] = None
    extends: Optional[str] = None
    indexes: list[list[str]] = []
    edges: dict[str, Type] = {}

    def __init__(self,
                 ref: str = None,
                 name: str = None,
                 extends: str = None,
                 indexes: list[list[str]] = [],
                 edges: dict[str, Type] = {}):
        self.ref = ref
        self.name = name
        self.extends = extends
        self.indexes = indexes
        self.edges = edges

    def __getitem__(self, name: str):
        return self.edges[name]

    def __contains__(self, name: str):
        return name in self.edges

    def __repr__(self):
        all_indexes = [idx for idxs in self.indexes for idx in idxs]
        non_index_edges = [edge for edge in self.edges.keys() if edge not in all_indexes]
        return "Type<{}{}{}{}>".format(
            self.ref or self.name or '',
            ':' + self.extends if self.extends else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )