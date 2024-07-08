from __future__ import annotations
import typing as t
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kye.errors import ErrorReporter
from kye.vm.op import OP, parse_command
from kye.compiler import Compiled

Expr = t.List[tuple[OP, list]]

@dataclass
class Edge:
    name: str
    null: bool
    many: bool
    type: str
    expr: t.Optional[Expr] = None

@dataclass
class Assertion:
    msg: str
    expr: Expr

class Source:
    name: str
    index: t.List[str]
    edges: t.Dict[str, Edge]
    assertions: t.List[Assertion]
    
    def __init__(self, name: str, index: t.List[str], assertions: t.List[Assertion]):
        self.name = name
        self.index = index
        self.assertions = assertions
        self.edges = {}
    
    def define(self, edge: Edge):
        self.edges[edge.name] = edge
    
    def __getitem__(self, key: str) -> Edge:
        return self.edges[key]

class Loader:
    reporter: ErrorReporter
    sources: t.Dict[str, Source]
    tables: t.Dict[str, pd.DataFrame]
    
    def __init__(self, compiled: Compiled, reporter: ErrorReporter):
        self.reporter = reporter
        self.sources = {}
        self.tables = {}

        for model_name, model in compiled['models'].items():
            index_edges = set()
            for index in model['indexes']:
                for edge in index:
                    index_edges.add(edge)
            source = Source(
                name=model_name,
                index=list(index_edges),
                assertions=[
                    Assertion(
                        msg=assertion['msg'],
                        expr=[
                            parse_command(cmd)
                            for cmd in assertion['expr']
                        ],
                    )
                    for assertion in model.get('assertions', [])
                ],
            )
            self.sources[model_name] = source
            for edge_name, edge in model['edges'].items():
                expr = None
                if 'expr' in edge:
                    expr = [
                        parse_command(cmd)
                        for cmd in edge['expr']
                    ]
                source.define(Edge(
                    name=edge_name,
                    null=edge.get('null', False),
                    many=edge.get('many', False),
                    type=edge['type'],
                    expr=expr,
                ))
    
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
        
        return table
    
    def get_source(self, source: str):
        return self.sources[source]
    
    def matches_dtype(self, edge: Edge, col: pd.Series):
        if edge.many:
            col = col.explode().dropna().infer_objects()
        if edge.type == 'String':
            assert col.dtype == 'object', "Expected string"
        elif edge.type == 'Number':
            assert pd.api.types.is_numeric_dtype(col.dtype), "Expected number"
        elif edge.type == 'Integer':
            assert pd.api.types.is_integer_dtype(col.dtype), "Expected integer"
        elif edge.type == 'Boolean':
            assert pd.api.types.is_bool_dtype(col.dtype), "Expected boolean"
        else:
            raise Exception(f"Unknown type {edge.type}")