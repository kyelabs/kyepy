from __future__ import annotations
from typing import Optional

class Environment:
    name: Optional[str]
    parent: Optional[Environment]
    local: dict[str, Optional[Type]]

    def __init__(self, name: Optional[str] = None, parent: Optional[Environment] = None):
        self.name = name
        self.parent = parent
        self.local = {}
        self.frozen = False
    
    @property
    def global_name(self):
        return '.'.join(self.get_path())

    def get_path(self, key=None):
        if key is None:
            path = self.parent.get_path() if self.parent is not None else tuple()
            if self.name is not None:
                path = (*path, self.name)
            return path
        else:
            return (*self.resolve(key).get_path(), key)
    
    def freeze(self):
        self.frozen = True
        return self
    
    def resolve(self, key):
        if key in self.local:
            return self
        if self.parent is not None:
            return self.parent.resolve(key)
        raise KeyError(key)

    def get(self, key, default = None):
        if key in self.local:
            return self.local[key]
        if self.parent is not None:
            return self.parent.get(key, default)
        return default

    def define(self, name, value: Optional[Type] = None):
        if self.frozen:
            raise RuntimeError('Cannot define new types in a frozen environment')
        if name in self.local:
            raise KeyError(f'Type {name} is already defined')
        self.local[name] = value
    
    def define_type(self,
                    name: str = None,
                    extends: str = None,
                    indexes: list[list[str]] = [],
                    edges: dict[str, Type] = {}) -> Type:
        model = Type(
            ref='.'.join((*self.get_path(), name)),
            name=name,
            extends=extends,
            indexes=indexes,
            edges=edges
        )
        self.define(name, model)
        return model
    
    def __getitem__(self, key):
        if key in self.local:
            return self.local[key]
        if self.parent is not None:
            return self.parent[key]
        raise KeyError(key)
    
    def __contains__(self, key):
        return key in self.local or (self.parent is not None and key in self.parent)

    def __repr__(self):
        return self.global_name + '{' + ','.join(self.local.keys()) + '}'


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