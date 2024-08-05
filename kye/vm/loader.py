from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path
import itertools

import pandas as pd

from kye.errors.validation_errors import ValidationErrorReporter
from kye.vm.op import OP, parse_command
import kye.compiled as compiled
from kye.vm.vm import VM

Expr = t.List[tuple[OP, list]]

def hash_columns(df: pd.DataFrame) -> pd.Series:
    if len(df.columns) == 1:
        return df.iloc[:, 0]
    return df.apply(tuple, axis=1)

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
            df.drop(df[~mask].index, inplace=True)
            if df.empty:
                return None
        
        # Check that sub-indexes are unique to each other
        if len(source.indexes) > 1:
            mask = pd.Series(True, index=df.index)
            idx = hash_columns(df[source.index])
            for sub_idx_edges in source.indexes:
                sub_idx = hash_columns(df[sub_idx_edges])
                invalid = idx.groupby(sub_idx).nunique() != 1
                if invalid.any():
                    invalid_rows = pd.Series(df.index, index=sub_idx)[invalid]
                    mask.loc[invalid_rows] = False # type: ignore
                    self.reporter.non_unique_sub_index(source, sub_idx_edges, invalid_rows.tolist())
            if not mask.all():
                df.drop(df[~mask].index, inplace=True)
                if df.empty:
                    return None
                

        # Run cardinality assertions and groupby the index
        idx = hash_columns(df[source.index]).rename(source.name)
        reversed_idx = pd.Series(df.index, index=idx)
        grouped_df = pd.DataFrame(index=idx.drop_duplicates())
        df.set_index(idx, inplace=True)
        mask = pd.Series(True, index=grouped_df.index)
        for col_name in df.columns:
            col = df[col_name]
            edge = source[col_name]
            g = col.explode().dropna().groupby(level=0)
            if not edge.many or not edge.null:
                nunique = g.nunique().reindex(grouped_df.index, fill_value=0)
                if not edge.many:
                    has_many = nunique > 1
                    if has_many.any():
                        mask &= ~has_many
                        self.reporter.multiple_values(source[col_name], reversed_idx.loc[has_many].tolist())
                if not edge.null:
                    is_null = nunique == 0
                    if is_null.any():
                        mask &= ~is_null
                        self.reporter.missing_values(source[col_name], reversed_idx.loc[is_null].tolist())
            grouped_df[col_name] = g.agg('unique' if edge.many else 'first')
        df = grouped_df
        if not mask.all():
            df.drop(df[~mask].index, inplace=True)
            if df.empty:
                return None
        
        # Check for index conflicts
        if len(source.indexes) > 1:
            mask = pd.Series(True, index=df.index)
            for idx1_id, idx2_id in itertools.combinations(range(len(source.indexes)), 2):
                idx1 = source.indexes[idx1_id]
                idx2 = source.indexes[idx2_id]
                # TODO: Check if compatible index types
                if len(idx1) != len(idx2):
                    continue

                t = pd.concat([
                    hash_columns(df[idx1]),
                    hash_columns(df[idx2]),
                ])
                t = pd.Series(t.index, index=t) # flip index/value
                invalid = t[t.groupby(level=0).nunique() > 1]
                if not invalid.empty:
                    mask.loc[invalid] = False
                    invalid_rows = reversed_idx.loc[invalid].tolist()
                    self.reporter.index_conflict(source, list(set(idx1) | set(idx2)), invalid_rows)
            if not mask.all():
                df.drop(df[~mask].index, inplace=True)
                if df.empty:
                    return None
        
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