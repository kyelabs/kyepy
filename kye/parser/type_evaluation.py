from __future__ import annotations
from typing import Optional
from kye.parser.kye_ast import *
from kye.parser.types import *

class TypeEvaluation:
    name: str
    global_name: str
    env: Environment

    def __init__(self, env: Environment, name: str):
        self.name = name
        self.global_name = name
        env[self.name] = self
        self.env = Environment(parent=env)
    
    def set_global_name(self, path: Optional[str] = None):
        if path is not None:
            self.global_name = path + '.' + self.name
        else:
            self.global_name = self.name

    def get_external_references(self):
        return []
    
    def __repr__(self):
        return f'{self.global_name}{repr(self.env)}'
    
    def __eq__(self, other: TypeEvaluation):
        return self.global_name == other.global_name

class ContainerTypeEvaluation(TypeEvaluation):
    ast: ContainedDefinitions
    children: list[TypeEvaluation]

    def __init__(self, env: Environment, ast: ContainedDefinitions):
        super().__init__(env, name=ast.name)
        self.ast = ast
        self.children = [ get_type_evaluation(self.env, child) for child in ast.children ]
    
    def set_global_name(self, path: Optional[str] = None):
        super().set_global_name(path)
        for child in self.children:
            child.set_global_name(self.global_name)
    
    def get_external_references(self):
        for child in self.children:
            for ref in child.get_external_references():
                if ref not in self.env.local:
                    yield ref

class ExpressionTypeEvaluation(TypeEvaluation):
    ast: ExpressionDefinition
    expr: Expression

    def __init__(self, env: Environment, ast: ExpressionDefinition):
        super().__init__(env, name=ast.name)
        self.ast = ast
        self.expr = ast.type

    def get_external_references(self):
        for _, child in self.ast.traverse():
            if isinstance(child, Identifier):
                yield child.name

def get_type_evaluation(
        env: Environment,
        ast: Definition,
    ) -> TypeEvaluation:
    assert isinstance(ast, Definition), 'ast must be a Definition'

    if isinstance(ast, ContainedDefinitions):
        return ContainerTypeEvaluation(env, ast)
    elif isinstance(ast, ExpressionDefinition):
        return ExpressionTypeEvaluation(env, ast)
    else:
        raise RuntimeError(f'Cannot evaluate {ast}')

    # def get_unresolved_references(self):
    #     if self.expr is not None:
    #         for _, child in self.ast.traverse():
    #             if isinstance(child, Identifier) and self.env[child.name] is None:
    #                 yield child.name
    #     for child in self.children:
    #         yield from child.get_unresolved_references()
    
    # def evaluate(self):
    #     if self.ast is None:
    #         return Type(self.name)
    #     if isinstance(self.ast, ModuleDefinitions):
    #         self.evaluate_module()
    #     if isinstance(self.ast, ModelDefinition):
    #         self.evaluate_model()
    #     elif isinstance(self.ast, AliasDefinition):
    #         self.evaluate_expression(self.ast.type)
    #     else:
    #         raise RuntimeError(f'Cannot evaluate {self.ast}')
    
    # def evaluate_module(self):
    #     pass

    # def evaluate_model(self):
    #     pass

    # def evaluate_expression(self, ast: Expression):
    #     if isinstance(ast, Identifier):
    #         return self.env[ast.name].evaluate()

