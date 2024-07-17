from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kye.errors import ErrorReporter
from kye.vm.op import OP, parse_command
import kye.compiled as compiled
from kye.vm.vm import VM

Expr = t.List[tuple[OP, list]]

class Loader:
    reporter: ErrorReporter
    tables: t.Dict[str, pd.DataFrame]
    sources: compiled.Compiled
    
    def __init__(self, compiled: compiled.Compiled, reporter: ErrorReporter):
        self.reporter = reporter
        self.tables = {}
        self.sources = compiled
    
    def load(self, source_name: str, table: pd.DataFrame) -> pd.DataFrame:
        if source_name in self.tables:
            raise NotImplementedError(f"Table '{source_name}' already loaded. Multiple sources for table not yet supported.")

        # Check if table exists
        assert source_name in self.sources, f"Source '{source_name}' not found"
        source = self.sources[source_name]

        # Check that the table has all the required columns
        for col_name in source.index:
            assert col_name in table.columns, f"Index column '{col_name}' not found in table"
    
        # Check the type of each column
        for col_name in table.columns:
            if col_name not in source.edges:
                print(f"Warning: Table '{source.name}' had extra column '{col_name}'")
                continue
            col = table[col_name]
            self.matches_dtype(source[col_name], col)

        # Run the single-column assertions
        vm = VM(table)
        mask = pd.Series(True, index=table.index)
        for assertion in source.assertions:
            if len(assertion.edges) == 1:
                result = vm.eval(assertion.expr)
                if not result.all():
                    mask &= result
                    self.reporter.assertion_error(assertion, result[~result].index.tolist())
        if not mask.all():
            print(f'dropping {table.shape[0] - mask.sum()} rows')
            table = table[mask]

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
        
        return table
    
    def get_source(self, source: str):
        return self.sources[source]
    
    def matches_dtype(self, edge: compiled.Edge, col: pd.Series):
        if edge.many:
            col = col.explode().dropna().infer_objects()
        if edge.type == 'String':
            if col.dtype != 'object':
                self.reporter.column_type_error(edge, 'String')
        elif edge.type == 'Number':
            if not pd.api.types.is_numeric_dtype(col.dtype):
                self.reporter.column_type_error(edge, 'Number')
        elif edge.type == 'Integer':
            if not pd.api.types.is_numeric_dtype(col.dtype):
                self.reporter.column_type_error(edge, 'Integer')
        elif edge.type == 'Boolean':
            if not pd.api.types.is_bool_dtype(col.dtype):
                self.reporter.column_type_error(edge, 'Boolean')
        else:
            raise Exception(f"Unknown type {edge.type}")
    
    def run_assertion(self, vm: VM, assertion: compiled.Assertion):
        result = vm.eval(assertion.expr)
        if not result.all():
            self.reporter.assertion_error(assertion, vm.df[~result].index.tolist())
            # self.reporter.assertion_error(assertion, table)