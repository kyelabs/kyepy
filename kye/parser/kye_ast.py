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
    type_ref: Optional[str] = None

    def __str__(self):
        return self.name or super().__str__()

    def traverse(self, path=tuple()):
        path = path + (self,)
        for child in self.children:
            yield path, child
            yield from child.traverse(path=path)
    
    def __repr__(self):
        end_line = f"-{self.meta.end_line}" if self.meta.end_line != self.meta.line else ''
        return f"{self.__class__.__name__}<{self.__repr_value__()}>:{self.meta.line}{end_line}"
    
    def __repr_value__(self):
        return ''

class Definitions(AST):
    children: list[Union[AliasDefinition, ModelDefinition]]

    @model_validator(mode='after')
    def validate_definitions(self):
        type_names = set()
        for child in self.children:
            # raise error if definition name is duplicated
            if child.name in type_names:
                raise ValueError(f'Model name {child.name} is duplicated in model {self.name}')
            type_names.add(child.name)
        return self
    
    def __repr_value__(self):
        return f"{','.join(child.name for child in self.children)}"

class Definition(AST):
    name: Union[TYPE, EDGE]

class TypeDefinition(Definition):
    name: TYPE

class AliasDefinition(TypeDefinition):
    typ: Expression

    @model_validator(mode='after')
    def set_children(self):
        self.children = [self.typ]
        return self
    
    def __repr_value__(self):
        return f"{self.name}:{self.typ}"

class ModelDefinition(TypeDefinition):
    indexes: list[list[EDGE]]
    edges: list[EdgeDefinition]
    subtypes: list[TypeDefinition]

    @model_validator(mode='after')
    def validate_indexes(self):
        self.children = self.edges + self.subtypes
        edge_names = set()
        for edge in self.edges:
            # raise error if edge name is duplicated
            if edge.name in edge_names:
                raise ValueError(f'Edge name {edge.name} is duplicated in model {self.name}')
            edge_names.add(edge.name)
        
        idx_names = set()
        for idx in self.indexes:
            for name in idx:
                # raise error if index name is not an edge name
                if name not in edge_names:
                    raise ValueError(f'Index {name} is not an edge name in model {self.name}')
                if name in idx_names:
                    raise ValueError(f'Index Edge {name} is in multiple indexes in model {self.name}')
                idx_names.add(name)
        return self

    def __repr_value__(self):
        def format_index(idx):
            return "(" + ','.join(idx) + ")"

        return self.name + \
            ''.join(format_index(idx) for idx in self.indexes) + \
            "{" + ','.join(edge.name for edge in self.children) + "}"

class EdgeDefinition(Definition):
    name: EDGE
    cardinality: Optional[Literal['*','?','+','!']]
    typ: Expression

    @model_validator(mode='after')
    def set_children(self):
        self.children = [self.typ]
        return self

    def __repr_value__(self):
        return f"{self.name}{self.cardinality or ''}"

class Expression(AST):
    pass

class Identifier(Expression):
    name: str

    def __repr_value__(self):
        return self.name

class LiteralExpression(Expression):
    value: Union[str, float, bool]

    def __repr_value__(self):
        return repr(self.value)

class Operation(Expression):
    _OP_NAMES = {
        '!': 'not', '~': 'invert',
        '!=': 'ne', '==': 'eq', 
        '>=': 'gte', '<=': 'lte', 
        '>': 'gt', '<': 'lt',
        '+': 'add', '-': 'sub',
        '*': 'mul', '/': 'div', '%': 'mod',
        '|': 'or', '&': 'and', '^': 'xor',
        '[]': 'filter', '.': 'dot',
    }

    op: Literal[
        '!','~',
        '!=','==','>=','<=','>','<',
        '+','-','*','/','%',
        '|','&','^',
        '[]','.'
    ]
    children: list[Expression]

    def __repr_value__(self):
        return self._OP_NAMES[self.op]