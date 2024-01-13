import duckdb
from duckdb import DuckDBPyConnection
from kye.types import Type, EDGE, TYPE_REF
from kye.engine.load_json import json_to_edges
from kye.engine.validate import check_table
import pandas as pd

class DuckDBEngine:
    db: DuckDBPyConnection
    models: dict[TYPE_REF, Type]

    def __init__(self, models: dict[TYPE_REF, Type]):
        self.db = duckdb.connect(':memory:')
        self.models = models
        self.has_validated = True
        self.create_tables()
    
    def create_tables(self):
        self.db.sql('''
        CREATE TABLE edges (
            loc TEXT NOT NULL,
            tbl TEXT NOT NULL,
            row TEXT NOT NULL,
            col TEXT NOT NULL,
            val TEXT NOT NULL,
            idx UINT64
        );
        CREATE TABLE errors (
            err TEXT NOT NULL,
            tbl TEXT NOT NULL,
            idx TEXT,
            row TEXT,
            col TEXT,
            val TEXT
        );
        ''')
    
    @property
    def edges(self):
        return self.db.table('edges')

    @property
    def errors(self):
        return self.db.table('errors')
    
    def load_json(self, model: TYPE_REF, data):
        self.has_validated = False
        assert model in self.models
        df = pd.DataFrame(json_to_edges(self.models[model], data))
        r = duckdb.df(df, connection=self.db)
        r.select('*, NULL as idx').insert_into('edges')
    
    def validate(self):
        if not self.has_validated:
            self.db.sql('''
            TRUNCATE errors;
            UPDATE edges SET idx = NULL;
            ''')
            for model_name in self.edges.aggregate('distinct tbl').fetchall():
                model = self.models[model_name[0]]
                check_table(model, self.db)
            self.has_validated = True
    
    def get_table(self, model: TYPE_REF):
        assert model in self.models
        self.validate()
        typ = self.models[model]
        table = self.db.sql(f'''
        PIVOT (
            SELECT * FROM edges
            ANTI JOIN errors on
                edges.tbl=errors.tbl
                AND (edges.row = errors.row OR errors.row IS NULL)
                AND (edges.col = errors.col OR errors.col IS NULL)
                AND (edges.val = errors.val OR errors.val IS NULL)
                AND (edges.idx = errors.idx OR errors.idx IS NULL)
            WHERE tbl = '{model}'
        ) ON col USING list(val) GROUP BY idx
        ''')
        select = []
        for edge in typ.edges:
            if edge in table.columns:
                if typ.allows_multiple(edge):
                    select.append(f'list_distinct({edge}) as {edge}')
                else:
                    select.append(f'list_any_value({edge}) as {edge}')
            else:
                if typ.allows_multiple(edge):
                    select.append(f'CAST([] AS VARCHAR[]) as {edge}')
                else:
                    select.append(f'CAST(NULL AS VARCHAR) as {edge}')
        return table.select(','.join(select))

    def fetch_json(self, model: TYPE_REF):
        assert model in self.models
        table = self.get_table(model)
        return table.fetchdf().to_dict(orient='records')