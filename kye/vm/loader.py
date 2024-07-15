from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kye.errors import ErrorReporter
from kye.vm.op import OP, parse_command
import kye.compiled as compiled

Expr = t.List[tuple[OP, list]]

class Loader:
    reporter: ErrorReporter
    tables: t.Dict[str, pd.DataFrame]
    sources: compiled.Compiled
    current_src: t.Optional[str]
    
    def __init__(self, compiled: compiled.Compiled, reporter: ErrorReporter):
        self.reporter = reporter
        self.current_src = None
        self.tables = {}
        self.sources = compiled
    
    def read(self, source_name: str, filepath: str) -> pd.DataFrame:
        file = Path(filepath)
        if file.suffix == '.csv':
            table = pd.read_csv(file)
        elif file.suffix == '.json':
            table = pd.read_json(file)
        elif file.suffix == '.jsonl':
            table = pd.read_json(file, lines=True)
        else:
            raise ValueError(f"Unknown file type {file.suffix}")
        return self.load(source_name, table)
    
    def load(self, source_name: str, table: pd.DataFrame) -> pd.DataFrame:
        if source_name in self.tables:
            raise NotImplementedError(f"Table '{source_name}' already loaded. Multiple sources for table not yet supported.")

        assert source_name in self.sources, f"Source '{source_name}' not found"
        self.current_src = source_name
        source = self.sources[source_name]

        for col_name in source.index:
            assert col_name in table.columns, f"Index column '{col_name}' not found in table"
            col = table[col_name]
            self.matches_dtype(source[col_name], col)
    
        for col_name in table.columns:
            if col_name not in source.edges:
                print(f"Warning: Table '{source.name}' had extra column '{col_name}'")
                continue
            if col_name not in source.index:
                col = table[col_name]
                self.matches_dtype(source[col_name], col)

        has_duplicate_index = table[table.duplicated(subset=source.index, keep=False)]
        if not has_duplicate_index.empty:
            raise Exception(f"Index columns {source.index} must be unique")
        
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
        self.current_src = None
        
        return table
    
    def get_source(self, source: str):
        return self.sources[source]
    
    def matches_dtype(self, edge: compiled.Edge, col: pd.Series):
        assert self.current_src is not None
        if edge.many:
            col = col.explode().dropna().infer_objects()
        if edge.type == 'String':
            if col.dtype != 'object':
                self.report_edge_error(edge, f"Expected string")
        elif edge.type == 'Number':
            if not pd.api.types.is_numeric_dtype(col.dtype):
                self.report_edge_error(edge, f"Expected number")
        elif edge.type == 'Integer':
            if not pd.api.types.is_numeric_dtype(col.dtype):
                self.report_edge_error(edge, f"Expected integer")
        elif edge.type == 'Boolean':
            if not pd.api.types.is_bool_dtype(col.dtype):
                self.report_edge_error(edge, f"Expected boolean")
        else:
            raise Exception(f"Unknown type {edge.type}")
    
    def report_edge_error(self, edge: compiled.Edge, message: str):
        assert self.current_src is not None
        self.reporter.loading_edge_error(edge.loc, self.current_src, edge.name, message)