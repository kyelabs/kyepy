from __future__ import annotations
import typing as t
from dataclasses import dataclass, asdict

import pandas as pd

from kye.errors.base_reporter import ErrorReporter

if t.TYPE_CHECKING:
    import kye.compiled as compiled

@dataclass
class Error:
    err: str
    model: str
    rows: t.List[int]
    edges: t.List[str]
    loc: t.Optional[str]
    expected: t.Optional[str] = None
    
    def message(self):
        if self.err == 'WrongType':
            return f"Expected {self.model}.{self.edges[0]} to be of type '{self.expected}'"
        if self.err == 'MultipleValues':
            return f"Expected {self.model}.{self.edges[0]} to not have more than one value"
        if self.err == 'MissingValue':
            return f"Expected {self.model}.{self.edges[0]} to not be null"
        if self.err == 'AssertionFailed':
            return f"Assertion failed {self.expected or ''}"
        if self.err == 'MissingIndex':
            return f"{self.model} is missing index columns: {','.join(self.edges)}"
        if self.err == 'NonUniqueSubIndex':
            return f"{self.model} has non-unique sub-index: {','.join(self.edges)}"
        if self.err == 'IndexConflict':
            return f"{self.model} has index conflict: {','.join(self.edges)}"
        raise ValueError(f"Invalid error type: {self.err}")

class ValidationErrorReporter(ErrorReporter):
    errors: t.List[Error]
    df: pd.DataFrame

    def __init__(self, ):
        self.errors = []
    
    def use_source(self, df):
        self.df = df
    
    @property
    def had_error(self):
        return len(self.errors) > 0

    def wrong_type(self, edge: compiled.Edge):
        self.errors.append(Error(
            err='WrongType',
            model=edge.model,
            rows=[],
            edges=[edge.name],
            loc=edge.loc,
            expected=edge.type,
        ))
    
    def multiple_values(self, edge: compiled.Edge, rows: t.List[int]):
        self.errors.append(Error(
            err='MultipleValues',
            model=edge.model,
            rows=rows,
            edges=[edge.name],
            loc=edge.loc,
        ))
    
    def missing_values(self, edge: compiled.Edge, rows: t.List[int]):
        self.errors.append(Error(
            err='MissingValue',
            model=edge.model,
            rows=rows,
            edges=[edge.name],
            loc=edge.loc,
        ))
    
    def assertion_failed(self, assertion: compiled.Assertion, rows: t.List[int]):
        self.errors.append(Error(
            err='AssertionFailed',
            model=assertion.model,
            rows=rows,
            edges=assertion.edges,
            loc=assertion.loc,
            expected=assertion.msg,
        ))
    
    def missing_index(self, edge: compiled.Edge):
        self.errors.append(Error(
            err='MissingIndex',
            model=edge.model,
            rows=[],
            edges=[edge.name],
            loc=edge.loc,
        ))
    
    def non_unique_sub_index(self, model: compiled.Model, sub_idx_edges: t.List[str], rows: t.List[int]):
        self.errors.append(Error(
            err='NonUniqueSubIndex',
            model=model.name,
            rows=rows,
            edges=sub_idx_edges,
            loc=model.loc,
        ))
    
    def index_conflict(self, model: compiled.Model, sub_idx_edges: t.List[str], rows: t.List[int]):
        self.errors.append(Error(
            err='IndexConflict',
            model=model.name,
            rows=rows,
            edges=sub_idx_edges,
            loc=model.loc,
        ))
    
    @property
    def error_df(self):
        if not self.had_error:
            return pd.DataFrame(columns=['err','model','row','col','loc','expected'])
        return pd.DataFrame(map(asdict, self.errors)).explode('rows').explode('edges').rename(columns={
            'rows': 'row',
            'edges': 'col',
        })
    
    def print_highlighted_df(self):
        ROW_COUNT = 10
        if not self.had_error:
            return
        all_rows = False
        rows = set()
        cols = set()
        for err in self.errors:
            assert err.model == self.df.index.name
            if len(err.rows) == 0:
                all_rows = True
            rows.update(err.rows)
            cols.update(err.edges)
        rows = sorted(list(rows))
        num_errors = len(rows)
        if all_rows:
            rows += self.df.head(ROW_COUNT).index.tolist()
        rows = rows[:ROW_COUNT]
        # make column order match original order of columns
        cols = [col for col in self.df.columns if col in cols]
        print(self.df.loc[rows, cols].reset_index().to_string(index=False))
        if num_errors > len(rows):
            print(f'... and {num_errors - len(rows)} more rows')
    
    def report(self):
        for err in self.errors:
            loc = 'line ' + err.loc + ' ' if err.loc is not None else ''
            print(f"{loc}{err.message()}")
        self.print_highlighted_df()