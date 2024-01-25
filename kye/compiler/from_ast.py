from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import kye.parser.kye_ast as AST
from enum import Enum
from contextlib import contextmanager

if TYPE_CHECKING:
    from kye.compiler.models import TYPE_REF, EDGE, Type, Models

class Status(Enum):
    INITIALIZED = 1
    PENDING = 2
    COMPLETE = 3

class Compiler:
    models: Models
    ast: dict[str, AST.Expression]
    status: dict[str, Status]
    
    def __init__(self, models: Models):
        self.models = models
        self.ast = {}
        self.status = {}

        for typ in self.models:
            self.status[typ.ref] = Status.COMPLETE
            for edge in typ.edges:
                self.status[typ.ref + '.' + edge] = Status.COMPLETE
    
    def get_models(self) -> Models:
        for ref, ast in self.ast.items():
            if isinstance(ast, AST.TypeDefinition):
                self.compile_type(ref)
        return self.models
    
    def read_definition(self, ast: AST.Definition):
        assert isinstance(ast, AST.Definition)
        ref = ast._ref if isinstance(ast, AST.EdgeDefinition) else ast.name
        assert ref is not None
        assert ref not in self.ast
        assert ref not in self.models
        self.ast[ref] = ast
        self.status[ref] = Status.INITIALIZED

        if isinstance(ast, AST.ContainedDefinitions):
            for child in ast.children:
                self.read_definition(child)
    
    def read_definitions(self, ast: AST.ModuleDefinitions) -> Compiler:
        for child in ast.children:
            self.read_definition(child)
        return self
    
    @contextmanager
    def _checkout(self, ref: str):
        """
        Using the 'status' property makes sure that there are no circular references
        (i.e. trying to use a reference during its own compilation)
        """
        if ref not in self.status:
            raise KeyError(f'Unknown symbol `{ref}`')

        # Already compiled
        if self.status[ref] == Status.PENDING:
            raise Exception(f'Possible circular reference for `{ref}`')
        
        self.status[ref] = Status.PENDING
        try:
            yield self.ast[ref]
        finally:
            self.status[ref] = Status.COMPLETE

    def compile_type(self, ref: TYPE_REF) -> Type:
        if ref in self.models:
            return self.models[ref]

        with self._checkout(ref) as ast:
            assert isinstance(ast, AST.TypeDefinition)
            typ = self.models.define(ref)

        if isinstance(ast, AST.AliasDefinition):
            typ.define_parent(self.compile_expression(ast.type, None))
        if isinstance(ast, AST.ModelDefinition):
            for edge in ast.edges:
                self.compile_edge(typ, edge.name)
            for idx in ast.indexes:
                typ.define_index(idx)
        return typ

    def compile_edge(self, model: Type, edge: EDGE):
        if model.has_edge(edge):
            return
        with self._checkout(model.ref + '.' + edge) as ast:
            assert isinstance(ast, AST.EdgeDefinition)
            model.define_edge(
                name=ast.name,
                type=self.compile_expression(ast.type, model),
                nullable=ast.cardinality in ('?','*'),
                multiple=ast.cardinality in ('+','*'),
            )
    
    def compile_expression(self, ast: AST.Expression, ctx_type: Optional[Type]) -> Type:
        assert isinstance(ast, AST.Expression)
        if isinstance(ast, AST.Identifier):
            if ast.kind == 'type':
                return self.compile_type(ast.name)
            # if ast.kind == 'edge':
            #     edge = self.lookup_edge(ctx_type, ast.name)
            #     return EdgeRefExpression(
            #         edge=edge,
            #         loc=ast.meta,
            #     )
        # elif isinstance(ast, AST.LiteralExpression):
        #     if type(ast.value) is str:
        #         ctx_type = self.get_type('String')
        #     elif type(ast.value) is bool:
        #         ctx_type = self.get_type('Boolean')
        #     elif isinstance(ast.value, (int, float)):
        #         ctx_type = self.get_type('Number')
        #     else:
        #         raise Exception()
        #     return LiteralExpression(type=ctx_type, value=ast.value, loc=ast.meta)
        # elif isinstance(ast, AST.Operation):
        #     assert len(ast.children) >= 1
        #     expr = self.compile_expression(ast.children[0], ctx_type)
        #     if ast.name == 'filter':
        #         assert len(ast.children) <= 2
        #         if len(ast.children) == 2:
        #             assert expr.is_type()
        #             filter = self.compile_expression(ast.children[1], expr.get_context())
        #             expr = CallExpression(
        #                 bound=expr,
        #                 args=[filter],
        #                 edge=self.get_edge('Type.$filter'),
        #                 loc=ast.meta,
        #             )
        #     elif ast.name == 'dot':
        #         assert len(ast.children) >= 2
        #         for child in ast.children[1:]:
        #             expr = self.compile_expression(child, expr.get_context())
        #     else:
        #         for child in ast.children[1:]:
        #             expr = CallExpression(
        #                 bound=expr,
        #                 args=[
        #                     self.compile_expression(child, ctx_type)
        #                 ],
        #                 edge=self.lookup_edge(expr.returns, '$' + ast.name),
        #                 loc=ast.meta,
        #             )
        #     return expr
        # else:
        raise Exception('Unknown Expression')

def models_from_ast(models: Models, ast: AST.ModuleDefinitions) -> Models:
    compiler = Compiler(models).read_definitions(ast)
    return compiler.get_models()