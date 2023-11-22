from __future__ import annotations
from pydantic import BaseModel, model_validator, constr
from typing import Optional, Literal, Union, Any
from kye.parser.environment import ChildEnvironment
from kye.parser.types import Type

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')

class TokenPosition(BaseModel):
    line: int
    column: int
    end_line: int
    end_column: int
    start_pos: int
    end_pos: int
    text: str
    
    def __repr__(self):
        end_line = f"{self.end_line}:" if self.end_line != self.line else ''
        return f"{self.line}:{self.column}-{end_line}{self.end_column}"

class AST(BaseModel):
    children: list[AST] = []
    meta: TokenPosition
    _env: Optional[ChildEnvironment] = None

    def __str__(self):
        return self.name or super().__str__()
    
    def set_env(self, env: ChildEnvironment):
        if isinstance(self, Definition):
            env = ChildEnvironment(self.name, parent=env)
        for child in self.children:
            child.set_env(env)
        setattr(self, '_env', env)
    
    def type_check(self):
        if isinstance(self, Identifier):
            assert self.name in self._env
            return self._env[self.name]
        if isinstance(self, LiteralExpression):
            if type(self.value) is str:
                return self._env['String']
            elif isinstance(self.value, (int, float)):
                return self._env['Number']
            elif type(self.value) is bool:
                return self._env['Boolean']
            else:
                raise Exception(f'Unexpected literal of type "{self.value.__class__.__name__}" "{self.value}"')
        if isinstance(self, Operation):
            # TODO: Get better sleep, so that I stop banging my head against a wall.
            pass

        for child in self.children:
            child.type_check()

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

class Definition(AST):
    """ Abstract class for all AST nodes that define a name """
    name: Union[TYPE, EDGE]

class TypeDefinition(Definition):
    """ Abstract class for all AST nodes that define a type """
    name: TYPE

class ExpressionDefinition(Definition):
    """ Abstract class for all AST nodes who's type is an expression """
    type: Expression

class ContainedDefinitions(AST):
    """ Abstract class for all AST nodes that have child definitions """
    children: list[Definition]

class ModuleDefinitions(ContainedDefinitions):
    children: list[TypeDefinition]

    @model_validator(mode='after')
    def validate_definitions(self):
        type_names = set()
        for child in self.children:
            # raise error if definition name is duplicated
            if child.name in type_names:
                raise ValueError(f'Type name {child.name} is duplicated in model {self.name}')
            type_names.add(child.name)
        return self
    
    def __repr_value__(self):
        return f"{','.join(child.name for child in self.children)}"

class AliasDefinition(TypeDefinition, ExpressionDefinition):

    @model_validator(mode='after')
    def set_children(self):
        self.children = [self.type]
        return self
    
    def __repr_value__(self):
        return f"{self.name}:{self.type}"

class ModelDefinition(TypeDefinition, ContainedDefinitions):
    indexes: list[list[EDGE]]
    subtypes: list[TypeDefinition]
    edges: list[EdgeDefinition]

    @model_validator(mode='after')
    def validate_indexes(self):
        self.children = self.subtypes + self.edges

        subtype_names = set()
        for subtype in self.subtypes:
            # raise error if subtype name is duplicated
            if subtype.name in subtype_names:
                raise ValueError(f'Subtype {subtype.name} is duplicated in model {self.name}')
            subtype_names.add(subtype.name)

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

class EdgeDefinition(ExpressionDefinition):
    name: EDGE
    cardinality: Optional[Literal['*','?','+','!']]

    @model_validator(mode='after')
    def set_children(self):
        self.children = [self.type]
        return self

    def __repr_value__(self):
        return f"{self.name}{self.cardinality or ''}"

class Expression(AST):
    """ Abstract class for all AST nodes that are expressions """
    pass

class Identifier(Expression):
    name: str

    @property
    def kind(self):
        assert len(self.name) > 0
        assert self.name[0].isalpha()
        return 'TYPE' if self.name[0].isupper() else 'EDGE'

    def evaluate(self):
        assert self.name in self._env
        return Type(extends=self._env[self.name].global_name)

    def __repr_value__(self):
        return self.name

class LiteralExpression(Expression):
    value: Union[str, float, bool]

    def evaluate(self):
        if type(self.value) is str:
            return Type(extends='String', filters={'eq': self.value})

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