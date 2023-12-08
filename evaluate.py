from __future__ import annotations
from duckdb import DuckDBPyRelation
import kye.types as Types

class Type:
    type: Types.Type
    validate: str

    def __init__(self, type: Types.Type):
        self.type = type
        self.validate = None

    def is_valid(self):
        pass

    def get_edge(self, edge: Types.Edge):
        pass

class DataType:
    r: DuckDBPyRelation

    def __init__(self, type: Types.Type, r: DuckDBPyRelation):
        self.type = type

CALCULATIONS = {
    'Boolean': 'TRY_CAST(value as BOOLEAN) IS NOT NULL',
    'Number': 'TRY_CAST(value as DOUBLE) IS NOT NULL',
    'String.length': 'LENGTH(value)'
}

class CalculatedType:
    def __init__(self, type: Types.Type):
        self.type = type

class StringType(CalculatedType):
    def is_valid(self):
        return 'TRUE'
    
    def get_edge(self, edge: str):
        if edge == 'length':
            return 'length(value)'

class NumberType(CalculatedType):
    def is_valid(self):
        return 'TRY_CAST(value as DOUBLE) IS NOT NULL'

class Evaluate:
    table: DuckDBPyRelation

    def __init__(self, models: Types.Models, table: DuckDBPyRelation):
        self.models = models
        self.table = table
    
    def get_edge(self, typ: Types.Type, name: str) -> Type:
        edge = typ.get_edge(name)
        r = self.table.filter(f'ref = "{edge.ref}"').set_alias(edge.ref)

        # Validate cardinality
        # type_indexes = self.table.filter(f'type="{typ.ref}" & valid').aggregate('DISTINCT(index)')
        # counts = r.aggregate('index, COUNT(DISTINCT(value)) as cnt')
        


if __name__ == '__main__':
    import duckdb
    import pandas as pd
    from io import StringIO
    import kye

    api = kye.compile('''
    model User(id) {
        id: Number > 0
    }
    ''')

    df = pd.read_csv(StringIO("""
loc,index,format,value,type,edge,ref,valid
User_1.0.id,1,Number,42,User,id,User.id,True
    """), dtype=dict(
        loc=str,
        index=int,
        format=str,
        value=str,
        type=str,
        edge=str,
        ref=str,
        valid=bool
    ))
    db = duckdb.connect(':memory:')
    db.execute('CREATE TABLE edges AS SELECT * FROM df')
    print(db.sql('SELECT * FROM edges'))
    print('hi')