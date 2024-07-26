from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kye.errors.validation_errors import ValidationErrorReporter
from kye.vm.op import OP, parse_command
import kye.compiled as compiled
from kye.vm.vm import VM

Expr = t.List[tuple[OP, list]]

class Loader:
    reporter: ValidationErrorReporter
    tables: t.Dict[str, pd.DataFrame]
    sources: compiled.Compiled
    
    def __init__(self, compiled: compiled.Compiled, reporter: ValidationErrorReporter):
        self.reporter = reporter
        self.tables = {}
        self.sources = compiled
    
    def load(self, source_name: str, df: pd.DataFrame):
        if source_name in self.tables:
            raise NotImplementedError(f"Table '{source_name}' already loaded. Multiple sources for table not yet supported.")
        
        # Check the table's index
        if not isinstance(df.index, pd.RangeIndex):
            assert None not in df.index.names, "Table should have a range index or a named index"
            df.reset_index(inplace=True)
        assert df.index.is_unique, "Table index must be unique at this point"
        df.index.name = source_name

        # Check if is a known model
        assert source_name in self.sources, f"Source '{source_name}' not found"
        source = self.sources[source_name]
        
        # Conform the table columns to our model edges
        #   - rename columns that use titles
        #   - drop any extra columns
        col_name_map = {
            edge.title or edge.name: edge.name
            for edge in source.edges.values()
        }
        rename_map = {}
        drop_columns = []
        for col_name in df.columns:
            if col_name not in col_name_map:
                drop_columns.append(col_name)
            elif col_name != col_name_map[col_name]:
                rename_map[col_name] = col_name_map[col_name]
        if len(drop_columns):
            print(f"Warning: Table '{source.name}' had extra columns: {','.join(drop_columns)}")
            df.drop(columns=drop_columns, inplace=True)
            if df.empty:
                return None
        if len(rename_map):
            df.rename(columns=rename_map, inplace=True)
        
        self.reporter.use_source(df.copy())

        # Check that the table has all the required columns
        is_missing_index_column = False
        for col_name in source.index:
            if col_name not in df.columns:
                is_missing_index_column = True
                self.reporter.missing_index(source[col_name])
        if is_missing_index_column:
            return None

        # Run cardinality assertions
        mask = pd.Series(True, index=df.index)
        for col_name in df.columns:
            col = df[col_name]
            edge = source[col_name]
            g = col.explode().dropna().groupby(level=0)
            if not edge.many or not edge.null:
                cnts = g.nunique().reindex(col.index, fill_value=0)
                if not edge.many:
                    has_many = cnts > 1
                    if has_many.any():
                        mask &= ~has_many
                        self.reporter.multiple_values(source[col_name], has_many[has_many].index.tolist())
                if not edge.null:
                    is_null = cnts == 0
                    if is_null.any():
                        mask &= ~is_null
                        self.reporter.missing_values(source[col_name], is_null[is_null].index.tolist())
            df[col_name] = g.agg('unique' if edge.many else 'first').reindex(col.index)
        if not mask.all():
            # print(f'dropping {df.shape[0] - mask.sum()} rows')
            df = df[mask]
            if df.empty:
                return None

        # Check the type of each column
        drop_columns = []
        for col_name in df.columns:
            col = df[col_name]
            if not self.matches_dtype(source[col_name], col):
                if col_name in source.index:
                    is_missing_index_column = True
                drop_columns.append(col_name)
                self.reporter.wrong_type(source[col_name])
        if is_missing_index_column:
            return None
        if len(drop_columns):
            df.drop(columns=drop_columns, inplace=True)
            if df.empty:
                return None

        # Run the single-column assertions
        vm = VM(df)
        mask = pd.Series(True, index=df.index)
        for assertion in source.assertions:
            if len(assertion.edges) == 1 and assertion.edges[0] in df.columns:
                result = vm.eval(assertion.expr)
                if not result.all():
                    mask &= result
                    self.reporter.assertion_failed(assertion, result[~result].index.tolist())
        if not mask.all():
            # print(f'dropping {df.shape[0] - mask.sum()} rows')
            df = df[mask]
            if df.empty:
                return None

        has_duplicate_index = df[df.duplicated(subset=source.index, keep=False)]
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
        self.tables[source_name] = df
    
    def get_source(self, source: str):
        return self.sources[source]
    
    def matches_dtype(self, edge: compiled.Edge, col: pd.Series) -> bool:
        col = col.explode().dropna().infer_objects()
        if edge.type == 'String':
            return col.dtype == 'object'
        elif edge.type == 'Number':
            return pd.api.types.is_numeric_dtype(col.dtype)
        elif edge.type == 'Integer':
            return pd.api.types.is_numeric_dtype(col.dtype)
        elif edge.type == 'Boolean':
            return pd.api.types.is_bool_dtype(col.dtype)
        else:
            raise Exception(f"Unknown type {edge.type}")