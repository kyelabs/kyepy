from __future__ import annotations
from pydantic import BaseModel, model_validator, field_validator
from typing import Optional, Literal, Union, Any

TAB = '    '

class AST(BaseModel):
    _parent: Optional[AST]

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
        return self
    
    @property
    def models(self):
        return [d for d in self.definitions if isinstance(d, Model)]
    
    @property
    def aliases(self):
        return [d for d in self.definitions if isinstance(d, TypeAlias)]
    
    def to_kye(self, depth=0):
        return '\n\n'.join(defn.to_kye(depth) for defn in self.definitions)

class Model(AST):
    name: str
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

        for idx in self.indexes:
            for name in idx.edges:
                # raise error if index name is not an edge name
                if name not in edge_names:
                    raise ValueError(f'Index {name} is not an edge name in model {self.name}')
        return self
    
    def get_edge(self, name):
        for edge in self.edges:
            if edge.name == name:
                return edge
        return None
    
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
    edges: list[str]

    def __repr__(self):
        return '(' + ','.join(self.edges) + ')'

    def to_kye(self, depth=0):
        return '(' + ','.join(self.edges) + ')'

class Edge(AST):
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

class TypeRef(AST):
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

class TypeAlias(AST):
    name: str
    typ: Union[TypeAlias, Model, TypeLiteral, TypeIndex, TypeRef]
    
    def __repr__(self):
        return 'Alias<' + self.name + ':' + repr(self.typ) + '>'
    
    def to_kye(self, depth=0):
        return f'type {self.name}: {self.typ.to_kye()}'

class TypeIndex(AST):
    name: str
    index: Index
    
    def to_kye(self, depth=0):
        return self.name + self.index.to_kye()

class TypeLiteral(AST):
    value: object
    
    def to_kye(self, depth=0):
        if type(self.value) is str:
            return f'"{self.value}"'
        return str(self.value)

Type = Union[TypeAlias, Model, TypeLiteral, TypeIndex, TypeRef]