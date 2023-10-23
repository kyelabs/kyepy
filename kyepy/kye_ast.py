from __future__ import annotations
from pydantic import BaseModel, model_validator, field_validator, constr
from typing import Optional, Literal, Union

TAB = '    '

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')

class AST(BaseModel):
    name: Optional[str] = None
    children: list[AST] = []

    def __str__(self):
        return self.name or super().__str__()

    def traverse(self, path=tuple()):
        path = path + (self,)
        for child in self.children:
            yield path, child
            yield from child.traverse(path=path)

class Script(AST):
    children: list[Union[TypeAlias, Model]]

    @model_validator(mode='after')
    def validate_definitions(self):
        type_names = set()
        for child in self.children:
            # raise error if definition name is duplicated
            if child.name in type_names:
                raise ValueError(f'Model name {child.name} is duplicated in model {self.name}')
            type_names.add(child.name)
        return self
    
    def __repr__(self):
        return f"Script<{','.join(child.name for child in self.children)}>"

class Model(AST):
    name: TYPE
    indexes: list[Index]
    edges: list[Edge]

    @model_validator(mode='after')
    def validate_indexes(self):
        # self.children.extend(self.indexes)
        self.children = self.edges
        edge_names = set()
        for edge in self.edges:
            # raise error if edge name is duplicated
            if edge.name in edge_names:
                raise ValueError(f'Edge name {edge.name} is duplicated in model {self.name}')
            edge_names.add(edge.name)
        
        idx_names = set()
        for idx in self.indexes:
            for name in idx.edges:
                # raise error if index name is not an edge name
                if name not in edge_names:
                    raise ValueError(f'Index {name} is not an edge name in model {self.name}')
                if name in idx_names:
                    raise ValueError(f'Index Edge {name} is in multiple indexes in model {self.name}')
                idx_names.add(name)
        return self

    def __repr__(self):
        return self.name + \
            ''.join(repr(idx) for idx in self.indexes) + \
            "{" + ','.join(edge.name for edge in self.edges) + "}"

class Index(AST):
    edges: list[EDGE]

    def __str__(self):
        return f"({','.join(self.edges)})"

    def __repr__(self):
        return str(self)

class Edge(AST):
    name: EDGE
    typ: Optional[Type]
    cardinality: Optional[Literal['*','?','+','!']]

    @model_validator(mode='after')
    def set_children(self):
        if self.typ:
            self.children = [self.typ]
        return self

    def __repr__(self):
        return f"{self.name}:{self.typ or ''}{self.cardinality or ''}"

class TypeRef(AST):
    name: TYPE

    def __repr__(self):
        return self.name

class TypeAlias(AST):
    name: TYPE
    typ: Type

    @model_validator(mode='after')
    def set_children(self):
        self.children.append(self.typ)
        return self
    
    def __repr__(self):
        return f"{self.name}:{self.typ}"

class TypeIndex(AST):
    typ: TypeRef
    index: Index

    @model_validator(mode='after')
    def set_children(self):
        self.name = self.typ.name
        self.children = [self.typ, self.index]
        return self
    
    def __repr__(self):
        return f"{self.name}{repr(self.index)}"

Type = Union[TypeAlias, Model, TypeIndex, TypeRef]