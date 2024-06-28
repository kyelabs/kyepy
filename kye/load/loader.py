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
from kye.vm.op import OP, parse_command

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
    engine: Engine
    reporter: ErrorReporter
    sources: t.Dict[str, Source]
    tables: t.Dict[str, ibis.Table]
    
    def __init__(self, compiled: t.Dict, engine: Engine, reporter: ErrorReporter):
        self.reporter = reporter
        self.engine = engine
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
    
    def get_source(self, source: str):
        return self.sources[source]
    
    def matches_dtype(self, edge: Edge, dtype: dtype.DataType):
        if edge.many:
            assert dtype.is_array(), "Expected array"
            dtype = dtype.value_type # type: ignore
        assert not dtype.is_nested(), "Unexpected nesting"
        if edge.type == 'String':
            assert dtype.is_string(), "Expected string"
        elif edge.type == 'Number':
            assert dtype.is_numeric(), "Expected numeric"
        elif edge.type == 'Integer':
            assert dtype.is_integer(), "Expected integer"
        elif edge.type == 'Boolean':
            assert dtype.is_boolean(), "Expected boolean"
        else:
            raise Exception(f"Unknown type {edge.type}")