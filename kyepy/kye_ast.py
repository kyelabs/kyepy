from __future__ import annotations
from pydantic import BaseModel, model_validator, field_validator
from typing import Optional, Literal, Union, Any

TAB = '    '

class TypeRef(BaseModel):
    name: str

    @field_validator('name')
    def validate_name(cls, v):
        if v[0].islower():
            raise ValueError('Type names must start with an uppercase letter')
        return v
    
    def __repr__(self):
        return 'Ref<' + self.name + '>'
    
    def to_kye(self, depth=0):
        return self.name

class Alias(BaseModel):
    name: str
    typ: Union[Alias, Model, Const, Index, TypeRef]
    
    def __repr__(self):
        return 'Alias<' + self.name + ':' + repr(self.typ) + '>'
    
    def to_kye(self, depth=0):
        return f'type {self.name}: {self.typ.to_kye()}'

class Edge(BaseModel):
    name: str
    typ: Optional[Type]
    cardinality: Optional[Literal['*','?','+','!']]

    @field_validator('name')
    def validate_name(cls, v):
        if v[0].isupper():
            raise ValueError('Edge names must start with an lowercase letter')
        return v
    
    def to_kye(self, depth=0):
        return f'{self.name}: {self.typ.to_kye(depth=depth)}{self.cardinality or ""}'

class Model(BaseModel):
    name: str
    indexes: list[list[str]]
    edges: list[Edge]

    @model_validator(mode='after')
    def validate_indexes(self):
        edge_names = set()
        for edge in self.edges:
            # raise error if edge name is duplicated
            if edge.name in edge_names:
                raise ValueError(f'Edge name {edge.name} is duplicated in model {self.name}')
            edge_names.add(edge.name)

        for idx in self.indexes:
            for name in idx:
                # raise error if index name is not an edge name
                if name not in edge_names:
                    raise ValueError(f'Index {name} is not an edge name in model {self.name}')
    
    def get_edge(self, name):
        for edge in self.edges:
            if edge.name == name:
                return edge
        return None
    
    def __repr__(self):
        indexes = ''
        for idx in self.indexes:
            indexes += '(' + ','.join(idx) + ')'
        return 'Model<' + self.name + indexes + '>'
    
    def to_kye(self, depth=0):
        indexes = ''
        for idx in self.indexes:
            indexes += '(' + ','.join(idx) + ')'
        
        edges = ''
        if len(self.edges) == 0:
            edges = ' {}'
        else:
            edges = ' {\n'
            for edge in self.edges:
                edges += TAB*(depth+1) + edge.to_kye(depth+1) + ',\n'
            edges += TAB*depth + '}'
        return self.name + indexes + edges

class Const(BaseModel):
    value: object
    
    def to_kye(self, depth=0):
        if type(self.value) is str:
            return f'"{self.value}"'
        return str(self.value)

class Index(BaseModel):
    name: str
    index: list[str]
    
    def to_kye(self, depth=0):
        return self.name + '(' + ','.join(self.index) + ')'

class Script(BaseModel):
    definitions: list[Union[Alias, Model]]
    
    @property
    def models(self):
        return [d for d in self.definitions if isinstance(d, Model)]
    
    @property
    def aliases(self):
        return [d for d in self.definitions if isinstance(d, Alias)]
    
    def to_kye(self, depth=0):
        return '\n\n'.join(defn.to_kye(depth) for defn in self.definitions)

Type = Union[Alias, Model, Const, Index, TypeRef]