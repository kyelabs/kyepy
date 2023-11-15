from __future__ import annotations
from typing import Optional

class Environment:
    parent: Optional[Environment]
    local: dict[str, Type]

    def __init__(self, parent: Optional[Environment]):
        self.parent = parent
        self.local = {}
        self.frozen = False
    
    def freeze(self):
        self.frozen = True
        return self
    
    def __getitem__(self, key):
        if key in self.local:
            return self.local[key]
        if self.parent is not None:
            return self.parent[key]
        raise KeyError(key)
    
    def __setitem__(self, key, value):
        if self.frozen:
            raise RuntimeError('Cannot define new types in a frozen environment')
        if key in self.local:
            raise KeyError(f'Type {key} is already defined')
        self.local[key] = value
    
    def __contains__(self, key):
        return key in self.local or (self.parent is not None and key in self.parent)

    def __repr__(self):
        return '{' + ','.join(self.local.keys()) + '}'


class Type:
    name: str
    edges: dict[str, Type]

    def __init__(self, name: str):
        self.name = name