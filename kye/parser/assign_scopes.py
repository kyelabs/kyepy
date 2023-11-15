from __future__ import annotations
from kye.parser.kye_ast import *

class Scope:
    def __init__(self, name, parent: Scope):
        if name is None or parent is None:
            assert name is None and parent is None
        else:
            assert name is not None
            assert parent is not None
        self.name = name
        self.parent = parent
        self.definitions = {}
    
    @property
    def path(self):
        if self.parent and self.parent.name:
            return self.parent.path + '.' + self.name
        return self.name
    
    def __getitem__(self, key):
        if key in self.definitions:
            return self.definitions[key]
        if self.parent is not None:
            return self.parent[key]
        raise KeyError(key)

    def __setitem__(self, key, value):
        self.definitions[key] = value
    
    def __contains__(self, key):
        return key in self.definitions or (self.parent is not None and key in self.parent)
    
    def __repr__(self):
        return self.path + '{' + ','.join(self.definitions.keys()) + '}'

def assign_scopes(node: AST, scope):
    assert scope is not None
    # Add definition to parent's scope
    if isinstance(node, Definition):
        scope[node.name] = node
    # Create new child scope for model
    if isinstance(node, ModelDefinition):
        scope = Scope(name=node.name, parent=scope)
    for child in node.children:
        assign_scopes(child, scope)
    setattr(node, 'scope', scope)