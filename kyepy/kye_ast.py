from __future__ import annotations
from pydantic import BaseModel, model_validator, constr
from typing import Optional, Literal, Union
from lark import tree

TAB = '    '

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')

class TokenPosition(BaseModel):
    line: int
    column: int
    end_line: int
    end_column: int
    start_pos: int
    end_pos: int

    @model_validator(mode='before')
    @classmethod
    def from_meta(cls, meta):
        if isinstance(meta, tree.Meta):
            return {
                'line': meta.line,
                'column': meta.column,
                'end_line': meta.end_line,
                'end_column': meta.end_column,
                'start_pos': meta.start_pos,
                'end_pos': meta.end_pos,
            }
        return meta
    
    def __repr__(self):
        end_line = f"{self.end_line}:" if self.end_line != self.line else ''
        return f"{self.line}:{self.column}-{end_line}{self.end_column}"

class AST(BaseModel):
    name: Optional[str] = None
    children: list[AST] = []
    meta: TokenPosition
    scope: Optional[dict] = None

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
    index: Optional[Index] = None

    @model_validator(mode='after')
    def set_children(self):
        if self.index:
            self.children = [self.index]
        return self

    def __repr__(self):
        return self.name + \
            (repr(self.index) if self.index else '')

class TypeAlias(AST):
    name: TYPE
    typ: Type

    @model_validator(mode='after')
    def set_children(self):
        self.children = [self.typ]
        return self
    
    def __repr__(self):
        return f"{self.name}:{self.typ}"

Type = Union[TypeAlias, Model, TypeRef]