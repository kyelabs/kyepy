from __future__ import annotations
import typing as t
from enum import Enum, auto

import expressions as exp

E = t.TypeVar('E')

EXPRESSION_TO_SCOPE = {
    # exp.Module: Root,
    # exp.Model: Model,
    # exp.Edge: Edge,
    # exp.Query: Query,
    # exp.Composite: Composite,
}

class Scope:
    _expression_type: t.Type[exp.Expression] = None

    # Root expression of this scope
    expression: exp.Expression
    # Mapping of source name to expression
    sources: dict[str, t.Union[Scope, exp.Expression]]
    # Parent scope
    parent: t.Optional[Scope]
    # List of child scopes
    scopes: list[Scope]

    def __init__(
        self,
        expression: exp.Expression,
        sources: dict[str, t.Union[Scope, exp.Expression]]={},
        parent: t.Optional[Scope]=None,
    ):
        assert isinstance(expression, self._expression_type)
        self.expression = expression
        self.sources = sources
        self.parent = parent
        self.scopes = []
        self.clear_cache()
    
    def __init_subclass__(cls) -> None:
        assert cls._expression_type is not None
        EXPRESSION_TO_SCOPE[cls._expression_type] = cls
    
    def clear_cache(self):
        self._collected = False
        self._models = None
        self._edges = None
    
    def branch(self, expression: exp.Expression, sources={}):
        """Branch from the current scope to a new, inner scope"""
        assert expression.__class__ in EXPRESSION_TO_SCOPE
        return EXPRESSION_TO_SCOPE[expression.__class__](
            expression=expression,
            sources=sources,
            parent=self,
        )

    def _collect(self):
        if self._collected:
            return
        self._collected = True
        self._models = []
        self._edges = []

        for node in self.walk(bfs=False):
            if node is self.expression:
                continue
            if isinstance(node, exp.TypeDefinition):
                self._models.append(node)
            if isinstance(node, exp.Edge):
                self._edges.append(node)

    def walk(self, bfs=True):
        def prune(node: exp.Expression):
            # Logical operators create a new type, and therefore a new scope
            if isinstance(node, (exp.Definition, exp.Composite, exp.Filter)):
                return True
            return False

        return self.expression.walk(bfs=bfs, prune=prune)

    def findall(self, *types: t.Type[E], bfs=True) -> t.Iterator[E]:
        for exp in self.walk(bfs=bfs):
            if isinstance(exp, types):
                yield exp
    
    def find(self, *types: t.Type[E], bfs=True) -> t.Optional[E]:
        return next(self.findall(*types, bfs=bfs), None)

    def replace(self, old: exp.Expression, new: exp.Expression):
        old.replace(new)
        self.clear_cache()
    
    @property
    def models(self):
        self._collect()
        return self._models
    
    @property
    def edges(self):
        self._collect()
        return self._edges
    
class Root(Scope):
    _expression_type = exp.Module

class Model(Scope):
    _expression_type = exp.Model

class Edge(Scope):
    _expression_type = exp.Edge

class Query(Scope):
    _expression_type = exp.Query

class Composite(Scope):
    _expression_type = exp.Composite