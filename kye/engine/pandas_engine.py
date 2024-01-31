from __future__ import annotations
from typing import Any
import pandas as pd
from kye.compiler.models import Type, TYPE_REF, Models


def normalize_type(col: pd.Series, model: Type):
    errors = []
    # TODO: split delimited fields
    # TODO: replace empty strings with null and other defined null values
    col = col.explode().dropna()
    return col, errors

def validate_model(df: pd.DataFrame, model: Type):
    errors = []

    for col in df.columns:
        if not col in model.edges:
            errors.append({
                'error_type': 'ADDITIONAL_EDGE',
                'params': {
                    'edge': edge,
                }
            })

    for edge in model.edges:
        if edge not in df.columns:
            if not model.allows_null(edge):
                errors.append({
                    'error_type': 'MISSING_EDGE',
                    'params': {
                        'edge': edge,
                        'rows': df.index.tolist(),
                    }
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
                    'params': {
                        'edge': edge,
                        'rows': missing.tolist(),
                    },
                })
        
        if not model.allows_multiple(edge):
            multiple = col.index[col.index.duplicated()]
            if not multiple.empty:
                errors.append({
                    'error_type': 'MULTIPLE_EDGE',
                    'params': {
                        'edge': edge,
                        'rows': multiple.unique().tolist()
                    }
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