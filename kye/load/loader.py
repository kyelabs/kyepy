from __future__ import annotations
import typing as t
from dataclasses import dataclass
from functools import cached_property
import ibis
import ibis.expr.datatypes as dtype
import ibis.expr.types as ir

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.type.types as typ
from kye.engine import Engine

@dataclass(frozen=True)
class DataType:
    name: str

@dataclass(frozen=True)
class Edge:
    name: str
    allows_null: bool
    allows_many: bool
    type: DataType
    
    def combine(self, other: Edge):
        assert self.name == other.name, "Edges must have the same name"
        assert self.type == other.type, "Edges must have the same type"
        return Edge(
            name=self.name,
            allows_null=self.allows_null or other.allows_null,
            allows_many=self.allows_many or other.allows_many,
            type=self.type,
        )

class Source:
    name: str
    index: t.List[str]
    edges: t.Dict[str, Edge]
    
    def __init__(self, name: str, index: t.List[str]):
        self.name = name
        self.index = index
        self.edges = {}
    
    @cached_property
    def non_index_edges(self):
        return [edge for edge in self.edges if edge not in self.index]
    
    def define(self, edge: Edge):
        existing = self.edges.get(edge.name)
        if existing:
            edge = existing.combine(edge)
        self.edges[edge.name] = edge
    
    def __getitem__(self, key: str) -> Edge:
        return self.edges[key]

class Loader:
    engine: Engine
    reporter: ErrorReporter
    sources: t.Dict[str, Source]
    tables: t.Dict[str, ibis.Table]
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.sources = {}
        self.tables = {}
    
    def load(self, types: typ.Types):
        for model in types.values():
            if not isinstance(model, typ.Model):
                continue
            if model.source not in self.sources:
                self.sources[model.source] = Source(
                    model.source,
                    model.indexes.edges
                )
            source = self.sources[model.source]
            for edge in model.edges.values():
                source.define(Edge(
                    name=edge.name,
                    allows_null=edge.allows_null,
                    allows_many=edge.allows_many,
                    type=DataType(edge.output.name),
                ))
        for source in self.sources.values():
            self.load_source(source)
    
    def load_source(self, source: Source):
        index_edges = []
        table = self.engine.get_table(source.name)
        for edge in source.index:
            assert edge in table.columns, f"Index column '{edge}' not found in table"
            col = table[edge]
            assert isinstance(col, ibis.Column), f"Column '{edge}' must be an ibis column"
            index_edge = self.load_edge(source[edge], col)
            index_edges.append(index_edge)
        
        edges = {}
        for column in table.columns:
            if column in source.non_index_edges:
                col = table[column]
                assert isinstance(col, ibis.Column), f"Column '{column}' must be an ibis column"
                edges[column] = self.load_edge(source[column], col)
    
    def load_edge(self, edge: Edge, column: ibis.Value) -> ibis.Value:
        if isinstance(column, ir.ArrayValue):
            column = column.unnest()
        assert not column.type().is_nested(), "Unhandled nesting"
        self.matches_dtype(edge.type, column.type())
        return column
    
    def matches_dtype(self, type: DataType, dtype: dtype.DataType):
        if type.name == 'String':
            assert dtype.is_string(), "Expected string"
        elif type.name == 'Number':
            assert dtype.is_numeric(), "Expected numeric"
        elif type.name == 'Integer':
            assert dtype.is_integer(), "Expected integer"
        elif type.name == 'Boolean':
            assert dtype.is_boolean(), "Expected boolean"
        else:
            raise Exception(f"Unknown type {type.name}")