from __future__ import annotations
from typing import Any
import pandas as pd
from kye.compiler.models import Type, TYPE_REF, Models
import kye.engine.formats as Formats
import itertools

def as_string(col: pd.Series):
    return col.astype(str, errors='ignore')

def as_boolean(col: pd.Series):
    return col.astype(bool, errors='ignore')

FORMATS = {
    'number': Formats.as_number,
    'string': as_string,
    'boolean': as_boolean,
}

def normalize_type(col: pd.Series, model: Type):
    errors = []
    # TODO: split delimited fields
    # TODO: replace empty strings with null and other defined null values
    # TODO: raise strict mode error for single element lists
    col = col.explode().dropna()

    # TODO: iterate through assertions by recursing on parent types

    for assertion in model.assertions:
        if assertion.op == 'type':
            assert assertion.arg in FORMATS
            formatted = FORMATS[assertion.arg](col, model.format or '')
            invalid = col[formatted.isna()]
            if not invalid.empty:
                errors.append({
                    'error_type': 'INVALID_VALUE_FORMAT',
                    'type': model.ref,
                    'rows': invalid.index.tolist(),
                    'values': invalid.tolist(),
                })
            col = formatted
                

    return col, errors

def validate_model(df: pd.DataFrame, model: Type):
    assert df.index.is_unique
    errors = []

    # TODO: recurse on parent models

    for col in df.columns:
        if not col in model.edges:
            defined = df.index[df[col].notnull()]
            errors.append({
                'error_type': 'EXTRA_EDGE',
                'edge': col,
                'rows': defined.tolist(),
            })

    # TODO: rebuild table from validated edges so that the index analysis
    # knows which edges are valid and that it can work with
    for edge in model.edges:
        if edge not in df.columns:
            if not model.allows_null(edge):
                errors.append({
                    'error_type': 'MISSING_EDGE',
                    'edge': edge,
                    'rows': df.index.tolist(),
                })
            continue

        # Normalize value format
        col, edge_errors = normalize_type(df[edge], model.get_edge(edge))
        
        # Skip cardinality check if there are value errors
        # because a value error could make a cardinality error irrelevant
        if len(edge_errors):
            errors += edge_errors
            continue

        if not model.allows_null(edge):
            missing = df.index.difference(col.index)
            if not missing.empty:
                errors.append({
                    'error_type': 'MISSING_EDGE',
                    'edge': edge,
                    'rows': missing.tolist(),
                })
        
        if not model.allows_multiple(edge):
            multiple = col.index[col.index.duplicated()]
            if not multiple.empty:
                errors.append({
                    'error_type': 'MULTIPLE_EDGE',
                    'edge': edge,
                    'rows': multiple.unique().tolist(),
                })
    
    indexes = []
    for idx in model.indexes:
        # Skip if missing some of the edges in this index
        if not all(edge in df.columns for edge in idx):
            continue
        non_unique = df.loc[df.duplicated(subset=idx, keep=False), idx]
        if not non_unique.empty:
            errors.append({
                'error_type': 'NON_UNIQUE_INDEX',
                'index': idx,
                'rows': non_unique.index.tolist(),
                'values': non_unique.drop_duplicates().values.tolist(),
            })
            continue
        
        indexes.append(df[list(idx)])
    
    for idx1, idx2 in itertools.combinations(indexes, 2):
        # Only do comparison if comparing indexes of the same dtype
        if tuple(idx1.dtypes.tolist()) != tuple(idx2.dtypes.tolist()):
            continue

        column_names = list(range(len(idx1.columns)))
        idx_table = pd.concat([
            idx1.set_axis(column_names, axis=1),
            idx2.set_axis(column_names, axis=1),
        ])
        # Drop rows whose conflicting index describes the same row
        idx_table = idx_table.reset_index().drop_duplicates().set_index('index')
        # Filter down to rows that have the same index
        idx_table = idx_table[idx_table.duplicated(keep=False)]

        if not idx_table.empty:
            errors.append({
                'error_type': 'AMBIGUOUS_INDEX',
                'indexes': [
                    list(idx1.columns),
                    list(idx2.columns),
                ],
                'rows': idx_table.index.drop_duplicates().tolist(),
                'values': idx_table.drop_duplicates().values.tolist(),
            })

    return errors

class PandasEngine:
    models: Models

    def __init__(self, models: Models):
        assert isinstance(models, Models)
        self.models = models
    
    def validate(self, model: TYPE_REF, data: pd.DataFrame):
        assert model in self.models
        assert isinstance(data, pd.DataFrame)
        return validate_model(data, self.models[model])