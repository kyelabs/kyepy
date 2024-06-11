from __future__ import annotations
import typing as t
from dataclasses import dataclass
from functools import cached_property
import ibis
from ibis import _
import ibis.expr.datatypes as dtype
import ibis.expr.types as ir

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.type.types as typ
from kye.engine import Engine

@dataclass(frozen=True)
class DataType:
    name: str

@dataclass
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
    
    def __init__(self, types: typ.Types, engine: Engine, reporter: ErrorReporter):
        self.reporter = reporter
        self.engine = engine
        self.sources = {}
        self.tables = {}
    
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
    
    def load(self, source_name: str) -> ibis.Table:
        if source_name in self.tables:
            return self.tables[source_name]
        
        assert source_name in self.sources, f"Source '{source_name}' not found"
        source = self.sources[source_name]
        table = self.engine.get_table(source.name)

        for col_name in source.index:
            assert col_name in table.columns, f"Index column '{col_name}' not found in table"
            col = table[col_name]
            assert isinstance(col, ibis.Column), f"Column '{col_name}' must be an ibis column"
            self.matches_dtype(source[col_name], col.type())
    
        for col_name in table.columns:
            if col_name not in source.edges:
                print(f"Warning: Table '{source.name}' had extra column '{col_name}'")
                continue
            if col_name not in source.index:
                col = table[col_name]
                assert isinstance(col, ibis.Column), f"Column '{col_name}' must be an ibis column"
                self.matches_dtype(source[col_name], col.type())

        t = table.select(source.index)
        is_index_unique = (t.count() == t.nunique()).as_scalar().execute()
        assert is_index_unique, f"Index columns {source.index} must be unique"
        
        # if not is_index_unique:
        #     non_plural_columns = [
        #         edge for edge in columns
        #         if not source[edge].allows_many
        #     ]
        #     t = table.aggregate(
        #         by=source.index, # type:ignore 
        #         **{
        #             edge: _[edge].nunique() # type: ignore
        #             for edge in non_plural_columns
        #         }
        #     )
        #     table = table.select(source.index + non_plural_columns).distinct(on=source.index)
        #     print('hi')
        self.tables[source_name] = table
        
        return table
    
    
    def matches_dtype(self, edge: Edge, dtype: dtype.DataType):
        type = edge.type
        if edge.allows_many:
            assert dtype.is_array(), "Expected array"
            dtype = dtype.value_type # type: ignore
        assert not dtype.is_nested(), "Unexpected nesting"
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