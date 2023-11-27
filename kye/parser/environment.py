from __future__ import annotations
import kye.parser.kye_ast as AST
from kye.parser.types import Type
from typing import Literal, Optional

def evaluate(ast: AST.AST, env: Environment) -> Type:
    pass

class Environment:
    """ Abstract class for Type Environments """
    local: dict[str, ChildEnvironment]
    
    def __init__(self):
        self.local = {}

    @property
    def path(self) -> tuple[str]:
        raise NotImplementedError('Abstract Environment does not define `.path`')
    
    @property
    def global_name(self) -> str:
        return '.'.join(self.path)

    def define(self, key: str, eval: type(evaluate), ast: Optional[AST.AST] = None):
        self.local[key] = ChildEnvironment(
            name=key,
            parent=self,
            evaluator=TypeEvaluator(
                eval=eval,
                env=self,
                ast=ast,
            )
        )
    
    def lookup(self, key: str) -> Optional[ChildEnvironment]:
        raise NotImplementedError('Abstract Environment does not define `lookup()`')

    def get_child(self, key) -> Optional[ChildEnvironment]:
        return self.local.get(key)
    
    def apply_ast(self, ast: AST.AST):
        env = self
        if isinstance(ast, AST.Definition):
            self.define(ast.name, eval=evaluate, ast=ast)
            env = env.get_child(ast.name)
        for child in ast.children:
            env.apply_ast(child)
        
    def __repr__(self):
        return self.global_name + '{' + ','.join(self.local.keys()) + '}'

class RootEnvironment(Environment):
    def __init__(self):
        super().__init__()

    @property
    def path(self) -> tuple[str]:
        return tuple()
    
    def lookup(self, key: str) -> Optional[ChildEnvironment]:
        return self.get_child(key)

class ChildEnvironment(Environment):
    name: str
    parent: Environment
    evaluator: TypeEvaluator

    def __init__(self, name: str, parent: Environment, evaluator: TypeEvaluator):
        super().__init__()
        self.name = name
        self.parent = parent
        self.evaluator = evaluator
    
    @property
    def path(self) -> tuple[str]:
        return (*self.parent.path, self.name)
    
    @property
    def type(self) -> Type:
        return self.evaluator.get_type()
    
    def lookup(self, key: str) -> Optional[ChildEnvironment]:
        if key == self.name:
            return self
        return self.get_child(key) or self.parent.lookup(key)

class TypeEvaluator:
    """
    Type Evaluator houses the evaluation function
    caching the resulting type and also making sure
    that it is not circularly referenced
    """
    eval: type(evaluate)
    env: Environment
    ast: Optional[AST.AST]
    status: Literal['new','processing','done']
    cached_type: Optional[Type]

    def __init__(self, eval: type(evaluate), env: Environment, ast: Optional[AST.AST]):
        self.eval = eval
        self.env = env
        self.ast = ast
        self.status = 'new'
        self.cached_type = None
    
    def get_type(self):
        if self.status == 'done':
            assert self.cached_type is not None
            return self.cached_type
        
        if self.status == 'processing':
            raise Exception('Already has been called, possible circular reference')
        
        if self.status == 'new':
            self.status = 'processing'
            self.cached_type = self.eval(self.ast, self.env)
            assert isinstance(self.cached_type, Type)
            self.status = 'done'
            return self.cached_type

        raise Exception(f'Unknown status "{self.status}"')