from kye.compiler.models import Type
from typing import Any
import re

def json_to_edges(typ: Type, val: Any, loc='', row=None, table: str=None, edge='<root>'):
    if val is None:
        return
    elif type(val) is list:
        for i, item in enumerate(val):
            yield from json_to_edges(
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
                yield from json_to_edges(
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