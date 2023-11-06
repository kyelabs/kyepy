from __future__ import annotations
from kyepy.compiled import CompiledDataset, CompiledEdge, CompiledType, TYPE_REF, EDGE


class Edge:
    def __init__(self, name: EDGE, edge: CompiledEdge, models: Models):
        self.name = name
        self._edge = edge
        self._models = models
    
    @property
    def type(self):
        return self._models[self._edge.type]
    
    def __repr__(self):
        return repr(self._edge)

class Type:
    def __init__(self, name: TYPE_REF):
        self.name = name
        self.indexes = []
        self.extends = None
        self.edges = {}
    
    def __getitem__(self, name: EDGE):
        return self.edges[name]

    def __contains__(self, name: EDGE):
        return name in self.edges
    
    def __repr__(self):
        return "Type<{}>".format(self.name)

class DefinedType(Type):
    def __init__(self, ref: TYPE_REF, type: CompiledType, models: Models):
        self.ref = ref
        self._type = type
        self._models = models

        self.edges = {
            name: Edge(name, edge, models)
            for name, edge in self._type.edges.items()
        }
        for parent in self.parents():
            for edge in parent.edges.values():
                if edge.name not in self.edges:
                    self.edges[edge.name] = edge
    
    @property
    def name(self):
        return self._type.name if self._type.name else self.extends.name

    @property
    def indexes(self):
        return self._type.indexes if self._type.indexes else self.extends.indexes
    
    @property
    def extends(self):
        return self._models[self._type.extends] if self._type.extends else None

    def parents(self):
        if self.extends:
            return [ self.extends ] + self.extends.parents()
        return []
    
    def __repr__(self):
        return repr(self._type)

class Models:
    globals = {
        'Number': Type('Number'),
        'String': Type('String'),
        'Boolean': Type('Boolean'),
        'Struct': Type('Struct'),
        'Model': Type('Model'),
    }

    def __init__(self, models: CompiledDataset):
        self._models = models

        # self.models = {
        #     **self.globals,
        #     **{
        #         name: DefinedType(name, type, self)
        #         for name, type in self._models.models.items()
        #     }
        # }

    def __getitem__(self, ref: TYPE_REF):
        if ref in self.globals:
            return self.globals[ref]
        if ref in self._models:
            return DefinedType(ref, self._models[ref], self)
        raise KeyError(ref)

    def __contains__(self, ref: TYPE_REF):
        return ref in self.globals or ref in self.models
    
    def __repr__(self):
        return repr(self._models)