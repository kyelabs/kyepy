from __future__ import annotations
import typing as t
import ibis

from kye.errors import ErrorReporter, KyeRuntimeError
import kye.type.types as typ

class Loader:
    reporter: ErrorReporter
    types: typ.Types
    tables: t.Dict[str, ibis.Table]
    
    def __init__(self, reporter: ErrorReporter, types: typ.Types):
        self.types = types
        self.reporter = reporter
    
    def load(self, name: str, table: ibis.Value):
        assert isinstance(table, ibis.Table), "Table must be an ibis table"
        assert name in self.types, f"Type '{name}' not found"
        model = self.types[name]
        assert isinstance(model, typ.Model), f"Type '{name}' is not a model"
        self.load_model(model, table)
    
    def load_model(self, model: typ.Model, table: ibis.Table):
        index_edges = []
        for edge in sorted(model.indexes.edges):
            if edge not in table.columns:
                raise KyeRuntimeError(model.indexes.tokens[edge][0], f"Index column '{edge}' not found in table")
            col = table[edge]
            assert isinstance(col, ibis.Column), f"Column '{edge}' must be an ibis column"
            index_edge = self.load_index_edge(model.edges[edge], col)
            index_edges.append(index_edge)
        
        edges = {}
        for column in table.columns:
            if column in model.edges and column not in model.indexes.edges:
                col = table[column]
                assert isinstance(col, ibis.Column), f"Column '{column}' must be an ibis column"
                edges[column] = self.load_edge(model.edges[column], col)
    
    def load_index_edge(self, edge: typ.Edge, column: ibis.Column) -> ibis.Column:
        self.matches_dtype(edge.output, column)
        return column
    
    def load_edge(self, edge: typ.Edge, column: ibis.Column) -> ibis.Column:
        self.matches_dtype(edge.output, column)
        return column
    
    def matches_dtype(self, type: typ.Type, value: ibis.Column):
        pass