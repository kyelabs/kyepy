from __future__ import annotations
from pydantic import BaseModel, model_validator, field_validator, constr
from typing import Optional, Literal, Union

TAB = '    '

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')

class AST(BaseModel):
    _parent: Optional[AST] = None

    # property setter for _parent
    def set_parent(self, parent):
        self._parent = parent
        return self
    
    def get_parent(self):
        return self._parent
    
    def get_model_name(self):
        parent = self.get_parent()
        parent_name = parent.get_model_name() if parent else None
        if isinstance(self, Model):
            if parent_name is not None:
                parent_name += '.' + self.name
            else:
                parent_name = self.name
        return parent_name

    def get_local_definitions(self):
        return []
    
    def has_local_definition(self, name):
        for defn in self.get_local_definitions():
            if name == defn.name:
                return True
    
    def get_local_definition(self, name):
        for defn in self.get_local_definitions():
            if name == defn.name:
                return defn

    def get_definition(self, name):
        parent = self.get_parent()
        if parent:
            if parent.has_local_definition(name):
                return parent.get_local_definition(name)
            else:
                return parent.get_definition(name)
        return ValueError(f'"{name}" not defined')

class Script(AST):
    definitions: list[Union[TypeAlias, Model]]

    @model_validator(mode='after')
    def validate_definitions(self):
        type_names = set()
        for defn in self.definitions:
            # raise error if definition name is duplicated
            if defn.name in type_names:
                raise ValueError(f'Model name {defn.name} is duplicated in model {self.name}')
            type_names.add(defn.name)

            defn.set_parent(self)
        return self

    def get_local_definitions(self):
        return self.definitions

    @property
    def models(self):
        return [d for d in self.definitions if isinstance(d, Model)]
    
    @property
    def aliases(self):
        return [d for d in self.definitions if isinstance(d, TypeAlias)]
    
    def to_kye(self, depth=0):
        return '\n\n'.join(defn.to_kye(depth) for defn in self.definitions)

class Model(AST):
    name: TYPE
    indexes: list[Index]
    edges: list[Edge]

    @model_validator(mode='after')
    def validate_indexes(self):
        edge_names = set()
        for edge in self.edges:
            # raise error if edge name is duplicated
            if edge.name in edge_names:
                raise ValueError(f'Edge name {edge.name} is duplicated in model {self.name}')
            edge_names.add(edge.name)
            edge.set_parent(self)

        for idx in self.indexes:
            for name in idx.get_key_names():
                # raise error if index name is not an edge name
                if name not in edge_names:
                    raise ValueError(f'Index {name} is not an edge name in model {self.name}')
            idx.set_parent(self)
        return self
    
    def get_local_definitions(self):
        return self.edges
    
    def get_key_names(self):
        return list({idx for idxs in self.indexes for idx in idxs.get_key_names()})
    
    def __repr__(self):
        indexes = ''.join(repr(idx) for idx in self.indexes)
        return 'Model<' + self.name + indexes + '>'
    
    def to_kye(self, depth=0):
        indexes = ''.join(idx.to_kye() for idx in self.indexes)
        edges = ''
        if len(self.edges) == 0:
            edges = ' {}'
        else:
            edges = ' {\n'
            for edge in self.edges:
                edges += TAB*(depth+1) + edge.to_kye(depth+1) + ',\n'
            edges += TAB*depth + '}'
        return self.name + indexes + edges

class Index(AST):
    edges: list[EDGE]

    def __repr__(self):
        return '(' + ','.join(self.edges) + ')'

    def get_key_names(self):
        return self.edges

    def to_kye(self, depth=0):
        return '(' + ','.join(self.edges) + ')'

class Edge(AST):
    name: EDGE
    typ: Optional[Type]
    cardinality: Optional[Literal['*','?','+','!']]

    @model_validator(mode='after')
    def set_type_parent(self):
        if self.typ:
            self.typ.set_parent(self)
        return self

    @field_validator('name')
    def validate_name(cls, v):
        if v[0].isupper():
            raise ValueError('Edge names must start with an lowercase letter')
        return v
    
    def to_kye(self, depth=0):
        return f'{self.name}: {self.typ.to_kye(depth=depth)}{self.cardinality or ""}'

class TypeRef(AST):
    name: TYPE

    @field_validator('name')
    def validate_name(cls, v):
        if v[0].islower():
            raise ValueError('Type names must start with an uppercase letter')
        return v
    
    def __repr__(self):
        return 'Ref<' + self.name + '>'
    
    def to_kye(self, depth=0):
        return self.name
    
    def resolve(self):
        return self.get_definition(self.name)

class TypeAlias(AST):
    name: TYPE
    typ: Type

    @model_validator(mode='after')
    def set_type_parent(self):
        self.typ.set_parent(self)
        return self
    
    def __repr__(self):
        return 'Alias<' + self.name + ':' + repr(self.typ) + '>'
    
    def to_kye(self, depth=0):
        return f'type {self.name}: {self.typ.to_kye()}'

class TypeIndex(AST):
    typ: TypeRef
    index: Index

    @model_validator(mode='after')
    def set_type_parent(self):
        self.typ.set_parent(self)
        self.index.set_parent(self)
        return self
    
    def to_kye(self, depth=0):
        return self.name + self.index.to_kye()

Type = Union[TypeAlias, Model, TypeIndex, TypeRef]