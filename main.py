from pathlib import Path
# import kye
# from kye.loader.loader import Loader
# from kye.validate import Validate
from kye.validate import Table
from kye.types import from_compiled
import yaml
DIR = Path(__file__).parent

from kye.types import Type
from typing import Any
import re
def iter_json_edges(typ: Type, val: Any, loc='', row=None, table: str=None, edge='<root>'):
    if val is None:
        return
    elif type(val) is list:
        for i, item in enumerate(val):
            yield from iter_json_edges(
                table=table,
                row=row,
                loc=f'{loc}[{i}]',
                typ=typ,
                edge=edge,
                val=item
            )
    elif type(val) is dict:
        for key, item in val.items():
            if typ.has_edge(key):
                yield from iter_json_edges(
                    table=typ.ref,
                    row=loc,
                    loc=f'{loc}.{key}',
                    typ=typ.get_edge(key),
                    edge=key,
                    val=item
                )
    else:
        assert table is not None
        if type(val) is float:
            val = re.sub(r'\.0$', '', str(val))
        
        yield {
            'loc': loc,
            'tbl': table,
            'row': row,
            'col': edge,
            'val': val,
        }



if __name__ == '__main__':
    with open(DIR / 'examples/compiled.yaml') as f:
        src = yaml.safe_load(f)
    
    models = from_compiled(src)

    import duckdb
    import pandas as pd
    
    edges = pd.DataFrame(iter_json_edges(models['User'], [{
        'id': 1,
        # 'name': None,
    }, {
        'id': 1,
        'name': ['Bob','Macro'],
    }, {
        'id': 2,
        'name': 'Bill',
    }, {
        'age': 23,
    }, {
        'id': 3,
    }, {
        'id': 4,
        'name': 'Bill',
    }]))
    duckdb.sql('CREATE TABLE edges AS SELECT * FROM edges')
    edges = duckdb.table('edges')
    print(edges)
    table = Table(models['User'], edges.filter("tbl = 'User'"))
    print(table.row_indexes())
    # TODO: Associate partial indexes with their full indexes
    print('hi')
    # loader = Loader(models)
    # loader.from_json('User', [{
    #     'id': 1,
    #     'name': 'Joe',
    # }, {
    #     'id': 2,
    #     'name': 'Bill',
    # }])
    # loader.from_json('User', [{
    #     'id': 1,
    #     'name': 'Joey', # conflicting name
    # }])
    # validate = Validate(loader)
    # errors = validate.errors.aggregate(f"rule_ref, error_type").df()
    # if not errors.empty:
    #     print('\nThe following validation errors were found:')
    #     print(errors)
    # else:
    #     print('\n\tNo validation errors found.\n')
    # print('hi')