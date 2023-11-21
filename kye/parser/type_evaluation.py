from __future__ import annotations
from typing import Optional
from kye.parser.kye_ast import *
from kye.parser.types import *

class TypeEvaluation:
    name: str
    type: Type
    env: Environment

    def __init__(self, env: Environment, name: str):
        self.name = name
        self.env = Environment(name=name, parent=env)

    @property
    def type(self):
        return self.env.parent.local.get(self.name)

    def evaluate(self):
        """ Evaluate Type Expressions to generate a type """
        raise NotImplementedError()
    
    def __repr__(self):
        return repr(self.env)

class ContainerTypeEvaluation(TypeEvaluation):
    ast: ContainedDefinitions
    children: list[TypeEvaluation]

    def __init__(self, env: Environment, ast: ContainedDefinitions):
        super().__init__(env, name=ast.name)
        self.ast = ast
        self.children = [ get_type_evaluation(self.env, child) for child in ast.children ]
        self.env.parent.define_type(
            name=self.name,
            indexes=self.ast.indexes if isinstance(self.ast, ModelDefinition) else [],
            edges={
                child.name: self.env[child.name]
                for child in self.children
            }
        )
        self.env.freeze()
    
    def evaluate(self):
        for child in self.children:
            child.evaluate()

def evaluate_type(ast: Expression, env: Environment) -> Type:
    if isinstance(ast, Identifier):
        if ast.name not in env:
            raise KeyError(f'Unknown reference to "{ast.name}" ({repr(ast.meta)})')
        else:
            typ = env[ast.name]
            if typ is None:
                return Type(extends='.'.join(env.get_path(ast.name)))
            else:
                return typ
    

class ExpressionTypeEvaluation(TypeEvaluation):
    ast: ExpressionDefinition
    expr: Expression

    def __init__(self, env: Environment, ast: ExpressionDefinition):
        super().__init__(env, name=ast.name)
        self.ast = ast
        self.expr = ast.type
        self.env.parent.define(self.name)        
    
    def evaluate(self):
        evaluate_type(self.expr, self.env)

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

